// Optional PIN-based encryption for the recovery phrase at rest.
//
// Without a PIN set, the mnemonic sits in localStorage as plain text
// under `fic_mnemonic` -- exactly as before, and exactly as the
// onboarding screen's security note describes. Setting a PIN moves it to
// `fic_mnemonic_encrypted` (removing the plaintext key) as a JSON blob
// produced by real encryption -- PBKDF2-SHA256 (200,000 iterations) to
// derive an AES-256-GCM key from the PIN, via the browser's own
// `crypto.subtle` (Web Crypto API), not a bespoke or weakened scheme.
// This is a genuine improvement over a UI-only lock screen: someone who
// reads localStorage directly (devtools, a malicious extension, a stolen
// browser profile) gets ciphertext, not the phrase. It does NOT protect
// against a PIN that's easy to guess, or against anyone with access to
// an already-unlocked tab -- said plainly rather than oversold.

const PBKDF2_ITERATIONS = 200_000;

function bytesToHex(bytes) {
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}

async function deriveAesKey(pin, saltBytes) {
  const pinKey = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(pin), "PBKDF2", false, ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: saltBytes, iterations: PBKDF2_ITERATIONS, hash: "SHA-256" },
    pinKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function encryptMnemonic(mnemonic, pin) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveAesKey(pin, salt);
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv }, key, new TextEncoder().encode(mnemonic)
  );
  return {
    salt: bytesToHex(salt),
    iv: bytesToHex(iv),
    ciphertext: bytesToHex(new Uint8Array(ciphertext)),
  };
}

// Throws (AES-GCM authentication failure) if the PIN is wrong.
export async function decryptMnemonic(blob, pin) {
  const salt = hexToBytes(blob.salt);
  const iv = hexToBytes(blob.iv);
  const key = await deriveAesKey(pin, salt);
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv }, key, hexToBytes(blob.ciphertext)
  );
  return new TextDecoder().decode(plaintext);
}

export function isPinSet() {
  return localStorage.getItem("fic_mnemonic_encrypted") != null;
}

export function loadEncryptedBlob() {
  const raw = localStorage.getItem("fic_mnemonic_encrypted");
  return raw ? JSON.parse(raw) : null;
}

export async function setPin(mnemonic, pin) {
  const blob = await encryptMnemonic(mnemonic, pin);
  localStorage.setItem("fic_mnemonic_encrypted", JSON.stringify(blob));
  localStorage.removeItem("fic_mnemonic");
}

export function removePin(mnemonic) {
  localStorage.setItem("fic_mnemonic", mnemonic);
  localStorage.removeItem("fic_mnemonic_encrypted");
}
