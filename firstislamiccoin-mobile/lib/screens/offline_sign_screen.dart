/// The "offline" (seed-holding) side of air-gapped sending: intended
/// for use only on a device kept off the network. Scan or paste a
/// signing request built by another device's Offline Send screen,
/// sign it with this device's own seed, and show the result to hand
/// back -- this screen never broadcasts anything itself. See
/// crypto/offline_signing.dart and PARAMETERS.md section 32.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../crypto/offline_signing.dart' as offline;
import '../services/wallet_service.dart';
import 'qr_scan_screen.dart';

const _qrMaxChars = 1500;

class OfflineSignScreen extends StatefulWidget {
  const OfflineSignScreen({super.key});

  @override
  State<OfflineSignScreen> createState() => _OfflineSignScreenState();
}

class _OfflineSignScreenState extends State<OfflineSignScreen> {
  final _requestJsonController = TextEditingController();
  String? _error;
  String? _signedHex;
  bool _signing = false;

  @override
  void dispose() {
    _requestJsonController.dispose();
    super.dispose();
  }

  Future<void> _scanRequest() async {
    final result = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScanScreen(title: 'Scan request')),
    );
    if (result != null) {
      setState(() {
        _requestJsonController.text = result;
        _signedHex = null;
        _error = null;
      });
    }
  }

  Future<void> _sign() async {
    setState(() {
      _signing = true;
      _error = null;
      _signedHex = null;
    });
    try {
      final wallet = context.read<WalletService>();
      final json = jsonDecode(_requestJsonController.text.trim()) as Map<String, dynamic>;
      final request = offline.OfflineSignRequest.fromJson(json);
      final rawTx = await wallet.signOfflineSignRequest(request);
      final hex = rawTx.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
      setState(() => _signedHex = hex);
    } catch (e) {
      setState(() => _error = 'Could not sign: $e');
    } finally {
      if (mounted) setState(() => _signing = false);
    }
  }

  Future<void> _showSignedQr() async {
    final hex = _signedHex;
    if (hex == null) return;
    if (hex.length > _qrMaxChars) {
      setState(() => _error =
          'This signed transaction is too large for a reliable QR code (${hex.length} characters). Copy the text directly instead.');
      return;
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Scan this on the online device'),
        content: SizedBox(
          width: 260,
          height: 260,
          child: Container(
            color: Colors.white,
            padding: const EdgeInsets.all(12),
            child: QrImageView(data: hex, version: QrVersions.auto),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Close'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Sign Offline Transaction')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Text(
            "Only use this on a device that stays off the network -- "
            "airplane mode, no Wi-Fi. It signs with this device's own "
            "seed and shows the result for you to hand back to the "
            "online device (QR or text); it never broadcasts anything "
            "itself.",
            style: TextStyle(color: Colors.orange, fontWeight: FontWeight.w600, fontSize: 12),
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _requestJsonController,
            maxLines: 8,
            style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
            decoration: const InputDecoration(labelText: 'Request JSON (paste or scan)', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _scanRequest, child: const Text('Scan QR')),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _signing ? null : _sign,
            child: Text(_signing ? 'Signing...' : 'Sign'),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
          if (_signedHex != null) ...[
            const Divider(height: 40),
            Text('Signed transaction -- hand this back to the online device',
                style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            SelectableText(_signedHex!, style: const TextStyle(fontFamily: 'monospace', fontSize: 11)),
            const SizedBox(height: 8),
            OutlinedButton(onPressed: _showSignedQr, child: const Text('Show as QR')),
          ],
        ],
      ),
    );
  }
}
