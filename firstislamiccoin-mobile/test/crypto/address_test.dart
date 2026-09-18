// Two kinds of ground truth here, not one:
//
//  - Testnet samples were captured live from the actual testnet node
//    (`firstislamiccoin-cli -testnet getnewaddress`/`getaddressinfo`/
//    `decodescript`, against fic-testnet-node0-1), so decoding one and
//    re-encoding the extracted hash is a real cross-implementation
//    round-trip check against the C++ node's own address encoding, not
//    just internal self-consistency.
//  - Mainnet has no live node to capture a sample from: mainnet's
//    genesis premine is still the "nothing up my sleeve" placeholder
//    (see docs/genesis.md), and `CMainParams::m_genesis_premine_placeholder`
//    makes the node refuse to start mainnet at all until the Phase 10 key
//    ceremony replaces it. So mainnet cases here are self-generated
//    (encode a fixed hash, decode it back) -- internally consistent, but
//    not yet cross-checked against a second implementation. Replace with
//    a live-node sample once mainnet actually starts.
import 'dart:typed_data';

import 'package:fic_wallet/config/network_config.dart';
import 'package:fic_wallet/crypto/address.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('P2PKH', () {
    test('mainnet: encode/decode round-trips (self-generated, no live mainnet node yet)', () {
      final hashBytes = Uint8List.fromList(List<int>.generate(20, (i) => i));
      final address = p2pkhAddress(hashBytes, NetworkConfig.mainnet);
      expect(address.startsWith('F'), isTrue); // version byte 36, docs/genesis.md
      final decoded = decodeAddress(address, NetworkConfig.mainnet);
      expect(decoded.type, AddressType.p2pkh);
      expect(decoded.hash, hashBytes);
    });

    test('testnet: decodes and re-encodes a real address from the live testnet node', () {
      // firstislamiccoin-cli -testnet getnewaddress "" legacy
      const sample = 'mhEHcfXxicGKESzqN2DwdwevFzDJE8fXo5';
      // Base58Check-decoding `sample` by hand confirms the real 20-byte hash
      // ends in "...00d5e" -- the previous fixture here had a stray trailing
      // "8" (41 hex chars, not 40) from a transcription slip. It happened to
      // not fail this test because `_hexToBytes` silently truncates
      // odd-length hex to floor(length/2) bytes, which -- purely by luck,
      // since the extra character was the very last one -- dropped exactly
      // the stray digit and left the other 20 bytes intact. See the bech32
      // P2WPKH testnet case below for the same class of typo where the
      // dropped character wasn't at the end, and did change the result.
      final expectedHash = Uint8List.fromList(
          _hexToBytes('12c94ef860ac24bf144ffa48f97950362db00d5e')); // from getaddressinfo's scriptPubKey
      final decoded = decodeAddress(sample, NetworkConfig.testnet);
      expect(decoded.type, AddressType.p2pkh);
      expect(decoded.hash, expectedHash);
      expect(p2pkhAddress(decoded.hash, NetworkConfig.testnet), sample);
    });
  });

  group('P2SH', () {
    test('mainnet: encode/decode round-trips (self-generated, no live mainnet node yet)', () {
      final hashBytes = Uint8List.fromList(List<int>.generate(20, (i) => 19 - i));
      final address = p2shAddress(hashBytes, NetworkConfig.mainnet);
      expect(address.startsWith('C'), isTrue); // version byte 28, docs/genesis.md
      final decoded = decodeAddress(address, NetworkConfig.mainnet);
      expect(decoded.type, AddressType.p2sh);
      expect(decoded.hash, hashBytes);
    });

    test('testnet: decodes and re-encodes a real 2-of-2 multisig address from the live testnet node', () {
      // firstislamiccoin-cli -testnet createmultisig 2 [...] legacy
      const sample = '2NESve3evyGhcnMneZfdci7tEquruCkhNRg';
      final decoded = decodeAddress(sample, NetworkConfig.testnet);
      expect(decoded.type, AddressType.p2sh);
      expect(decoded.hash.length, 20);
      expect(p2shAddress(decoded.hash, NetworkConfig.testnet), sample);
    });
  });

  group('bech32 P2WPKH', () {
    test('mainnet: round-trips through encode/decode', () {
      final hashBytes = Uint8List.fromList(List<int>.generate(20, (i) => i));
      final address = p2wpkhAddress(hashBytes, NetworkConfig.mainnet);
      expect(address.startsWith('fic1'), isTrue);
      final decoded = decodeAddress(address, NetworkConfig.mainnet);
      expect(decoded.type, AddressType.p2wpkh);
      expect(decoded.hash, hashBytes);
    });

    test('testnet: decodes and re-encodes a real address from the live testnet node', () {
      // firstislamiccoin-cli -testnet getnewaddress "" bech32
      const sample = 'tfic1qajsvccmkxck7tvf0suz55v0dlqmg8u3ay6ln39';
      // Root cause of this test's prior failure: this fixture was missing
      // its trailing hex nibble ("...683f23" instead of the real
      // "...683f23d", 39 hex chars instead of 40). Independently decoding
      // `sample` by hand with a standalone BIP173 bech32 implementation
      // confirms the witness program is genuinely 20 bytes ending in
      // "...683f23d" -- 20 bytes is also the only length BIP141 allows for
      // a P2WPKH (witness version 0) program, since it's HASH160 of the
      // pubkey. So `decodeAddress` producing 20 bytes was always correct;
      // it was this fixture's expected value that was wrong (and, on top of
      // that, `_hexToBytes` silently truncated the odd-length typo'd hex to
      // 19 bytes instead of throwing, which is how a 1-character transcription
      // slip turned into a byte-count assertion failure instead of a loud
      // parse error).
      final expectedHash =
          Uint8List.fromList(_hexToBytes('eca0cc6376362de5b12f87054a31edf83683f23d')); // getaddressinfo's witness_program
      final decoded = decodeAddress(sample, NetworkConfig.testnet);
      expect(decoded.type, AddressType.p2wpkh);
      expect(decoded.hash, expectedHash);
      expect(p2wpkhAddress(decoded.hash, NetworkConfig.testnet), sample);
    });
  });

  group('cross-network rejection', () {
    test('testnet address is rejected on mainnet decode', () {
      expect(
        () => decodeAddress('mhEHcfXxicGKESzqN2DwdwevFzDJE8fXo5', NetworkConfig.mainnet),
        throwsFormatException,
      );
    });

    test('mainnet address is rejected on testnet decode', () {
      final hashBytes = Uint8List.fromList(List<int>.generate(20, (i) => i));
      final mainnetAddress = p2pkhAddress(hashBytes, NetworkConfig.mainnet);
      expect(
        () => decodeAddress(mainnetAddress, NetworkConfig.testnet),
        throwsFormatException,
      );
    });
  });
}

List<int> _hexToBytes(String hex) {
  // An odd-length hex string can only mean a transcription typo in a test
  // fixture (bytes are always whole hex-digit pairs) -- fail loudly instead
  // of floor-dividing and silently dropping the dangling nibble, which is
  // exactly how a missing/extra character in a fixture above turned into a
  // confusing byte-count assertion failure instead of an immediate, obvious
  // parse error.
  if (hex.length.isOdd) {
    throw FormatException('Odd-length hex string (typo?): $hex');
  }
  final out = List<int>.filled(hex.length ~/ 2, 0);
  for (var i = 0; i < out.length; i++) {
    out[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return out;
}
