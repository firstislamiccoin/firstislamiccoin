/// BIP39 mnemonic + BIP32 HD key derivation for FirstIslamicCoin.
///
/// Derivation path: m/44'/coinType'/0'/0/index (BIP44 external chain),
/// where coinType comes from NetworkConfig -- see its `bip44CoinType` field
/// doc for the mainnet/testnet split (mainnet's 9770 is an unregistered
/// SLIP-44 placeholder; testnet uses the standard shared testnet index 1).
/// (This comment used to cite a `PARAMETERS.md` and CAC's coin type 3377 --
/// both leftover from the CAC fork this file came from and never updated
/// for FIC: this repo has no PARAMETERS.md, and FIC's own coin type is
/// 9770, not 3377. See firstislamiccoin-core/src/wallet/scriptpubkeyman.cpp
/// for the ground truth this wallet's coin types must match.)
library;

import 'dart:typed_data';

import 'package:bip32/bip32.dart' as bip32;
import 'package:bip39/bip39.dart' as bip39;

import '../config/network_config.dart';

class DerivedKey {
  final Uint8List privateKey; // 32 bytes
  final Uint8List publicKey; // 33 bytes, compressed
  const DerivedKey(this.privateKey, this.publicKey);
}

/// Generate a new random 12-word BIP39 mnemonic (128 bits of entropy).
String generateMnemonic() => bip39.generateMnemonic(strength: 128);

/// Validate a mnemonic's checksum. Does not verify it was ever actually
/// used to derive any specific wallet -- just that it's well-formed.
bool isValidMnemonic(String mnemonic) => bip39.validateMnemonic(mnemonic);

/// BIP32 root node for a given mnemonic (+ optional BIP39 passphrase).
/// This, and everything derived from it, must never be persisted as-is --
/// only the mnemonic itself is stored (see services/wallet_storage.dart),
/// and only in platform secure storage.
bip32.BIP32 _rootNode(String mnemonic, {String passphrase = ''}) {
  final seed = bip39.mnemonicToSeed(mnemonic, passphrase: passphrase);
  return bip32.BIP32.fromSeed(seed);
}

/// Derive the key at m/44'/coinType'/0'/0/[index] for [network].
DerivedKey deriveKey({
  required String mnemonic,
  required NetworkConfig network,
  required int index,
  String passphrase = '',
  bool change = false,
}) {
  final root = _rootNode(mnemonic, passphrase: passphrase);
  final path =
      "m/44'/${network.bip44CoinType}'/0'/${change ? 1 : 0}/$index";
  final node = root.derivePath(path);
  final priv = node.privateKey;
  if (priv == null) {
    // BIP32.fromSeed always yields a node with a private key present;
    // this should be unreachable, but fail loudly rather than silently
    // returning a half-valid key if it ever isn't.
    throw StateError('Derived node has no private key (path=$path)');
  }
  return DerivedKey(Uint8List.fromList(priv), Uint8List.fromList(node.publicKey));
}
