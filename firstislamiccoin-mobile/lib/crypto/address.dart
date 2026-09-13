/// FirstIslamicCoin address encoding.
///
/// Deliberately hand-implemented (Base58Check + bech32 only, via the
/// narrow `bs58check`/`bech32` packages) rather than depending on a
/// higher-level Bitcoin-family package's address logic, so every step is
/// checkable against the ground-truth sample addresses already generated
/// and verified in Phase 1 (see PARAMETERS.md section 3.1) -- see
/// test/crypto/address_test.dart, which asserts against those exact
/// samples, not just internal self-consistency.
library;

import 'dart:typed_data';

import 'package:bech32/bech32.dart';
import 'package:bs58check/bs58check.dart' as bs58check;
import 'package:pointycastle/digests/ripemd160.dart';
import 'package:pointycastle/digests/sha256.dart';

import '../config/network_config.dart';

/// RIPEMD160(SHA256(data)) -- the standard Bitcoin-family "hash160".
Uint8List hash160(Uint8List data) {
  final sha = SHA256Digest().process(data);
  return RIPEMD160Digest().process(sha);
}

/// Encode a 20-byte pubkey hash as a P2PKH address for [network].
String p2pkhAddress(Uint8List pubkeyHash20, NetworkConfig network) {
  if (pubkeyHash20.length != 20) {
    throw ArgumentError('pubkeyHash20 must be exactly 20 bytes');
  }
  final payload = Uint8List(21);
  payload[0] = network.p2pkhVersion;
  payload.setRange(1, 21, pubkeyHash20);
  return bs58check.encode(payload);
}

/// Encode a 20-byte script hash as a P2SH address for [network].
String p2shAddress(Uint8List scriptHash20, NetworkConfig network) {
  if (scriptHash20.length != 20) {
    throw ArgumentError('scriptHash20 must be exactly 20 bytes');
  }
  final payload = Uint8List(21);
  payload[0] = network.p2shVersion;
  payload.setRange(1, 21, scriptHash20);
  return bs58check.encode(payload);
}

/// Encode a 20-byte pubkey hash as a native segwit (P2WPKH, witness
/// version 0) bech32 address for [network]. FIC inherits Bitcoin-derived
/// segwit support unchanged (see PARAMETERS.md); this wallet defaults new
/// receive addresses to this format.
String p2wpkhAddress(Uint8List pubkeyHash20, NetworkConfig network) {
  if (pubkeyHash20.length != 20) {
    throw ArgumentError('pubkeyHash20 must be exactly 20 bytes');
  }
  final witnessProgram = _convertBits(pubkeyHash20, 8, 5, true);
  final data = [0, ...witnessProgram]; // witness version 0 + program
  return const Bech32Codec()
      .encode(Bech32(network.bech32Hrp, Uint8List.fromList(data)));
}

/// Decode any FIC address (P2PKH, P2SH, or bech32 P2WPKH) back to its
/// scriptPubKey hash + type, for building transaction outputs when
/// sending. Throws [FormatException] if [address] doesn't decode as any
/// recognized FIC address type for [network].
class DecodedAddress {
  final AddressType type;
  final Uint8List hash;
  const DecodedAddress(this.type, this.hash);
}

enum AddressType { p2pkh, p2sh, p2wpkh }

DecodedAddress decodeAddress(String address, NetworkConfig network) {
  // Try bech32 first (distinct alphabet/checksum from base58, so a
  // mis-decode as the wrong type is not a silent-failure risk).
  if (address.toLowerCase().startsWith('${network.bech32Hrp}1')) {
    final decoded = const Bech32Codec().decode(address, address.length);
    if (decoded.hrp != network.bech32Hrp) {
      throw const FormatException('Address is for a different network');
    }
    final witnessVersion = decoded.data[0];
    final program = _convertBits(
        Uint8List.fromList(decoded.data.sublist(1)), 5, 8, false);
    if (witnessVersion != 0 || program.length != 20) {
      throw const FormatException('Unsupported witness version/program length');
    }
    return DecodedAddress(AddressType.p2wpkh, program);
  }

  final decoded = bs58check.decode(address);
  if (decoded.length != 21) {
    throw const FormatException('Invalid Base58Check address length');
  }
  final version = decoded[0];
  final payload = decoded.sublist(1);
  if (version == network.p2pkhVersion) {
    return DecodedAddress(AddressType.p2pkh, payload);
  } else if (version == network.p2shVersion) {
    return DecodedAddress(AddressType.p2sh, payload);
  }
  throw FormatException(
      'Address version byte $version does not match ${network.name}');
}

/// Bit-width conversion for bech32 witness programs (8-bit bytes <-> 5-bit
/// groups), per BIP173. Not from a package because bech32 (Dart)'s public
/// API only exposes the HRP+data codec, not this segwit-specific helper.
Uint8List _convertBits(Uint8List data, int fromBits, int toBits, bool pad) {
  int acc = 0;
  int bits = 0;
  final result = <int>[];
  final maxv = (1 << toBits) - 1;
  for (final value in data) {
    if (value < 0 || value >> fromBits != 0) {
      throw const FormatException('Invalid data for bit conversion');
    }
    acc = (acc << fromBits) | value;
    bits += fromBits;
    while (bits >= toBits) {
      bits -= toBits;
      result.add((acc >> bits) & maxv);
    }
  }
  if (pad) {
    if (bits > 0) {
      result.add((acc << (toBits - bits)) & maxv);
    }
  } else if (bits >= fromBits || ((acc << (toBits - bits)) & maxv) != 0) {
    throw const FormatException('Invalid padding in bit conversion');
  }
  return Uint8List.fromList(result);
}
