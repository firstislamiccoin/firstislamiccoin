/// The "online" (watch-only) side of air-gapped sending: paste an
/// account xpub (no seed involved), build an unsigned spend from its
/// derived addresses' UTXOs, hand the request off to an offline device
/// holding the matching seed (QR or text), then import the signed
/// result back and broadcast it. See crypto/offline_signing.dart and
/// PARAMETERS.md section 32 for the full design.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../crypto/address.dart';
import '../crypto/offline_signing.dart' as offline;
import '../crypto/transaction.dart' as tx;
import '../crypto/xpub.dart' as xpub;
import '../services/wallet_service.dart';
import 'qr_scan_screen.dart';

// Matches multisig_screen.dart's identical cutoff -- a conservative
// limit for reliable QR scanning, well under the encoder's hard limit.
const _qrMaxChars = 1500;

String _bytesToHex(List<int> b) => b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();

class OfflineSendScreen extends StatefulWidget {
  const OfflineSendScreen({super.key});

  @override
  State<OfflineSendScreen> createState() => _OfflineSendScreenState();
}

class _OfflineSendScreenState extends State<OfflineSendScreen> {
  final _xpubController = TextEditingController();
  final _countController = TextEditingController(text: '5');
  final _changeIndexController = TextEditingController(text: '0');
  final _toController = TextEditingController();
  final _amountController = TextEditingController();
  final _requestJsonController = TextEditingController();
  final _signedHexController = TextEditingController();

  bool _building = false;
  String? _buildError;

  bool _broadcasting = false;
  String? _broadcastError;
  String? _broadcastSuccess;

  @override
  void dispose() {
    _xpubController.dispose();
    _countController.dispose();
    _changeIndexController.dispose();
    _toController.dispose();
    _amountController.dispose();
    _requestJsonController.dispose();
    _signedHexController.dispose();
    super.dispose();
  }

  Future<void> _buildRequest() async {
    setState(() {
      _building = true;
      _buildError = null;
      _requestJsonController.text = '';
    });
    try {
      final wallet = context.read<WalletService>();
      final xpubStr = _xpubController.text.trim();
      final count = int.tryParse(_countController.text.trim()) ?? 0;
      final changeIndex = int.tryParse(_changeIndexController.text.trim()) ?? -1;
      final toAddress = _toController.text.trim();
      final amountFic = double.tryParse(_amountController.text.trim());
      if (xpubStr.isEmpty || count < 1 || count > 50 || changeIndex < 0 || changeIndex >= count) {
        throw ArgumentError('Enter an xpub, a valid address count, and a change index within that range.');
      }
      if (toAddress.isEmpty || amountFic == null || amountFic <= 0) {
        throw ArgumentError('Enter a destination address and amount.');
      }
      final amountSatoshis = (amountFic * 100000000).round();

      final decoded = decodeAddress(toAddress, wallet.network);
      final Uint8List outScript;
      switch (decoded.type) {
        case AddressType.p2pkh:
          outScript = tx.p2pkhScriptPubKey(decoded.hash);
        case AddressType.p2sh:
          outScript = tx.p2shScriptPubKey(decoded.hash);
        case AddressType.p2wpkh:
          outScript = tx.p2wpkhScriptPubKey(decoded.hash);
      }

      // Gather every UTXO across the first [count] derived addresses,
      // each tagged with the derivation index and pubkey hash the
      // offline signer will need -- computed from the xpub alone
      // (public-key-only BIP32 derivation), no private key involved.
      final candidates = <offline.OfflineSignInput>[];
      for (var i = 0; i < count; i++) {
        final address = xpub.deriveXpubAddress(xpub: xpubStr, network: wallet.network, index: i);
        final pubkeyHash = decodeAddress(address, wallet.network).hash;
        final resp = await wallet.gateway.utxos(address);
        final list = resp['utxos'] as List<dynamic>? ?? const [];
        for (final u in list) {
          final m = u as Map<String, dynamic>;
          candidates.add(offline.OfflineSignInput(
            txidHex: m['txid'] as String,
            vout: m['vout'] as int,
            valueSatoshis: int.parse(m['value'].toString()),
            derivationIndex: i,
            pubkeyHashHex: _bytesToHex(pubkeyHash),
          ));
        }
      }
      if (candidates.isEmpty) {
        throw StateError('No spendable funds found across the first $count derived addresses.');
      }

      final feeResp = await wallet.gateway.feeEstimate();
      final feeRate = int.tryParse(feeResp['fee_rate_sat_per_vbyte']?.toString() ?? '') ?? 1;

      var totalIn = 0;
      final chosen = <offline.OfflineSignInput>[];
      for (final c in candidates) {
        chosen.add(c);
        totalIn += c.valueSatoshis;
        final estimatedVsize = 10 + chosen.length * 148 + 2 * 34;
        final feeSatoshis = (feeRate * estimatedVsize + 999) ~/ 1000;
        if (totalIn >= amountSatoshis + feeSatoshis) break;
      }
      final finalVsize = 10 + chosen.length * 148 + 2 * 34;
      final feeSatoshis = (feeRate * finalVsize + 999) ~/ 1000;
      if (totalIn < amountSatoshis + feeSatoshis) {
        throw StateError('Insufficient funds: have $totalIn, need ${amountSatoshis + feeSatoshis}');
      }
      final change = totalIn - amountSatoshis - feeSatoshis;

      final changeAddress = xpub.deriveXpubAddress(xpub: xpubStr, network: wallet.network, index: changeIndex);
      final changeScript = tx.p2pkhScriptPubKey(decodeAddress(changeAddress, wallet.network).hash);

      final request = offline.OfflineSignRequest(
        locktime: 0,
        inputs: chosen,
        outputs: [
          offline.OfflineSignOutput(scriptPubKeyHex: _bytesToHex(outScript), valueSatoshis: amountSatoshis),
          if (change > 0) offline.OfflineSignOutput(scriptPubKeyHex: _bytesToHex(changeScript), valueSatoshis: change),
        ],
      );
      setState(() => _requestJsonController.text = const JsonEncoder.withIndent('  ').convert(request.toJson()));
    } catch (e) {
      setState(() => _buildError = e.toString());
    } finally {
      if (mounted) setState(() => _building = false);
    }
  }

  Future<void> _showRequestQr() async {
    final json = _requestJsonController.text.trim();
    if (json.isEmpty) return;
    if (json.length > _qrMaxChars) {
      setState(() => _buildError =
          'This request is too large for a reliable QR code (${json.length} characters). Share the JSON text directly instead.');
      return;
    }
    setState(() => _buildError = null);
    await _showQrDialog(json);
  }

  Future<void> _showQrDialog(String data) async {
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Scan this on the offline device'),
        content: SizedBox(
          width: 260,
          height: 260,
          child: Container(
            color: Colors.white,
            padding: const EdgeInsets.all(12),
            child: QrImageView(data: data, version: QrVersions.auto),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Close'))],
      ),
    );
  }

  Future<void> _scanSignedResult() async {
    final result = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScanScreen(title: 'Scan signed transaction')),
    );
    if (result != null) {
      setState(() => _signedHexController.text = result.trim());
    }
  }

  Future<void> _broadcast() async {
    setState(() {
      _broadcasting = true;
      _broadcastError = null;
      _broadcastSuccess = null;
    });
    try {
      final wallet = context.read<WalletService>();
      final hex = _signedHexController.text.trim();
      if (hex.isEmpty) throw ArgumentError('Paste or scan the signed transaction first.');
      final txid = await wallet.gateway.broadcast(hex);
      setState(() {
        _broadcastSuccess = 'Broadcast: $txid';
        _signedHexController.clear();
        _requestJsonController.clear();
        _toController.clear();
        _amountController.clear();
      });
    } catch (e) {
      setState(() => _broadcastError = e.toString());
    } finally {
      if (mounted) setState(() => _broadcasting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Send via Offline Signing')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Text(
            "For a wallet whose seed lives only on a separate, offline "
            "device. This screen never touches a private key -- it "
            "builds an unsigned request from an account xpub, you hand "
            "that to the offline device (QR or text) to sign, then "
            "import the signed result back here to broadcast.",
            style: TextStyle(color: Colors.grey, fontSize: 12),
          ),
          const SizedBox(height: 24),
          Text('1. Build a request', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          TextField(
            controller: _xpubController,
            maxLines: 2,
            decoration: const InputDecoration(labelText: 'Account xpub', border: OutlineInputBorder()),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _countController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Addresses to check', border: OutlineInputBorder()),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _changeIndexController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Change index', border: OutlineInputBorder()),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _toController,
            decoration: const InputDecoration(labelText: 'Destination address', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _amountController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Amount (FIC)', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: _building ? null : _buildRequest,
            child: Text(_building ? 'Building...' : 'Build request'),
          ),
          if (_buildError != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_buildError!, style: const TextStyle(color: Colors.red)),
            ),
          const Divider(height: 40),
          Text('2. Send the request to the offline device', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          TextField(
            controller: _requestJsonController,
            maxLines: 8,
            readOnly: true,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
            decoration: const InputDecoration(labelText: 'Request JSON', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _showRequestQr, child: const Text('Show as QR')),
          const Divider(height: 40),
          Text('3. Import the signed transaction and broadcast', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          TextField(
            controller: _signedHexController,
            maxLines: 4,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
            decoration: const InputDecoration(labelText: 'Signed transaction (hex)', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _scanSignedResult, child: const Text('Scan QR')),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: _broadcasting ? null : _broadcast,
            child: Text(_broadcasting ? 'Broadcasting...' : 'Broadcast'),
          ),
          if (_broadcastError != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_broadcastError!, style: const TextStyle(color: Colors.red)),
            ),
          if (_broadcastSuccess != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_broadcastSuccess!, style: const TextStyle(color: Colors.green)),
            ),
        ],
      ),
    );
  }
}
