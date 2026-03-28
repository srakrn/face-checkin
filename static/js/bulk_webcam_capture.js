/**
 * bulk_webcam_capture.js
 *
 * Bulk webcam capture widget for the FaceGroup admin change form.
 *
 * For each inline Face row in the FaceGroup admin, this script injects a
 * "Capture from webcam" button next to the photo field.  Clicking it opens
 * a shared modal with a live <video> preview.  After capture, face-api.js
 * extracts a 128-d embedding and stores it in the per-row hidden
 * ``face_embedding_json`` field (rendered by FaceInlineForm) so it is
 * submitted together with the admin formset save.
 *
 * Depends on: face-api-utils.js  (must be loaded first)
 *
 * Expects:
 *   - window.FACE_API_MODELS_URL set by the change_form template (optional)
 *   - Django admin inline rows with id matching "faces-<n>"
 *   - Each row has a file input named "faces-<n>-photo"
 *   - Each row has a hidden input named "faces-<n>-face_embedding_json"
 *     (rendered by FaceInlineForm)
 */

(function () {
  "use strict";

  // Single shared modal instance for all inline rows
  let sharedModal = null;

  // ── per-row widget injection ──────────────────────────────────────────────

  /**
   * Inject the webcam capture button + thumbnail + status line into a single
   * inline Face row.  The hidden embedding field is already rendered by
   * FaceInlineForm — we just locate it.
   *
   * @param {HTMLElement} row    - The <tr> or <div> for one inline Face entry
   * @param {string}      prefix - Django formset prefix, e.g. "faces"
   * @param {number}      index  - Row index (0-based)
   */
  function injectRowWidget(row, prefix, index) {
    const photoInput = row.querySelector(
      `input[name="${prefix}-${index}-photo"]`
    );
    if (!photoInput) return; // row has no photo field (e.g. the empty extra form template)

    // Avoid double-injection
    if (row.dataset.webcamInjected) return;
    row.dataset.webcamInjected = "1";

    // The hidden embedding field is rendered by FaceInlineForm
    const hiddenField = row.querySelector(
      `input[name="${prefix}-${index}-face_embedding_json"]`
    );

    // "Capture from webcam" button
    const captureBtn = document.createElement("button");
    captureBtn.type = "button";
    captureBtn.textContent = "📷 ถ่ายภาพจากกล้อง";
    captureBtn.style.cssText =
      "margin-left:8px;padding:4px 12px;background:#417690;color:#fff;" +
      "border:none;border-radius:4px;cursor:pointer;font-size:.85rem";
    photoInput.insertAdjacentElement("afterend", captureBtn);

    // Thumbnail preview
    const thumbWrap = document.createElement("div");
    thumbWrap.style.cssText = "margin-top:6px;display:none";
    const thumb = document.createElement("img");
    thumb.style.cssText =
      "max-width:160px;border-radius:4px;border:1px solid #ccc";
    thumb.alt = "ตัวอย่างรูปภาพ";
    thumbWrap.appendChild(thumb);
    captureBtn.insertAdjacentElement("afterend", thumbWrap);

    // Status line
    const statusLine = document.createElement("div");
    statusLine.style.cssText = "margin-top:4px;font-size:.80rem;color:#555";
    thumbWrap.insertAdjacentElement("afterend", statusLine);

    // Show existing photo thumbnail if editing
    const currentPhotoLink = row.querySelector(".field-photo a");
    if (currentPhotoLink) {
      thumb.src = currentPhotoLink.href;
      thumbWrap.style.display = "block";
    }

    // Open the shared modal for this row
    captureBtn.addEventListener("click", () => {
      sharedModal.openModal({ photoInput, hiddenField, statusLine, thumbWrap, thumb });
    });

    // Extract embedding when a file is selected via the file input directly
    photoInput.addEventListener("change", async () => {
      const file = photoInput.files && photoInput.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = async (e) => {
        const dataURL = e.target.result;
        thumb.src = dataURL;
        thumbWrap.style.display = "block";

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
  }

  // ── row scanning and mutation observation ─────────────────────────────────

  function injectAllRows(prefix) {
    const totalFormsInput = document.querySelector(
      `input[name="${prefix}-TOTAL_FORMS"]`
    );
    if (!totalFormsInput) return;

    const total = parseInt(totalFormsInput.value, 10);
    for (let i = 0; i < total; i++) {
      const row =
        document.getElementById(`${prefix}-${i}`) ||
        document.querySelector(`[id="${prefix}-${i}"]`);
      if (row) {
        injectRowWidget(row, prefix, i);
      }
    }
  }

  function observeInlineRows(prefix) {
    const inlineGroup = document.getElementById(`${prefix}-group`);
    if (!inlineGroup) return;

    const observer = new MutationObserver(() => {
      injectAllRows(prefix);
    });
    observer.observe(inlineGroup, { childList: true, subtree: true });
  }

  // ── main init ─────────────────────────────────────────────────────────────

  function init() {
    // Only run on the FaceGroup change form (has the faces inline)
    const totalFormsInput = document.querySelector(
      'input[name="faces-TOTAL_FORMS"]'
    );
    if (!totalFormsInput) return;

    // Build the single shared modal via shared utility
    sharedModal = FaceApiUtils.buildWebcamModal("bulk-webcam");

    const prefix = "faces";
    injectAllRows(prefix);
    observeInlineRows(prefix);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
