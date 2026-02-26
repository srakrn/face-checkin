/**
 * session_qr.js
 * Provides showKioskQR(relativeUrl, sessionName) for the Session admin list.
 * Dynamically loads qrcode.js from a CDN, then renders a modal with the QR code.
 */

(function () {
  "use strict";

  // ── QR library loader ──────────────────────────────────────────────────────
  const QR_LIB_URL =
    "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js";

  function loadQRLib(callback) {
    if (window.QRCode) {
      callback();
      return;
    }
    const script = document.createElement("script");
    script.src = QR_LIB_URL;
    script.onload = callback;
    script.onerror = function () {
      alert("Failed to load QR code library. Check your internet connection.");
    };
    document.head.appendChild(script);
  }

  // ── Modal helpers ──────────────────────────────────────────────────────────
  function buildModal() {
    const overlay = document.createElement("div");
    overlay.id = "kiosk-qr-overlay";
    overlay.style.cssText = [
      "position:fixed",
      "inset:0",
      "background:rgba(0,0,0,.55)",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "z-index:99999",
    ].join(";");

    const box = document.createElement("div");
    box.style.cssText = [
      "background:#fff",
      "border-radius:8px",
      "padding:32px 40px",
      "text-align:center",
      "box-shadow:0 8px 32px rgba(0,0,0,.3)",
      "max-width:360px",
      "width:90%",
    ].join(";");

    const title = document.createElement("h2");
    title.id = "kiosk-qr-title";
    title.style.cssText = "margin:0 0 4px;font-size:1.1rem;color:#333";

    const subtitle = document.createElement("p");
    subtitle.id = "kiosk-qr-subtitle";
    subtitle.style.cssText =
      "margin:0 0 20px;font-size:.8rem;color:#666;word-break:break-all";

    const qrContainer = document.createElement("div");
    qrContainer.id = "kiosk-qr-canvas";
    qrContainer.style.cssText =
      "display:inline-block;margin-bottom:20px";

    const closeBtn = document.createElement("button");
    closeBtn.textContent = "Close";
    closeBtn.className = "button";
    closeBtn.style.cssText = "display:block;margin:0 auto";
    closeBtn.onclick = closeModal;

    box.appendChild(title);
    box.appendChild(subtitle);
    box.appendChild(qrContainer);
    box.appendChild(closeBtn);
    overlay.appendChild(box);

    // Close on backdrop click
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) closeModal();
    });

    // Close on Escape
    document._kioskQREscHandler = function (e) {
      if (e.key === "Escape") closeModal();
    };
    document.addEventListener("keydown", document._kioskQREscHandler);

    return overlay;
  }

  function closeModal() {
    const overlay = document.getElementById("kiosk-qr-overlay");
    if (overlay) overlay.remove();
    if (document._kioskQREscHandler) {
      document.removeEventListener("keydown", document._kioskQREscHandler);
      delete document._kioskQREscHandler;
    }
  }

  // ── Public API ─────────────────────────────────────────────────────────────
  window.showKioskQR = function (relativeUrl, sessionName) {
    // Build absolute URL so the QR code works from any device on the network
    const absoluteUrl =
      window.location.protocol + "//" + window.location.host + relativeUrl;

    loadQRLib(function () {
      // Remove any existing modal
      closeModal();

      const overlay = buildModal();
      document.body.appendChild(overlay);

      document.getElementById("kiosk-qr-title").textContent = sessionName;
      document.getElementById("kiosk-qr-subtitle").textContent = absoluteUrl;

      new window.QRCode(document.getElementById("kiosk-qr-canvas"), {
        text: absoluteUrl,
        width: 256,
        height: 256,
        colorDark: "#000000",
        colorLight: "#ffffff",
        correctLevel: window.QRCode.CorrectLevel.M,
      });
    });
  };
})();
