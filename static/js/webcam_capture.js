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
 *     and store it in the hidden "face_embedding_json" field so it is submitted
 *     together with the admin form save (works for both new and existing records).
 *
 * Depends on: face-api-utils.js  (must be loaded first)
 *
 * The script is loaded via the FaceAdmin change_form_template and expects:
 *   - A file input with id="id_photo"
 *   - A hidden input with id="id_face_embedding_json"
 *   - window.FACE_API_MODELS_URL set by the change_form template (optional)
 */

(function () {
  "use strict";

  function init() {
    const photoInput = document.getElementById("id_photo");
    if (!photoInput) return; // not on the Face change form

    // Inject "Capture from webcam" button next to the photo field
    const captureBtn = document.createElement("button");
    captureBtn.type = "button";
    captureBtn.textContent = "📷 ถ่ายภาพจากกล้อง";
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
    thumb.alt = "ตัวอย่างรูปภาพ";
    thumbWrap.appendChild(thumb);
    captureBtn.insertAdjacentElement("afterend", thumbWrap);

    // Status line (embedding / enroll feedback)
    const statusLine = document.createElement("div");
    statusLine.id = "enroll-status";
    statusLine.style.cssText = "margin-top:6px;font-size:.82rem;color:#555";
    thumbWrap.insertAdjacentElement("afterend", statusLine);

    // Build modal via shared utility
    const { openModal } = FaceApiUtils.buildWebcamModal("webcam");

    // Wire the page-level "Capture from webcam" button to open the modal
    // with the context for this single-Face form.
    captureBtn.addEventListener("click", () => {
      openModal({
        photoInput,
        hiddenField: document.getElementById("id_face_embedding_json"),
        statusLine,
        thumbWrap,
        thumb,
      });
    });

    // Extract embedding when a file is selected via the file input directly
    photoInput.addEventListener("change", async () => {
      const file = photoInput.files && photoInput.files[0];
      if (!file) return;

      const hiddenField = document.getElementById("id_face_embedding_json");

      // Show thumbnail preview
      const reader = new FileReader();
      reader.onload = async (e) => {
        const dataURL = e.target.result;
        thumb.src = dataURL;
        thumbWrap.style.display = "block";

        // Extract embedding
        statusLine.textContent = "⏳ กำลังตรวจจับใบหน้าและดึงข้อมูล…";
        const result = await FaceApiUtils.extractEmbedding(dataURL);
        const msg = FaceApiUtils.embeddingStatusMessage(result);

        if (msg !== null) {
          statusLine.textContent = msg;
          return;
        }

        const embedding = result.embedding;
        if (hiddenField) {
          hiddenField.value = JSON.stringify(Array.from(embedding));
        }
        statusLine.textContent =
          "✅ พบใบหน้า! ข้อมูลใบหน้าพร้อมแล้ว (เวกเตอร์ขนาด " + embedding.length + " มิติ) บันทึกฟอร์มเพื่อลงทะเบียน";
      };
      reader.readAsDataURL(file);
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
