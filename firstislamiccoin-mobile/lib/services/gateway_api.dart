/// HTTP client for the FIC staking-service gateway (Phase 6 -- not built
/// yet, see docs/repo-map.md's "Two mapping caveats" and
/// ../../docs/CHANGELOG-FIC.md). Matches ../docs/mobile-api.md, this
/// wallet's own copy of the REST contract CAC's vps-gateway/web-wallet
/// pair established, kept unchanged apart from renaming. Kept as a
/// single, narrow client class so it's the only place in the app that
/// does any networking beyond broadcasting a transaction.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/network_config.dart';

class GatewayException implements Exception {
  final String code;
  final String message;
  GatewayException(this.code, this.message);
  @override
  String toString() => 'GatewayException($code): $message';
}

class GatewayApi {
  final NetworkConfig network;
  final http.Client _client;

  GatewayApi(this.network, {http.Client? client}) : _client = client ?? http.Client();

  Uri _uri(String path) => Uri.parse('${network.gatewayBaseUrl}$path');

  Map<String, String> _authHeaders(String? token) =>
      token == null ? const {} : {'Authorization': 'Bearer $token'};

  Future<Map<String, dynamic>> _get(String path, {String? auth}) async {
    final resp = await _client.get(_uri(path), headers: _authHeaders(auth));
    return _decode(resp);
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body, {String? auth}) async {
    final resp = await _client.post(
      _uri(path),
      headers: {'Content-Type': 'application/json', ..._authHeaders(auth)},
      body: jsonEncode(body),
    );
    return _decode(resp);
  }

  Map<String, dynamic> _decode(http.Response resp) {
    final decoded = jsonDecode(resp.body) as Map<String, dynamic>;
    if (resp.statusCode >= 400) {
      final error = decoded['error'] as Map<String, dynamic>?;
      throw GatewayException(
        error?['code'] as String? ?? 'unknown-error',
        error?['message'] as String? ?? 'Request failed (${resp.statusCode})',
      );
    }
    return decoded;
  }

  // -- §1 network status --
  Future<Map<String, dynamic>> networkStatus() => _get('/network/status');

  // -- §2 balance --
  Future<Map<String, dynamic>> balance(String address) =>
      _get('/address/$address/balance');

  // -- §3 UTXOs --
  Future<Map<String, dynamic>> utxos(String address) =>
      _get('/address/$address/utxos');

  // -- §4 history / tx detail / broadcast / fee estimate --
  Future<Map<String, dynamic>> history(String address, {int limit = 50}) =>
      _get('/address/$address/history?limit=$limit');

  Future<Map<String, dynamic>> transaction(String txid) => _get('/tx/$txid');

  Future<String> broadcast(String rawTxHex) async {
    final result = await _post('/tx/broadcast', {'raw_tx_hex': rawTxHex});
    return result['txid'] as String;
  }

  Future<Map<String, dynamic>> feeEstimate({int targetBlocks = 6}) =>
      _get('/fee-estimate?target_blocks=$targetBlocks');

  // -- account auth (gateway account for the custodial staking service --
  // separate from this wallet's own on-chain keys/mnemonic) --
  Future<String> login(String email, String password) async {
    final result = await _post('/auth/login', {'email': email, 'password': password});
    return result['token'] as String;
  }

  /// [dateOfBirth] must be `YYYY-MM-DD`. [idType] is `nic` or `passport`.
  /// These KYC fields are self-attested, not identity-verified -- see
  /// CAC's vps-gateway/kyc.py's module docstring, which this contract
  /// carries over unchanged (the FIC staking service itself is unbuilt).
  Future<String> signup({
    required String email,
    required String password,
    required String fullName,
    required String dateOfBirth,
    required String idType,
    required String idNumber,
    String? referralCode,
  }) async {
    final result = await _post('/auth/signup', {
      'email': email,
      'password': password,
      'full_name': fullName,
      'date_of_birth': dateOfBirth,
      'id_type': idType,
      'id_number': idNumber,
      if (referralCode != null && referralCode.isNotEmpty) 'referral_code': referralCode,
    });
    return result['token'] as String;
  }

  // -- §5 staking (custodial pool; requires an account auth token from
  // login/signup above) --
  Future<Map<String, dynamic>> stakingStatus(String authToken) =>
      _get('/staking/status', auth: authToken);

  Future<Map<String, dynamic>> stakingDeposit(String authToken, int amountSatoshis) =>
      _post('/staking/deposit', {'amount': amountSatoshis.toString()}, auth: authToken);

  Future<Map<String, dynamic>> stakingWithdraw(
    String authToken,
    int amountSatoshis,
    String toAddress,
  ) =>
      _post('/staking/withdraw', {
        'amount': amountSatoshis.toString(),
        'to_address': toAddress,
      }, auth: authToken);

  Future<Map<String, dynamic>> referralStatus(String authToken) =>
      _get('/referral/status', auth: authToken);

  Future<Map<String, dynamic>> referralHistory(String authToken) =>
      _get('/referral/history', auth: authToken);

  Future<Map<String, dynamic>> referralWithdraw(String authToken, String toAddress) =>
      _post('/referral/withdraw', {'to_address': toAddress}, auth: authToken);

  // -- native mobile push (FCM) -- no auth required, address-keyed like
  // the balance/utxo/history endpoints above rather than requiring a
  // staking-service login. See CAC's vps-gateway/app.py's
  // push_mobile_register and docs/upstream/cac-PARAMETERS.md section 34.
  Future<void> registerPushToken({
    required String address,
    required String platform,
    required String token,
  }) =>
      _post('/push/mobile/register', {'address': address, 'platform': platform, 'token': token});

  // -- FIC/USD price + price-threshold alerts. Same shape as CAC's
  // gateway.js: /price is no-auth (same convention as balance/history);
  // the alerts themselves are address+token-keyed, no-auth, same
  // convention as registerPushToken above -- delivered via that same
  // FCM token. Where this price itself would come from is an open
  // question for whoever builds the Phase 6 gateway -- FIC has no DEX
  // listing to source it from the way CAC's did (see
  // widgets/fiat_placeholder.dart).
  Future<double> currentPrice() async {
    final result = await _get('/price');
    return (result['usd_per_fic'] as num).toDouble();
  }

  Future<int> createPriceAlert({
    required String address,
    required String token,
    required String direction,
    required double thresholdUsd,
  }) async {
    final result = await _post('/price-alerts/mobile', {
      'address': address,
      'token': token,
      'direction': direction,
      'threshold_usd': thresholdUsd,
    });
    return result['id'] as int;
  }

  Future<List<Map<String, dynamic>>> listPriceAlerts({
    required String address,
    required String token,
  }) async {
    final result = await _get(
      '/price-alerts/mobile?address=$address&token=${Uri.encodeQueryComponent(token)}',
    );
    return (result['alerts'] as List).cast<Map<String, dynamic>>();
  }

  Future<void> deletePriceAlert({
    required String address,
    required String token,
    required int alertId,
  }) async {
    final resp = await _client.delete(
      _uri('/price-alerts/mobile/$alertId?address=$address&token=${Uri.encodeQueryComponent(token)}'),
    );
    _decode(resp);
  }

  void close() => _client.close();
}
