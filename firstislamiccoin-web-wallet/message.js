// Bitcoin-style "sign message with an address" / "verify a signature
// against an address" -- proves control of an address's private key
// without spending anything. Mirrors firstislamiccoin-core/src/util/
// message.cpp's MessageHash/MessageSign/MessageVerify exactly (same
// MESSAGE_MAGIC, same double-SHA256 preimage, same 65-byte compact
// recoverable signature format), so a signature produced here verifies
// with `firstislamiccoin-cli verifymessage` and vice versa.
//
// Only P2PKH addresses are supported, matching the node's own
// MessageVerify (which rejects anything but a PKHash destination): the
// scheme works by recovering a public key from the signature and
// comparing its hash160 to the address, which only makes sense for an
// address that *is* a pubkey hash, not a script (P2SH/multisig) or
// witness program.
import * as secp from "https://cdn.jsdelivr.net/npm/@noble/secp256k1@2.1.0/+esm";
import { sha256 } from "https://cdn.jsdelivr.net/npm/@noble/hashes@1.4.0/sha256/+esm";
import { hmac } from "https://cdn.jsdelivr.net/npm/@noble/hashes@1.4.0/hmac/+esm";
import { hash160, decodeAddress, AddressType, varInt, concatBytes, bytesToHex } from "./crypto.js";

secp.etc.hmacSha256Sync = (key, ...msgs) => hmac(sha256, key, secp.etc.concatBytes(...msgs));

const MESSAGE_MAGIC = "FirstIslamicCoin Signed Message:\n";
const encoder = new TextEncoder();

function messageHash(message) {
  const magicBytes = encoder.encode(MESSAGE_MAGIC);
  const msgBytes = encoder.encode(message);
  // Mirrors CHashWriter's operator<<(const std::string&): a compact-size
  // length prefix followed by the raw bytes, for each of the two strings.
  const preimage = concatBytes(
    varInt(magicBytes.length), magicBytes,
    varInt(msgBytes.length), msgBytes
  );
  return sha256(sha256(preimage));
}

function base64Encode(bytes) {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}
function base64Decode(str) {
  const binary = atob(str);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

// Returns a base64 signature: header byte (27 + recovery id + 4, the
// "+4" signalling a compressed pubkey -- this wallet only ever uses
// compressed keys) followed by the 64-byte compact (r||s) signature.
// This is Bitcoin Core's CKey::SignCompact layout.
export function signMessage(privateKey, message) {
  const hash = messageHash(message);
  const sig = secp.sign(hash, privateKey);
  const header = 27 + sig.recovery + 4;
  return base64Encode(concatBytes(new Uint8Array([header]), sig.toCompactRawBytes()));
}

// Throws on a malformed signature or a non-P2PKH address. Returns true/
// false for whether the signature actually matches; never throws just
// because the signature doesn't match (that's a normal "no" outcome).
export function verifyMessage(address, signatureBase64, message, network) {
  const decoded = decodeAddress(address, network);
  if (decoded.type !== AddressType.p2pkh) {
    throw new Error("Only P2PKH addresses support message signing/verification");
  }
  let sigBytes;
  try {
    sigBytes = base64Decode(signatureBase64.trim());
  } catch {
    throw new Error("Malformed signature (not valid base64)");
  }
  if (sigBytes.length !== 65) throw new Error("Malformed signature (wrong length)");
  const header = sigBytes[0];
  if (header < 27 || header > 42) throw new Error("Malformed signature (bad header byte)");
  const recovery = (header - 27) & 3;
  const hash = messageHash(message);
  let pubkey;
  try {
    const sig = secp.Signature.fromCompact(sigBytes.slice(1)).addRecoveryBit(recovery);
    pubkey = sig.recoverPublicKey(hash).toRawBytes(true);
  } catch {
    return false; // a syntactically valid but cryptographically bogus signature
  }
  return bytesToHex(hash160(pubkey)) === bytesToHex(decoded.hash);
}
