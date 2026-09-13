/// Ties together key derivation, secure storage, and the gateway API into
/// the app's single wallet state object.
///
/// NOTHING in this file, or anything it calls, performs mining, staking,
/// or any background/periodic computation -- see docs/store-compliance.md.
/// Every network call here is a single request/response HTTP call
/// initiated by explicit user action (opening a screen, tapping send).
library;

import 'package:flutter/foundation.dart';

import '../config/network_config.dart';
import '../crypto/address.dart';
import '../crypto/keys.dart';
import '../crypto/offline_signing.dart' as offline;
import '../crypto/transaction.dart' as tx;
import '../crypto/xpub.dart' as xpub;
import 'gateway_api.dart';
import 'wallet_storage.dart';

/// One destination in a [WalletService.sendTransaction] call -- a plain
/// pair rather than anything JSON-serializable, since it only ever
/// exists transiently while a send is being built.
class SendRecipient {
  final String address;
  final int amountSatoshis;
  const SendRecipient({required this.address, required this.amountSatoshis});
}

class WalletService extends ChangeNotifier {
  final WalletStorage _storage = WalletStorage();
  GatewayApi _gateway = GatewayApi(NetworkConfig.mainnet);

  NetworkConfig network = NetworkConfig.mainnet;
  String? _mnemonic;
  String? _stakeToken;
  bool loaded = false;

  // 'system' (default), 'dark', or 'light' -- kept as a plain string
  // rather than Flutter's ThemeMode enum so this file doesn't need a
  // material.dart import; main.dart maps it to ThemeMode.
  String themeMode = 'system';

  // Every BIP44 index this wallet has generated on this device for the
  // current network -- not full gap-limit discovery, see activeAddress().
  List<int> _addressIndices = [0];
  int activeIndex = 0;
  final Map<int, DerivedKey> _keys = {};
  final Map<int, String> _addresses = {};

  bool get hasWallet => _mnemonic != null;

  List<int> get addressIndices => List.unmodifiable(_addressIndices);

  /// Logged in to the custodial staking service's gateway account. This is
  /// entirely separate from [hasWallet]/the mnemonic -- it's an account on
  /// the staking pool, not a property of the on-chain wallet itself.
  bool get stakingLoggedIn => _stakeToken != null;

  Future<void> bootstrap() async {
    final storedNetwork = await _storage.readActiveNetwork();
    network = storedNetwork == 'testnet' ? NetworkConfig.testnet : NetworkConfig.mainnet;
    _gateway = GatewayApi(network);
    _mnemonic = await _storage.readMnemonic();
    _stakeToken = await _storage.readStakeToken();
    themeMode = await _storage.readThemeMode() ?? 'system';
    if (_mnemonic != null) await _deriveAllKnownAddresses();
    loaded = true;
    notifyListeners();
  }

  Future<void> setThemeMode(String mode) async {
    themeMode = mode;
    await _storage.saveThemeMode(mode);
    notifyListeners();
  }

  Future<void> _deriveAllKnownAddresses() async {
    _addressIndices = await _storage.readAddressIndices(_networkStorageName());
    for (final idx in _addressIndices) {
      await ensureKey(idx);
    }
    if (!_addressIndices.contains(activeIndex)) {
      activeIndex = _addressIndices.last;
    }
  }

  String _networkStorageName() => network.network == FicNetwork.testnet ? 'testnet' : 'mainnet';

  Future<DerivedKey> ensureKey(int index) async {
    final cached = _keys[index];
    if (cached != null) return cached;
    if (_mnemonic == null) throw StateError('No wallet loaded');
    final key = deriveKey(mnemonic: _mnemonic!, network: network, index: index);
    _keys[index] = key;
    _addresses[index] = p2pkhAddress(hash160(key.publicKey), network);
    return key;
  }

  /// Derives the next BIP44 index, adds it to this wallet's known set, and
  /// makes it the active receive address. See activeAddress() for what
  /// "known set" means (locally tracked, not gap-limit discovery).
  Future<String> generateNewAddress() async {
    final next = (_addressIndices.isEmpty ? -1 : _addressIndices.reduce((a, b) => a > b ? a : b)) + 1;
    _addressIndices = [..._addressIndices, next];
    await _storage.saveAddressIndices(_networkStorageName(), _addressIndices);
    await ensureKey(next);
    activeIndex = next;
    notifyListeners();
    return _addresses[next]!;
  }

  void setActiveIndex(int index) {
    if (!_addressIndices.contains(index)) return;
    activeIndex = index;
    notifyListeners();
  }

  Future<void> stakingLogin(String email, String password) async {
    final token = await _gateway.login(email, password);
    _stakeToken = token;
    await _storage.saveStakeToken(token);
    notifyListeners();
  }

  Future<void> stakingSignup({
    required String email,
    required String password,
    required String fullName,
    required String dateOfBirth,
    required String idType,
    required String idNumber,
    String? referralCode,
  }) async {
    final token = await _gateway.signup(
      email: email,
      password: password,
      fullName: fullName,
      dateOfBirth: dateOfBirth,
      idType: idType,
      idNumber: idNumber,
      referralCode: referralCode,
    );
    _stakeToken = token;
    await _storage.saveStakeToken(token);
    notifyListeners();
  }

  /// Signs out of the staking service's gateway account only -- does not
  /// touch the on-chain wallet/mnemonic.
  Future<void> stakingLogout() async {
    _stakeToken = null;
    await _storage.clearStakeToken();
    notifyListeners();
  }

  Future<Map<String, dynamic>> fetchStakingStatus() {
    final token = _stakeToken;
    if (token == null) throw StateError('Not logged in to staking');
    return _gateway.stakingStatus(token);
  }

  Future<Map<String, dynamic>> stakingDeposit(int amountSatoshis) {
    final token = _stakeToken;
    if (token == null) throw StateError('Not logged in to staking');
    return _gateway.stakingDeposit(token, amountSatoshis);
  }

  Future<Map<String, dynamic>> stakingWithdraw(int amountSatoshis, String toAddress) {
    final token = _stakeToken;
    if (token == null) throw StateError('Not logged in to staking');
    return _gateway.stakingWithdraw(token, amountSatoshis, toAddress);
  }

  Future<Map<String, dynamic>> fetchReferralStatus() {
    final token = _stakeToken;
    if (token == null) throw StateError('Not logged in to staking');
    return _gateway.referralStatus(token);
  }

  Future<Map<String, dynamic>> fetchReferralHistory() {
    final token = _stakeToken;
    if (token == null) throw StateError('Not logged in to staking');
    return _gateway.referralHistory(token);
  }

  Future<Map<String, dynamic>> referralWithdraw(String toAddress) {
    final token = _stakeToken;
    if (token == null) throw StateError('Not logged in to staking');
    return _gateway.referralWithdraw(token, toAddress);
  }

  Future<String> createNewWallet() async {
    final mnemonic = generateMnemonic();
    await _storage.saveMnemonic(mnemonic);
    _mnemonic = mnemonic;
    _addressIndices = [0];
    activeIndex = 0;
    _keys.clear();
    _addresses.clear();
    await _storage.saveAddressIndices(_networkStorageName(), _addressIndices);
    await ensureKey(0);
    notifyListeners();
    return mnemonic;
  }

  Future<void> restoreWallet(String mnemonic) async {
    if (!isValidMnemonic(mnemonic)) {
      throw ArgumentError('Invalid recovery phrase');
    }
    await _storage.saveMnemonic(mnemonic);
    _mnemonic = mnemonic;
    _addressIndices = [0];
    activeIndex = 0;
    _keys.clear();
    _addresses.clear();
    await _storage.saveAddressIndices(_networkStorageName(), _addressIndices);
    await ensureKey(0);
    notifyListeners();
  }

  Future<void> switchNetwork(FicNetwork n) async {
    network = NetworkConfig.forNetwork(n);
    _gateway = GatewayApi(network);
    await _storage.saveActiveNetwork(n == FicNetwork.testnet ? 'testnet' : 'mainnet');
    _keys.clear();
    _addresses.clear();
    activeIndex = 0;
    if (_mnemonic != null) await _deriveAllKnownAddresses();
    notifyListeners();
  }

  /// The wallet's current active receive address. Not necessarily index 0
  /// -- see [generateNewAddress] and the note there on what "known set"
  /// means for this wallet (locally tracked generation, not full BIP44
  /// gap-limit discovery: a phrase restored on a different device starts
  /// back at index 0 and won't find addresses generated elsewhere).
  String activeAddress() {
    final cached = _addresses[activeIndex];
    if (cached != null) return cached;
    final key = _requireKey();
    return p2pkhAddress(hash160(key.publicKey), network);
  }

  String addressAt(int index) => _addresses[index] ?? (throw StateError('Address $index not derived yet'));

  /// The hash160 of the active key -- computed locally rather than trusted
  /// from the gateway response: the UTXO endpoint doesn't return a
  /// pubkey_hash field at all (it only returns txid/vout/value/height/
  /// confirmations -- see CAC's vps-gateway/app.py's address_utxos
  /// handler, whose contract ../docs/mobile-api.md carries over).
  Uint8List activePubkeyHash() {
    final key = _requireKey();
    return hash160(key.publicKey);
  }

  DerivedKey _requireKey() {
    final cached = _keys[activeIndex];
    if (cached != null) return cached;
    if (_mnemonic == null) {
      throw StateError('No wallet loaded');
    }
    return deriveKey(mnemonic: _mnemonic!, network: network, index: activeIndex);
  }

  GatewayApi get gateway => _gateway;

  /// Balance combined across every address this wallet has generated on
  /// this device (see [generateNewAddress]), in the same {confirmed,
  /// unconfirmed} shape a single-address balance call returns so
  /// Balance.fromJson doesn't need to change.
  Future<Map<String, dynamic>> fetchBalance() async {
    var confirmed = BigInt.zero;
    var unconfirmed = BigInt.zero;
    for (final idx in _addressIndices) {
      final json = await _gateway.balance(_addresses[idx]!);
      confirmed += BigInt.parse(json['confirmed'] as String);
      unconfirmed += BigInt.parse(json['unconfirmed'] as String);
    }
    return {'confirmed': confirmed.toString(), 'unconfirmed': unconfirmed.toString()};
  }

  /// Transaction history combined across every known address, deduped by
  /// txid, most recent/pending first.
  Future<Map<String, dynamic>> fetchHistory() async {
    final seen = <String>{};
    final all = <Map<String, dynamic>>[];
    for (final idx in _addressIndices) {
      final json = await _gateway.history(_addresses[idx]!);
      final list = json['transactions'] as List<dynamic>? ?? const [];
      for (final t in list) {
        final m = t as Map<String, dynamic>;
        final txid = m['txid'] as String;
        if (seen.add(txid)) all.add(m);
      }
    }
    all.sort((a, b) {
      final ha = (a['height'] as int?) ?? 0;
      final hb = (b['height'] as int?) ?? 0;
      if (ha <= 0 && hb <= 0) return 0;
      if (ha <= 0) return -1; // pending sorts first
      if (hb <= 0) return 1;
      return hb.compareTo(ha);
    });
    return {'transactions': all};
  }

  /// Compares the current combined transaction list against what was
  /// seen the last time this was called, returns how many are new, and
  /// updates the persisted "seen" set. Returns 0 (and just seeds the
  /// set) the very first time it's ever called for this wallet, since
  /// pre-existing transactions aren't "new".
  ///
  /// Deliberately *not* a timer/poll -- only ever called from an
  /// explicit user action (opening Home/History, pull-to-refresh). The
  /// web wallet's equivalent polls every 30s while its Home/History
  /// screen is the visible browser tab, which is fine there (a
  /// foreground JS interval in a tab has no bearing on app-store
  /// background-execution policy) but would not be fine here --
  /// docs/store-compliance.md states flatly that this Flutter project
  /// has no scheduled/periodic tasks of any kind, which is a real
  /// constraint from Apple/Google's virtual-currency-app review
  /// guidelines, not just a style preference. So mobile trades "live
  /// while the screen happens to be open" for "freshly checked every
  /// time you look" -- said explicitly here rather than silently
  /// shipping a narrower version of the web feature.
  Future<int> checkForNewTransactions() async {
    final json = await fetchHistory();
    final currentTxids = (json['transactions'] as List<dynamic>? ?? const [])
        .map((e) => (e as Map<String, dynamic>)['txid'] as String)
        .toSet();
    final seen = (await _storage.readSeenTxids()).toSet();
    await _storage.saveSeenTxids(currentTxids.toList());
    if (seen.isEmpty) return 0;
    return currentTxids.difference(seen).length;
  }

  /// Fetches UTXOs across every known address, each tagged with the
  /// signing key it actually belongs to, ready to hand straight to
  /// sendTransaction. Reverses the gateway's display-order txid hex to
  /// the internal/wire byte order buildAndSignTransaction needs -- Core's
  /// listunspent (what the gateway's UTXO endpoint is meant to pass
  /// through, per ../docs/mobile-api.md) returns txid in the conventional
  /// display order, which is byte-reversed from how it belongs in a
  /// transaction's prevTxid field.
  Future<List<tx.Utxo>> gatherAllUtxos() async {
    final result = <tx.Utxo>[];
    for (final idx in _addressIndices) {
      final key = await ensureKey(idx);
      final pubkeyHash = hash160(key.publicKey);
      final resp = await _gateway.utxos(_addresses[idx]!);
      final list = resp['utxos'] as List<dynamic>? ?? const [];
      for (final u in list) {
        final m = u as Map<String, dynamic>;
        result.add(tx.Utxo(
          txid: _hexToBytesReversed(m['txid'] as String),
          vout: m['vout'] as int,
          valueSatoshis: int.parse(m['value'].toString()),
          pubkeyHash: pubkeyHash,
          privateKey: key.privateKey,
          publicKeyCompressed: key.publicKey,
        ));
      }
    }
    return result;
  }

  Uint8List _hexToBytesReversed(String hex) {
    final bytes = Uint8List(hex.length ~/ 2);
    for (var i = 0; i < bytes.length; i++) {
      bytes[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
    }
    return Uint8List.fromList(bytes.reversed.toList());
  }

  /// Builds, signs, and broadcasts a send to one or more recipients in a
  /// single transaction (a "batch send" -- one shared fee/change output
  /// instead of one transaction per recipient). [utxos] should come from
  /// [gatherAllUtxos] (already tagged with each input's own signing key)
  /// -- this method does not itself query anything beyond broadcasting
  /// the final signed transaction. Change goes to the current active
  /// address.
  Future<String> sendTransaction({
    required List<tx.Utxo> utxos,
    required List<SendRecipient> recipients,
    required int feeSatoshis,
  }) async {
    if (recipients.isEmpty) {
      throw ArgumentError('No recipients specified');
    }
    final changeKey = await ensureKey(activeIndex);

    final destOutputs = <tx.TxOutputSpec>[];
    var amountTotal = 0;
    for (final r in recipients) {
      final decoded = decodeAddress(r.address, network);
      final Uint8List outScript;
      switch (decoded.type) {
        case AddressType.p2pkh:
          outScript = tx.p2pkhScriptPubKey(decoded.hash);
        case AddressType.p2sh:
          outScript = tx.p2shScriptPubKey(decoded.hash);
        case AddressType.p2wpkh:
          outScript = tx.p2wpkhScriptPubKey(decoded.hash);
      }
      destOutputs.add(tx.TxOutputSpec(outScript, r.amountSatoshis));
      amountTotal += r.amountSatoshis;
    }

    final totalIn = utxos.fold<int>(0, (sum, u) => sum + u.valueSatoshis);
    final change = totalIn - amountTotal - feeSatoshis;
    if (change < 0) {
      throw ArgumentError('Insufficient funds: have $totalIn, need ${amountTotal + feeSatoshis}');
    }

    final changeScript = tx.p2pkhScriptPubKey(hash160(changeKey.publicKey));
    final outputs = <tx.TxOutputSpec>[
      ...destOutputs,
      if (change > 0) tx.TxOutputSpec(changeScript, change),
    ];

    final rawTx = tx.buildAndSignTransaction(inputs: utxos, outputs: outputs);

    final hex = rawTx.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    final txid = await _gateway.broadcast(hex);

    final record = tx.SentTxRecord(
      inputs: [
        for (final u in utxos)
          tx.SentTxInput(
            txidHex: _bytesToHexReversed(u.txid),
            vout: u.vout,
            valueSatoshis: u.valueSatoshis,
            derivationIndex: _indexForPubkeyHash(u.pubkeyHash),
          ),
      ],
      outputs: [
        for (final o in destOutputs)
          tx.SentTxOutput(scriptPubKeyHex: _bytesToHex(o.scriptPubKey), valueSatoshis: o.valueSatoshis),
        if (change > 0)
          tx.SentTxOutput(scriptPubKeyHex: _bytesToHex(changeScript), valueSatoshis: change, isChange: true),
      ],
      feeSatoshis: feeSatoshis,
    );
    final log = await _storage.readSentTxLog();
    log[txid] = record.toJson();
    await _storage.saveSentTxLog(log);

    return txid;
  }

  String _bytesToHex(Uint8List b) => b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
  String _bytesToHexReversed(Uint8List b) => _bytesToHex(Uint8List.fromList(b.reversed.toList()));

  /// The derivation index whose key hashes to [pubkeyHash] -- every UTXO
  /// this wallet spends belongs to a known index (see gatherAllUtxos),
  /// so this should always find a match for anything sendTransaction was
  /// actually given.
  int _indexForPubkeyHash(Uint8List pubkeyHash) {
    for (final idx in _addressIndices) {
      final key = _keys[idx];
      if (key != null && _bytesEqual(hash160(key.publicKey), pubkeyHash)) return idx;
    }
    throw StateError('No known address for this UTXO\'s pubkey hash');
  }

  bool _bytesEqual(Uint8List a, Uint8List b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  /// Whether a local sent-tx record exists for [txid] -- i.e. whether
  /// "bump fee" is even possible here (see bumpFee()).
  Future<bool> hasSentTxRecord(String txid) async {
    final log = await _storage.readSentTxLog();
    return log.containsKey(txid);
  }

  /// Rebuilds and rebroadcasts [txid] (a transaction this wallet itself
  /// sent, per the local log) with a higher fee taken out of its own
  /// change output. Throws with a clear, specific reason rather than
  /// guessing at a fallback for any case this can't handle -- the
  /// actual rebuild/reduce-change math lives in transaction.dart's
  /// buildBumpFeeTransaction (pure, independently tested), this just
  /// supplies the fee target and re-derived keys and handles the
  /// network calls.
  Future<String> bumpFee(String txid) async {
    final log = await _storage.readSentTxLog();
    final recordJson = log[txid];
    if (recordJson == null) {
      throw StateError(
          "No local record of this transaction -- it was either sent from a different device/install, or before this feature existed. Can't bump its fee here.");
    }
    final record = tx.SentTxRecord.fromJson((recordJson as Map).cast<String, dynamic>());

    final feeResp = await _gateway.feeEstimate();
    final feeRate = int.tryParse(feeResp['fee_rate_sat_per_vbyte']?.toString() ?? '') ?? 1;
    final estimatedVsize = 10 + record.inputs.length * 148 + record.outputs.length * 34;
    final rateBasedFee = (feeRate * estimatedVsize + 999) ~/ 1000;
    // Must be a *meaningfully* higher fee, not just technically higher
    // (BIP125 rule 4 requires paying for the replacement's own
    // bandwidth too) -- take whichever is larger of "fresh rate
    // estimate" and "50% more than before".
    final newFeeSatoshis = [rateBasedFee, (record.feeSatoshis * 3) ~/ 2].reduce((a, b) => a > b ? a : b);

    final inputPrivateKeys = <Uint8List>[];
    final inputPublicKeys = <Uint8List>[];
    for (final inp in record.inputs) {
      final key = await ensureKey(inp.derivationIndex);
      inputPrivateKeys.add(key.privateKey);
      inputPublicKeys.add(key.publicKey);
    }

    final result = tx.buildBumpFeeTransaction(
      record: record,
      newFeeSatoshis: newFeeSatoshis,
      inputPrivateKeys: inputPrivateKeys,
      inputPublicKeys: inputPublicKeys,
    );
    final hex = result.rawTx.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    final newTxid = await _gateway.broadcast(hex);

    final log2 = await _storage.readSentTxLog();
    log2.remove(txid);
    log2[newTxid] = tx.SentTxRecord(inputs: record.inputs, outputs: result.newOutputs, feeSatoshis: newFeeSatoshis).toJson();
    await _storage.saveSentTxLog(log2);

    return newTxid;
  }

  /// Signs an air-gapped offline-signing request (see
  /// crypto/offline_signing.dart) with this wallet's own seed. Meant to
  /// be run only on a device kept offline -- see CAC's
  /// docs/upstream/cac-PARAMETERS.md section 32, which this design
  /// carries over unchanged. Does not broadcast; the caller (UI) hands
  /// the result back to the online/watch-only device however it likes
  /// (QR, text).
  Future<Uint8List> signOfflineSignRequest(offline.OfflineSignRequest request) async {
    if (_mnemonic == null) throw StateError('No wallet loaded');
    return offline.signOfflineTransaction(request: request, mnemonic: _mnemonic!, network: network);
  }

  /// This wallet's multisig identity key, independent of whichever
  /// address is "active" for receiving -- a cosigner set needs a stable
  /// key, not one that changes every time the user taps "New address".
  Future<DerivedKey> multisigKey() => ensureKey(0);

  Future<List<Map<String, String>>> loadAddressBook() => _storage.readAddressBook();
  Future<void> saveAddressBook(List<Map<String, String>> entries) => _storage.saveAddressBook(entries);

  Future<List<Map<String, String>>> loadWatchList() => _storage.readWatchList();
  Future<void> saveWatchList(List<Map<String, String>> entries) => _storage.saveWatchList(entries);

  /// This wallet's account xpub, for someone else (or this wallet
  /// restored elsewhere) to watch its addresses' balances without ever
  /// seeing a private key. Derived on demand from the in-memory
  /// mnemonic -- never cached, same as every other key derivation in
  /// this service.
  String exportAccountXpub() {
    if (_mnemonic == null) throw StateError('No wallet loaded');
    return xpub.deriveAccountXpub(mnemonic: _mnemonic!, network: network);
  }

  /// Wipes the stored mnemonic. Irreversible -- the caller (UI layer)
  /// must have already confirmed this with the user via an explicit,
  /// unambiguous confirmation step before calling this.
  Future<void> wipeWallet() async {
    await _storage.wipeWallet();
    _mnemonic = null;
    _stakeToken = null;
    _addressIndices = [0];
    activeIndex = 0;
    _keys.clear();
    _addresses.clear();
    notifyListeners();
  }
}
