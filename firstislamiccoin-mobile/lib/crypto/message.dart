/// Bitcoin-style "sign message with an address" / "verify a signature
/// against an address" -- proves control of an address's private key
/// without spending anything. Mirrors firstislamiccoin-core/src/util/
/// message.cpp's MessageHash/MessageSign/MessageVerify exactly (same
/// MESSAGE_MAGIC, same double-SHA256 preimage, same 65-byte compact
/// recoverable signature format) and web-wallet/message.js's algorithm,
/// so a signature produced on either platform -- or by `firstislamiccoin-cli
/// signmessage` -- verifies on any of the others.
///
/// Only P2PKH addresses are supported, matching the node's own
/// MessageVerify (which rejects anything but a PKHash destination): the
/// scheme recovers a pubkey from the signature and compares its
/// hash160 to the address, which only makes sense for an address that
/// *is* a pubkey hash, not a script (P2SH/multisig) or witness program.
///
/// pointycastle's ECDSASigner has no built-in public-key recovery
/// (unlike @noble/secp256k1 on the web side, which computes it as part
/// of signing), so the recovery id is found here by brute force: try
/// each of the 4 possible ids, recover a candidate pubkey via the
/// standard ECDSA recovery formula Q = r^-1 * (s*R - z*G), and keep
/// whichever one matches the pubkey we already know we signed with.
/// Verification (where the pubkey is genuinely unknown up front) uses
/// the same formula with the recid read straight out of the signature.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:pointycastle/api.dart';
import 'package:pointycastle/digests/sha256.dart';
import 'package:pointycastle/ecc/api.dart';
import 'package:pointycastle/ecc/curves/secp256k1.dart';
import 'package:pointycastle/macs/hmac.dart';
import 'package:pointycastle/signers/ecdsa_signer.dart';

import 'address.dart' show hash160, decodeAddress, AddressType;
import '../config/network_config.dart';

const String _messageMagic = 'FirstIslamicCoin Signed Message:\n';

// secp256k1's field prime p (distinct from the curve order n) -- only
// needed for the astronomically rare recid-overflow case (x = r + n
// happens to still be < p), which every mainstream implementation
// checks for correctness even though it essentially never triggers.
final BigInt _secp256k1P = BigInt.parse(
  'fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f',
  radix: 16,
);

Uint8List _doubleSha256(Uint8List data) {
  final once = SHA256Digest().process(data);
  return SHA256Digest().process(once);
}

Uint8List _varInt(int n) {
  if (n < 0xfd) return Uint8List.fromList([n]);
  if (n <= 0xffff) {
    final b = Uint8List(3)..[0] = 0xfd;
    b.buffer.asByteData().setUint16(1, n, Endian.little);
    return b;
  }
  final b = Uint8List(5)..[0] = 0xfe;
  b.buffer.asByteData().setUint32(1, n, Endian.little);
  return b;
}

BigInt _bytesToBigInt(Uint8List bytes) {
  var result = BigInt.zero;
  for (final b in bytes) {
    result = (result << 8) | BigInt.from(b);
  }
  return result;
}

Uint8List _bigIntTo32Bytes(BigInt v) {
  final out = Uint8List(32);
  var value = v;
  for (var i = 31; i >= 0; i--) {
    out[i] = (value & BigInt.from(0xff)).toInt();
    value = value >> 8;
  }
  return out;
}

BigInt _mod(BigInt a, BigInt n) => ((a % n) + n) % n;

Uint8List messageHash(String message) {
  final magicBytes = utf8.encode(_messageMagic);
  final msgBytes = utf8.encode(message);
  final preimage = Uint8List.fromList([
    ..._varInt(magicBytes.length), ...magicBytes,
    ..._varInt(msgBytes.length), ...msgBytes,
  ]);
  return _doubleSha256(preimage);
}

/// Standard ECDSA public-key recovery: Q = r^-1 * (s*R - z*G), where R
/// is the curve point whose x-coordinate is r (picked via [recid]'s
/// parity/overflow bits) and z is the message hash as a scalar.
ECPoint? _recoverPublicKey(
  BigInt r,
  BigInt s,
  BigInt z,
  int recid,
  ECDomainParameters domain,
) {
  final n = domain.n;
  final xOverflow = recid >> 1;
  final isYOdd = recid & 1;
  final x = r + BigInt.from(xOverflow) * n;
  if (x >= _secp256k1P) return null;
  ECPoint R;
  try {
    R = domain.curve.decompressPoint(isYOdd, x);
  } catch (_) {
    return null;
  }
  if (R.isInfinity) return null;
  final rInv = r.modInverse(n);
  final sR = R * s;
  final zG = domain.G * _mod(z, n);
  if (sR == null || zG == null) return null;
  final diff = sR - zG;
  if (diff == null) return null;
  return diff * rInv;
}

/// Returns a base64 signature: header byte (27 + recovery id + 4, the
/// "+4" signalling a compressed pubkey -- this wallet only ever uses
/// compressed keys) followed by the 64-byte compact (r||s) signature.
/// This is Bitcoin Core's CKey::SignCompact layout.
String signMessage(Uint8List privateKey, Uint8List publicKeyCompressed, String message) {
  final ECDomainParameters domain = ECCurve_secp256k1();
  final priv = ECPrivateKey(_bytesToBigInt(privateKey), domain);
  final hash = messageHash(message);
  final signer = ECDSASigner(null, HMac(SHA256Digest(), 64));
  signer.init(true, PrivateKeyParameter(priv));
  var sig = signer.generateSignature(hash) as ECSignature;
  var s = sig.s;
  final n = domain.n;
  if (s > (n >> 1)) {
    s = n - s; // enforce low-S, same convention as transaction.dart's DER signing
  }
  final r = sig.r;
  final z = _bytesToBigInt(hash);
  int? recid;
  for (var candidate = 0; candidate < 4; candidate++) {
    final recovered = _recoverPublicKey(r, s, z, candidate, domain);
    if (recovered == null) continue;
    final recoveredBytes = recovered.getEncoded(true);
    if (_bytesEqual(recoveredBytes, publicKeyCompressed)) {
      recid = candidate;
      break;
    }
  }
  if (recid == null) {
    throw StateError('Could not determine a recovery id for this signature');
  }
  final header = 27 + recid + 4;
  final out = Uint8List.fromList([header, ..._bigIntTo32Bytes(r), ..._bigIntTo32Bytes(s)]);
  return base64.encode(out);
}

bool _bytesEqual(Uint8List a, Uint8List b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

/// Throws [FormatException] on a malformed signature or a non-P2PKH
/// address. Returns true/false for whether the signature actually
/// matches; never throws just because it doesn't match -- that's a
/// normal "no" outcome, not an error.
bool verifyMessage(String address, String signatureBase64, String message, NetworkConfig network) {
  final decoded = decodeAddress(address, network);
  if (decoded.type != AddressType.p2pkh) {
    throw const FormatException('Only P2PKH addresses support message signing/verification');
  }
  Uint8List sigBytes;
  try {
    sigBytes = base64.decode(signatureBase64.trim());
  } catch (_) {
    throw const FormatException('Malformed signature (not valid base64)');
  }
  if (sigBytes.length != 65) {
    throw const FormatException('Malformed signature (wrong length)');
  }
  final header = sigBytes[0];
  if (header < 27 || header > 42) {
    throw const FormatException('Malformed signature (bad header byte)');
  }
  final recid = (header - 27) & 3;
  final r = _bytesToBigInt(sigBytes.sublist(1, 33));
  final s = _bytesToBigInt(sigBytes.sublist(33, 65));
  final ECDomainParameters domain = ECCurve_secp256k1();
  final z = _bytesToBigInt(messageHash(message));
  final pubkeyPoint = _recoverPublicKey(r, s, z, recid, domain);
  if (pubkeyPoint == null) return false;
  final pubkeyHash = hash160(pubkeyPoint.getEncoded(true));
  return _bytesEqual(pubkeyHash, decoded.hash);
}
