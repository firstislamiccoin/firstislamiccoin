/// Full detail for a single transaction (status, confirmations,
/// coinstake/reward if applicable, inputs, outputs), fetched from the
/// gateway's /tx/<txid> endpoint. Opened by tapping a row in
/// HistoryScreen.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/wallet_models.dart';
import '../services/wallet_service.dart';

class TxDetailScreen extends StatefulWidget {
  final String txid;
  const TxDetailScreen({super.key, required this.txid});

  @override
  State<TxDetailScreen> createState() => _TxDetailScreenState();
}

class _TxDetailScreenState extends State<TxDetailScreen> {
  Map<String, dynamic>? _raw;
  TxDetail? _detail;
  String? _error;

  bool _canBumpFee = false;
  bool _bumping = false;
  String? _bumpError;
  String? _bumpSuccess;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final wallet = context.read<WalletService>();
      final json = await wallet.gateway.transaction(widget.txid);
      final detail = TxDetail.fromJson(json);
      final canBump = detail.isPending && await wallet.hasSentTxRecord(widget.txid);
      setState(() {
        _raw = json;
        _detail = detail;
        _canBumpFee = canBump;
      });
    } catch (e) {
      setState(() => _error = 'Could not load transaction: $e');
    }
  }

  Future<void> _bumpFee() async {
    setState(() {
      _bumping = true;
      _bumpError = null;
      _bumpSuccess = null;
    });
    try {
      final wallet = context.read<WalletService>();
      final newTxid = await wallet.bumpFee(widget.txid);
      setState(() {
        _bumpSuccess = 'Rebroadcast with a higher fee: $newTxid';
        _canBumpFee = false;
      });
    } catch (e) {
      setState(() => _bumpError = e.toString());
    } finally {
      if (mounted) setState(() => _bumping = false);
    }
  }

  Future<void> _viewOnExplorer() async {
    final uri = Uri.parse('https://explorer.firstislamiccoin.com/#/tx/${widget.txid}');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Transaction'),
        actions: [
          IconButton(icon: const Icon(Icons.open_in_new), tooltip: 'View on explorer', onPressed: _viewOnExplorer),
        ],
      ),
      body: _error != null
          ? Padding(
              padding: const EdgeInsets.all(24),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            )
          : _raw == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _kv('Txid', _detail!.txid),
                    _kv(
                      'Status',
                      !_detail!.isPending
                          ? 'Confirmed, height ${_detail!.height} (${_detail!.confirmations} confirmations)'
                          : 'Pending',
                    ),
                    if (_detail!.isCoinstake && _detail!.rewardSatoshis != null) ...[
                      _kv('Type', 'Staking reward (coinstake)'),
                      _kv('Reward', '${formatFic(_detail!.rewardSatoshis!)} FIC'),
                    ],
                    for (final vin in (_raw!['vin'] as List<dynamic>? ?? const []))
                      _kv(
                        'Input',
                        (vin as Map)['coinbase'] != null
                            ? 'coinbase'
                            : '${(vin['txid'] as String).substring(0, 16)}...:${vin['vout']}',
                      ),
                    for (final vout in (_raw!['vout'] as List<dynamic>? ?? const []))
                      _kv('Output', _formatVout(vout as Map)),
                    if (_canBumpFee) ...[
                      const SizedBox(height: 16),
                      OutlinedButton(
                        onPressed: _bumping ? null : _bumpFee,
                        child: _bumping
                            ? const SizedBox(
                                height: 16, width: 16,
                                child: CircularProgressIndicator(strokeWidth: 2))
                            : const Text('Bump fee'),
                      ),
                    ],
                    if (_bumpSuccess != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(_bumpSuccess!, style: const TextStyle(color: Colors.green)),
                      ),
                    if (_bumpError != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(_bumpError!, style: const TextStyle(color: Colors.red)),
                      ),
                  ],
                ),
    );
  }

  String _formatVout(Map vout) {
    final scriptPubKey = vout['scriptPubKey'] as Map? ?? const {};
    final address = scriptPubKey['address'] ??
        (scriptPubKey['addresses'] is List && (scriptPubKey['addresses'] as List).isNotEmpty
            ? (scriptPubKey['addresses'] as List).first
            : '(non-standard output)');
    return '$address: ${vout['value']} FIC';
  }

  Widget _kv(String key, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 70, child: Text(key, style: const TextStyle(color: Colors.grey, fontSize: 12))),
            Expanded(child: SelectableText(value, style: const TextStyle(fontFamily: 'monospace', fontSize: 12))),
          ],
        ),
      );
}
