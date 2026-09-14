// QR code generation/scanning, isolated in one small module so the CDN
// imports live in exactly one place (same convention crypto.js uses for
// its dependencies). Neither library is security- or consensus-relevant
// (unlike the hand-rolled address/signing code in crypto.js), so pulling
// them from a CDN rather than hand-rolling is the right tradeoff here.
import QRCode from "https://cdn.jsdelivr.net/npm/qrcode@1.5.3/+esm";
import jsQR from "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/+esm";

export async function renderQr(canvas, text) {
  await QRCode.toCanvas(canvas, text, { width: 220, margin: 1 });
}

// Starts the device camera and repeatedly scans frames until a QR code is
// found or `stop()` is called. Returns { stop } immediately; `onResult`
// fires exactly once with the decoded string, or `onError` once if the
// camera itself can't be accessed (permission denied, no camera, etc.).
export function startQrScanner({ video, canvas, onResult, onError }) {
  let stream = null;
  let stopped = false;
  let rafId = null;

  function stop() {
    stopped = true;
    if (rafId) cancelAnimationFrame(rafId);
    if (stream) stream.getTracks().forEach((t) => t.stop());
  }

  function tick() {
    if (stopped) return;
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(imageData.data, imageData.width, imageData.height);
      if (code && code.data) {
        stop();
        onResult(code.data);
        return;
      }
    }
    rafId = requestAnimationFrame(tick);
  }

  navigator.mediaDevices
    .getUserMedia({ video: { facingMode: "environment" } })
    .then((s) => {
      if (stopped) { s.getTracks().forEach((t) => t.stop()); return; }
      stream = s;
      video.srcObject = s;
      video.play();
      rafId = requestAnimationFrame(tick);
    })
    .catch((e) => onError(e));

  return { stop };
}
