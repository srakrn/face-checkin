/**
 * webcam_capture.js
 *
 * Webcam capture widget for the Face admin change form.
 *
 * Responsibilities:
 *  1. Open a modal with a live <video> preview using getUserMedia.
 *  2. On "Capture", draw the frame to a <canvas>, convert to a Blob/File,
 *     and set it on the Django admin photo <input type="file"> field.
 *  3. Show a thumbnail preview of the captured image.
 *  4. After capture, run face-api.js (if loaded) to extract a 128-d embedding
 *     and POST it together with the photo to /faces/<pk>/enroll/.
 *
 * The script is loaded via the FaceAdmin change_form_template and expects:
 *   - A file input with id="id_photo"
 *   - window.FACE_ENROLL_URL set by the change_form template
 *   - window.FACE_API_MODELS_URL set by the change_form template (optional)
 */

(function () {
  "use strict";

  // ── helpers ──────────────────────────────────────────────────────────────

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  }

  function dataURLtoBlob(dataURL) {
    const [header, data] = dataURL.split(",");
    const mime = header.match(/:(.*?);/)[1];
    const binary = atob(data);
    const array = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) array[i] = binary.charCodeAt(i);
    return new Blob([array], { type: mime });
  }

  /** Load an image from a dataURL into an HTMLImageElement. */
  function loadImage(dataURL) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = dataURL;
    });
  }

  // ── modal markup ─────────────────────────────────────────────────────────

  function buildModal() {
    const modal = document.createElement("div");
    modal.id = "webcam-modal";
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
        <video id="webcam-video" autoplay playsinline muted
               style="width:100%;border-radius:4px;background:#000;display:block"></video>
        <canvas id="webcam-canvas" style="display:none"></canvas>
        <div id="webcam-preview-wrap" style="display:none;margin-top:8px">
          <img id="webcam-preview" style="width:100%;border-radius:4px" alt="Captured photo" />
        </div>
        <div id="webcam-status" style="margin-top:8px;font-size:.85rem;color:#555"></div>
        <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
          <button type="button" id="webcam-capture-btn"
                  style="padding:8px 18px;background:#417690;color:#fff;border:none;border-radius:4px;cursor:pointer">
            📷 Capture
          </button>
          <button type="button" id="webcam-retake-btn"
                  style="display:none;padding:8px 18px;background:#6c757d;color:#fff;border:none;border-radius:4px;cursor:pointer">
            🔄 Retake
          </button>
          <button type="button" id="webcam-use-btn"
                  style="display:none;padding:8px 18px;background:#28a745;color:#fff;border:none;border-radius:4px;cursor:pointer">
            ✅ Use this photo
          </button>
          <button type="button" id="webcam-close-btn"
                  style="padding:8px 18px;background:#dc3545;color:#fff;border:none;border-radius:4px;cursor:pointer;margin-left:auto">
            ✕ Close
          </button>
        </div>
      </div>`;

    document.body.appendChild(modal);
    return modal;
  }

  // ── face-api.js embedding extraction ─────────────────────────────────────

  /**
   * Returns:
   *   { embedding: Float32Array(128) }  — face found
   *   { embedding: null, reason: "no_face" }  — face-api loaded but no face detected
   *   { embedding: null, reason: "not_loaded" }  — face-api.js not available
   *   { embedding: null, reason: "models_missing" }  — model weights not found
   *   { embedding: null, reason: "error", message: string }  — unexpected error
   */
  async function extractEmbedding(dataURL) {
    if (typeof faceapi === "undefined") {
      return { embedding: null, reason: "not_loaded" };
    }

    const modelsUrl =
      window.FACE_API_MODELS_URL || "/static/js/face-api/models";

    try {
      // Load models if not already loaded
      if (!faceapi.nets.ssdMobilenetv1.isLoaded) {
        await faceapi.nets.ssdMobilenetv1.loadFromUri(modelsUrl);
      }
      if (!faceapi.nets.faceRecognitionNet.isLoaded) {
        await faceapi.nets.faceRecognitionNet.loadFromUri(modelsUrl);
      }
      if (!faceapi.nets.faceLandmark68Net.isLoaded) {
        await faceapi.nets.faceLandmark68Net.loadFromUri(modelsUrl);
      }
    } catch (e) {
      // Model weight files not present (404) or network error
      return { embedding: null, reason: "models_missing", message: e.message };
    }

    try {
      // Use a regular HTMLImageElement — face-api.js works best with DOM elements
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

  // ── main init ─────────────────────────────────────────────────────────────

  function init() {
    const photoInput = document.getElementById("id_photo");
    if (!photoInput) return; // not on the Face change form

    // Inject "Capture from webcam" button next to the photo field
    const captureBtn = document.createElement("button");
    captureBtn.type = "button";
    captureBtn.textContent = "📷 Capture from webcam";
    captureBtn.style.cssText =
      "margin-left:8px;padding:4px 12px;background:#417690;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:.85rem";
    photoInput.insertAdjacentElement("afterend", captureBtn);

    // Thumbnail preview (shown after capture / if photo already set)
    const thumbWrap = document.createElement("div");
    thumbWrap.id = "photo-thumb-wrap";
    thumbWrap.style.cssText = "margin-top:8px;display:none";
    const thumb = document.createElement("img");
    thumb.id = "photo-thumb";
    thumb.style.cssText = "max-width:200px;border-radius:4px;border:1px solid #ccc";
    thumb.alt = "Photo preview";
    thumbWrap.appendChild(thumb);
    captureBtn.insertAdjacentElement("afterend", thumbWrap);

    // Status line (embedding / enroll feedback)
    const statusLine = document.createElement("div");
    statusLine.id = "enroll-status";
    statusLine.style.cssText = "margin-top:6px;font-size:.82rem;color:#555";
    thumbWrap.insertAdjacentElement("afterend", statusLine);

    // Build modal (lazy)
    const modal = buildModal();
    const video = modal.querySelector("#webcam-video");
    const canvas = modal.querySelector("#webcam-canvas");
    const previewWrap = modal.querySelector("#webcam-preview-wrap");
    const preview = modal.querySelector("#webcam-preview");
    const webcamStatus = modal.querySelector("#webcam-status");
    const captureBtnModal = modal.querySelector("#webcam-capture-btn");
    const retakeBtn = modal.querySelector("#webcam-retake-btn");
    const useBtn = modal.querySelector("#webcam-use-btn");
    const closeBtn = modal.querySelector("#webcam-close-btn");

    let stream = null;
    let capturedDataURL = null;

    function stopStream() {
      if (stream) {
        stream.getTracks().forEach((t) => t.stop());
        stream = null;
      }
    }

    function openModal() {
      modal.style.display = "flex";
      capturedDataURL = null;
      previewWrap.style.display = "none";
      video.style.display = "block";
      captureBtnModal.style.display = "";
      retakeBtn.style.display = "none";
      useBtn.style.display = "none";
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

    function closeModal() {
      stopStream();
      modal.style.display = "none";
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

    async function usePhoto() {
      if (!capturedDataURL) return;

      // Convert dataURL → File and set on the photo input
      const blob = dataURLtoBlob(capturedDataURL);
      const file = new File([blob], "webcam_capture.jpg", { type: "image/jpeg" });
      const dt = new DataTransfer();
      dt.items.add(file);
      photoInput.files = dt.files;

      // Show thumbnail
      thumb.src = capturedDataURL;
      thumbWrap.style.display = "block";

      closeModal();

      // ── Optional: extract embedding via face-api.js and POST to enroll ──
      const enrollUrl = window.FACE_ENROLL_URL;
      if (!enrollUrl) {
        statusLine.textContent =
          "📸 Photo set. Save the form to persist. (New record — enroll after first save.)";
        return;
      }

      statusLine.textContent = "⏳ Detecting face and extracting embedding…";

      const result = await extractEmbedding(capturedDataURL);

      if (result.reason === "not_loaded") {
        // face-api.js bundle not present — photo will be saved via normal admin save
        statusLine.textContent =
          "📸 Photo set. face-api.js not loaded — embedding will not be extracted. " +
          "Save the form to persist the photo.";
        return;
      }

      if (result.reason === "models_missing") {
        statusLine.textContent =
          "📸 Photo set. Face recognition model weights not found at " +
          (window.FACE_API_MODELS_URL || "/static/js/face-api/models") +
          " — embedding will not be extracted. Save the form to persist the photo.";
        return;
      }

      if (result.reason === "no_face") {
        statusLine.textContent =
          "⚠️ No face detected in the captured photo. " +
          "Try again with better lighting or a clearer face view. " +
          "The photo has been set — save the form to persist it without an embedding.";
        return;
      }

      if (result.reason === "error") {
        statusLine.textContent = "❌ Face detection error: " + result.message;
        return;
      }

      // We have a valid embedding — POST photo + embedding to the enroll endpoint
      const embedding = result.embedding; // Float32Array(128)
      statusLine.textContent = "⏳ Saving photo and embedding…";

      try {
        const formData = new FormData();
        formData.append("photo", file);
        formData.append("embedding", JSON.stringify(Array.from(embedding)));

        const resp = await fetch(enrollUrl, {
          method: "POST",
          headers: { "X-CSRFToken": getCookie("csrftoken") },
          body: formData,
        });

        if (resp.ok) {
          const data = await resp.json();
          statusLine.textContent =
            "✅ Embedding saved! (" + (data.embedding_length || 128) + "-d vector). Reloading…";
          // Reload the page so the admin reflects the saved embedding
          setTimeout(() => location.reload(), 1200);
        } else {
          const err = await resp.json().catch(() => ({}));
          statusLine.textContent =
            "❌ Enroll failed: " + (err.error || resp.statusText);
        }
      } catch (e) {
        statusLine.textContent = "❌ Network error: " + e.message;
      }
    }

    // ── event wiring ──────────────────────────────────────────────────────

    captureBtn.addEventListener("click", openModal);
    captureBtnModal.addEventListener("click", captureFrame);
    retakeBtn.addEventListener("click", retake);
    useBtn.addEventListener("click", usePhoto);
    closeBtn.addEventListener("click", closeModal);

    // Close on backdrop click
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });

    // Show thumbnail if photo already exists (edit form)
    const currentPhotoLink = document.querySelector(".field-photo a");
    if (currentPhotoLink) {
      thumb.src = currentPhotoLink.href;
      thumbWrap.style.display = "block";
    }
  }

  // Run after DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
