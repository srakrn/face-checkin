/**
 * face-api-utils.js
 *
 * Shared utilities for webcam capture and face embedding extraction.
 *
 * Exposes a single global `window.FaceApiUtils` object consumed by:
 *   - webcam_capture.js      (single-Face admin change form)
 *   - bulk_webcam_capture.js (FaceGroup admin change form with inline rows)
 *
 * Face detection net choice
 * ─────────────────────────
 * We use `SsdMobilenetv1` (+ `faceLandmark68Net` + `faceRecognitionNet`) for
 * all embedding extraction.  Compared to `TinyFaceDetector`:
 *
 *   • SsdMobilenetv1 is significantly more accurate for small / angled faces,
 *     which matters for enrollment where a missed detection means no embedding.
 *   • The 128-d descriptor produced by `faceRecognitionNet` is the same
 *     regardless of which detector is used; detector choice only affects
 *     whether a face is found at all.
 *   • The kiosk check-in page also uses SsdMobilenetv1 (default options),
 *     so enrollment and matching use the same detection pipeline — consistent.
 *   • Speed is not a concern for the admin enrollment flow (one photo at a time).
 *
 * Required model weight files (under `window.FACE_API_MODELS_URL`):
 *   ssd_mobilenetv1_model-weights_manifest.json + .bin
 *   face_landmark_68_model-weights_manifest.json + .bin
 *   face_recognition_model-weights_manifest.json + .bin
 */

(function (global) {
  "use strict";

  // ── helpers ────────────────────────────────────────────────────────────────

  /**
   * Convert a dataURL string to a Blob.
   * @param {string} dataURL
   * @returns {Blob}
   */
  function dataURLtoBlob(dataURL) {
    const [header, data] = dataURL.split(",");
    const mime = header.match(/:(.*?);/)[1];
    const binary = atob(data);
    const array = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) array[i] = binary.charCodeAt(i);
    return new Blob([array], { type: mime });
  }

  /**
   * Load a dataURL into an HTMLImageElement.
   * @param {string} dataURL
   * @returns {Promise<HTMLImageElement>}
   */
  function loadImage(dataURL) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = dataURL;
    });
  }

  // ── face embedding extraction ──────────────────────────────────────────────

  /**
   * Extract a 128-d face embedding from a dataURL using face-api.js.
   *
   * Returns one of:
   *   { embedding: Float32Array(128) }                          — face found
   *   { embedding: null, reason: "not_loaded" }                 — faceapi not available
   *   { embedding: null, reason: "models_missing", message }    — model weights 404 / network error
   *   { embedding: null, reason: "no_face" }                    — no face detected
   *   { embedding: null, reason: "error", message }             — unexpected error
   *
   * @param {string} dataURL
   * @returns {Promise<object>}
   */
  async function extractEmbedding(dataURL) {
    if (typeof faceapi === "undefined") {
      return { embedding: null, reason: "not_loaded" };
    }

    const modelsUrl =
      global.FACE_API_MODELS_URL || "/static/js/face-api/models";

    try {
      if (!faceapi.nets.ssdMobilenetv1.isLoaded) {
        await faceapi.nets.ssdMobilenetv1.loadFromUri(modelsUrl);
      }
      if (!faceapi.nets.faceLandmark68Net.isLoaded) {
        await faceapi.nets.faceLandmark68Net.loadFromUri(modelsUrl);
      }
      if (!faceapi.nets.faceRecognitionNet.isLoaded) {
        await faceapi.nets.faceRecognitionNet.loadFromUri(modelsUrl);
      }
    } catch (e) {
      return { embedding: null, reason: "models_missing", message: e.message };
    }

    try {
      const img = await loadImage(dataURL);
      const detection = await faceapi
        .detectSingleFace(img, new faceapi.SsdMobilenetv1Options())
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (!detection) {
        return { embedding: null, reason: "no_face" };
      }
      return { embedding: detection.descriptor }; // Float32Array(128)
    } catch (e) {
      return { embedding: null, reason: "error", message: e.message };
    }
  }

  // ── shared status message renderer ────────────────────────────────────────

  /**
   * Render a human-readable status message for an `extractEmbedding` result.
   * Returns null when the result contains a valid embedding (no message needed).
   *
   * @param {object} result  — return value of extractEmbedding()
   * @returns {string|null}
   */
  function embeddingStatusMessage(result) {
    const modelsUrl =
      global.FACE_API_MODELS_URL || "/static/js/face-api/models";

    switch (result.reason) {
      case "not_loaded":
        return (
          "📸 Photo set. face-api.js not loaded — embedding will not be extracted. " +
          "Save the form to persist the photo."
        );
      case "models_missing":
        return (
          "📸 Photo set. Face recognition model weights not found at " +
          modelsUrl +
          " — embedding will not be extracted. Save the form to persist the photo."
        );
      case "no_face":
        return (
          "⚠️ No face detected in the captured photo. " +
          "Try again with better lighting or a clearer face view. " +
          "The photo has been set — save the form to persist it without an embedding."
        );
      case "error":
        return "❌ Face detection error: " + result.message;
      default:
        return null; // embedding is valid
    }
  }

  // ── webcam modal builder ───────────────────────────────────────────────────

  /**
   * Build and attach a webcam capture modal to `document.body`.
   *
   * The modal is reusable: call `openModal(context)` to open it for a specific
   * target context object:
   *   {
   *     photoInput  : HTMLInputElement   — <input type="file"> to receive the captured file
   *     hiddenField : HTMLInputElement   — hidden field to receive the JSON embedding
   *     statusLine  : HTMLElement        — element to display status messages
   *     thumbWrap   : HTMLElement        — wrapper shown/hidden around the thumbnail
   *     thumb       : HTMLImageElement   — thumbnail <img>
   *   }
   *
   * @param {string} idPrefix  — prefix for element IDs, e.g. "webcam" or "bulk-webcam"
   * @returns {{ modal: HTMLElement, openModal: function }}
   */
  function buildWebcamModal(idPrefix) {
    const modal = document.createElement("div");
    modal.id = idPrefix + "-modal";
    modal.style.cssText = [
      "display:none",
      "position:fixed",
      "inset:0",
      "background:rgba(0,0,0,.7)",
      "z-index:9999",
      "align-items:center",
      "justify-content:center",
    ].join(";");

    modal.innerHTML = `
      <div style="background:#fff;border-radius:8px;padding:24px;max-width:520px;width:95%;box-shadow:0 4px 32px rgba(0,0,0,.4)">
        <h3 style="margin:0 0 12px;font-size:1.1rem">Capture from webcam</h3>
        <video id="${idPrefix}-video" autoplay playsinline muted
               style="width:100%;border-radius:4px;background:#000;display:block"></video>
        <canvas id="${idPrefix}-canvas" style="display:none"></canvas>
        <div id="${idPrefix}-preview-wrap" style="display:none;margin-top:8px">
          <img id="${idPrefix}-preview" style="width:100%;border-radius:4px" alt="Captured photo" />
        </div>
        <div id="${idPrefix}-status" style="margin-top:8px;font-size:.85rem;color:#555"></div>
        <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
          <button type="button" id="${idPrefix}-capture-btn"
                  style="padding:8px 18px;background:#417690;color:#fff;border:none;border-radius:4px;cursor:pointer">
            📷 Capture
          </button>
          <button type="button" id="${idPrefix}-retake-btn"
                  style="display:none;padding:8px 18px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer">
            🔄 Retake
          </button>
          <button type="button" id="${idPrefix}-use-btn"
                  style="display:none;padding:8px 18px;background:#28a745;color:#fff;border:none;border-radius:4px;cursor:pointer">
            ✅ Use this photo
          </button>
          <button type="button" id="${idPrefix}-close-btn"
                  style="padding:8px 18px;background:#dc3545;color:#fff;border:none;border-radius:4px;cursor:pointer;margin-left:auto">
            ✕ Close
          </button>
        </div>
      </div>`;

    document.body.appendChild(modal);

    const video = modal.querySelector("#" + idPrefix + "-video");
    const canvas = modal.querySelector("#" + idPrefix + "-canvas");
    const previewWrap = modal.querySelector("#" + idPrefix + "-preview-wrap");
    const preview = modal.querySelector("#" + idPrefix + "-preview");
    const webcamStatus = modal.querySelector("#" + idPrefix + "-status");
    const captureBtnModal = modal.querySelector("#" + idPrefix + "-capture-btn");
    const retakeBtn = modal.querySelector("#" + idPrefix + "-retake-btn");
    const useBtn = modal.querySelector("#" + idPrefix + "-use-btn");
    const closeBtn = modal.querySelector("#" + idPrefix + "-close-btn");

    let stream = null;
    let capturedDataURL = null;
    let currentContext = null; // set by openModal()

    function stopStream() {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        stream = null;
      }
    }

    function startCamera() {
      webcamStatus.textContent = "Starting camera…";
      navigator.mediaDevices
        .getUserMedia({ video: { facingMode: "user" }, audio: false })
        .then((s) => {
          stream = s;
          video.srcObject = s;
          webcamStatus.textContent = "";
        })
        .catch((err) => {
          webcamStatus.textContent = "Camera error: " + err.message;
        });
    }

    function openModal(context) {
      currentContext = context || null;
      capturedDataURL = null;
      previewWrap.style.display = "none";
      video.style.display = "block";
      captureBtnModal.style.display = "";
      retakeBtn.style.display = "none";
      useBtn.style.display = "none";
      modal.style.display = "flex";
      startCamera();
    }

    function closeModal() {
      stopStream();
      modal.style.display = "none";
      currentContext = null;
    }

    function captureFrame() {
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      canvas.getContext("2d").drawImage(video, 0, 0);
      capturedDataURL = canvas.toDataURL("image/jpeg", 0.92);
      preview.src = capturedDataURL;
      previewWrap.style.display = "block";
      video.style.display = "none";
      captureBtnModal.style.display = "none";
      retakeBtn.style.display = "";
      useBtn.style.display = "";
      webcamStatus.textContent = "Photo captured. Click 'Use this photo' to apply.";
      stopStream();
    }

    function retake() {
      capturedDataURL = null;
      previewWrap.style.display = "none";
      video.style.display = "block";
      captureBtnModal.style.display = "";
      retakeBtn.style.display = "none";
      useBtn.style.display = "none";
      startCamera();
    }

    async function usePhoto() {
      if (!capturedDataURL) return;

      const ctx = currentContext;
      if (!ctx) return;

      // Convert dataURL → File and set on the photo input
      const blob = dataURLtoBlob(capturedDataURL);
      const file = new File([blob], "webcam_capture.jpg", { type: "image/jpeg" });
      const dt = new DataTransfer();
      dt.items.add(file);
      ctx.photoInput.files = dt.files;

      // Show thumbnail
      ctx.thumb.src = capturedDataURL;
      ctx.thumbWrap.style.display = "block";

      closeModal();

      // Extract embedding via face-api.js
      ctx.statusLine.textContent = "⏳ Detecting face and extracting embedding…";

      const result = await extractEmbedding(capturedDataURL);
      const msg = embeddingStatusMessage(result);

      if (msg !== null) {
        ctx.statusLine.textContent = msg;
        return;
      }

      // Valid embedding — store in hidden field
      const embedding = result.embedding; // Float32Array(128)
      if (ctx.hiddenField) {
        ctx.hiddenField.value = JSON.stringify(Array.from(embedding));
      }
      ctx.statusLine.textContent =
        "✅ Face detected! Embedding ready (" + embedding.length + "-d vector). Save the form to enroll.";
    }

    // Event wiring
    captureBtnModal.addEventListener("click", captureFrame);
    retakeBtn.addEventListener("click", retake);
    useBtn.addEventListener("click", usePhoto);
    closeBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });

    return { modal, openModal };
  }

  // ── public API ─────────────────────────────────────────────────────────────

  global.FaceApiUtils = {
    dataURLtoBlob,
    loadImage,
    extractEmbedding,
    embeddingStatusMessage,
    buildWebcamModal,
  };
})(window);
