/// Transaction history list for the active address. One fetch on open +
/// pull-to-refresh, no polling -- refreshing also compares against what
/// was seen last time and shows a "N new" banner (see
/// WalletService.checkForNewTransactions for why this is check-on-
/// refresh rather than a timer).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

import '../models/wallet_models.dart';
import '../services/wallet_service.dart';
import 'tx_detail_screen.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<TxSummary>? _txs;
  String? _error;
  int _newTxCount = 0;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => _error = null);
    try {
      final wallet = context.read<WalletService>();
      final json = await wallet.fetchHistory();
      final list = json['transactions'] as List<dynamic>? ?? const [];
      setState(() {
        _txs = list
            .map((e) => TxSummary.fromJson(e as Map<String, dynamic>))
            .toList();
      });
      // Best-effort, and also marks everything just fetched as "seen" --
      // opening this screen is itself a natural point to clear the count.
      try {
        final newCount = await wallet.checkForNewTransactions();
        if (mounted) setState(() => _newTxCount = newCount);
      } catch (_) {}
    } catch (e) {
      setState(() => _error = 'Could not reach the network: $e');
    }
  }

  // Exports the summary fields already on screen (txid, status, height,
  // fee) -- not the full detail (inputs/outputs) for every transaction,
  // which would mean one extra gateway call per row. A reasonable scope
  // cut for what a CSV export is normally used for.
  Future<void> _exportCsv() async {
    final txs = _txs;
    if (txs == null || txs.isEmpty) return;
    final buffer = StringBuffer('txid,status,height,fee_satoshis\n');
    for (final t in txs) {
      final status = t.isPending ? 'pending' : 'confirmed';
      buffer.writeln(
          '"${t.txid}","$status","${t.height ?? ''}","${t.fee ?? ''}"');
    }
    await Share.share(buffer.toString(),
        subject: 'FirstIslamicCoin transaction history');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
        actions: [
          IconButton(
              icon: const Icon(Icons.ios_share),
              tooltip: 'Export as CSV',
              onPressed: _exportCsv),
        ],
      ),
      body: Column(
        children: [
          if (_newTxCount > 0)
            Material(
              color: Theme.of(context).colorScheme.primaryContainer,
              child: InkWell(
                onTap: () => setState(() => _newTxCount = 0),
                child: Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          _newTxCount == 1
                              ? '1 new transaction'
                              : '$_newTxCount new transactions',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close, size: 18),
                        onPressed: () => setState(() => _newTxCount = 0),
                        tooltip: 'Dismiss',
                      ),
                    ],
                  ),
                ),
              ),
            ),
          Expanded(child: _buildList(context)),
        ],
      ),
    );
  }

  Widget _buildList(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: _error != null
          ? ListView(
              children: [
                Padding(
                  padding: const EdgeInsets.all(24),
                  child:
                      Text(_error!, style: const TextStyle(color: Colors.red)),
                ),
              ],
            )
          : _txs == null
              ? const Center(child: CircularProgressIndicator())
              : _txs!.isEmpty
                  ? ListView(
                      children: const [
                        Padding(
                          padding: EdgeInsets.all(24),
                          child: Center(child: Text('No transactions yet')),
                        ),
                      ],
                    )
                  : ListView.separated(
                      itemCount: _txs!.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, i) {
                        final t = _txs![i];
                        return ListTile(
                          leading: Icon(
                            t.isPending
                                ? Icons.hourglass_empty
                                : Icons.check_circle_outline,
                          ),
                          title: Text(
                            t.txid,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontFamily: 'monospace'),
                          ),
                          subtitle: Text(
                              t.isPending ? 'Pending' : 'Height ${t.height}'),
                          trailing: t.fee != null ? Text('fee ${t.fee}') : null,
                          onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) => TxDetailScreen(txid: t.txid)),
                          ),
                        );
                      },
                    ),
    );
  }
}
