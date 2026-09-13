/// Send flow: scan or paste one or more destination addresses with an
/// amount each (a "batch send" -- one shared transaction, one shared
/// fee, instead of sending separately to each), fetch this wallet's
/// UTXOs (across every address it's generated -- see
/// WalletService.gatherAllUtxos) from the gateway, sign locally, and
/// broadcast. Signing happens entirely on-device (crypto/transaction.dart);
/// the gateway only ever sees the final signed raw transaction hex.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../crypto/transaction.dart' as tx;
import '../services/bip21.dart';
import '../services/wallet_service.dart';
import 'qr_scan_screen.dart';

/// One recipient row's editable state.
class _RecipientRow {
  final TextEditingController addressController = TextEditingController();
  final TextEditingController amountController = TextEditingController();

  void dispose() {
    addressController.dispose();
    amountController.dispose();
  }
}

class SendScreen extends StatefulWidget {
  const SendScreen({super.key});

  @override
  State<SendScreen> createState() => _SendScreenState();
}

class _SendScreenState extends State<SendScreen> {
  final List<_RecipientRow> _recipients = [_RecipientRow()];
  bool _sending = false;
  String? _error;
  String? _txid;

  // Adjustable network fee. Defaults to the gateway's own recommended
  // rate (its floor) -- can be raised, but not lowered below it: this
  // coin enforces a single fixed consensus minimum fee rate, not a real
  // congestion market (see mobile-api.md section 4), so anything lower
  // would just get the transaction rejected.
  int? _minFeeRate;
  int? _feeRateOverride;
  final _feeRateController = TextEditingController();

  int get _effectiveFeeRate => _feeRateOverride ?? _minFeeRate ?? 1;

  void _setFeeRate(int rate) {
    if (_minFeeRate == null) return;
    final ceiling = _minFeeRate! * 50;
    final clamped = rate < _minFeeRate! ? _minFeeRate! : (rate > ceiling ? ceiling : rate);
    setState(() {
      _feeRateOverride = clamped == _minFeeRate ? null : clamped;
      _feeRateController.text = clamped.toString();
    });
  }

  @override
  void initState() {
    super.initState();
    final wallet = context.read<WalletService>();
    wallet.gateway.feeEstimate().then((json) {
      final rate = int.tryParse(json['fee_rate_sat_per_vbyte']?.toString() ?? '') ?? 1;
      if (mounted) {
        setState(() {
          _minFeeRate = rate;
          _feeRateController.text = rate.toString();
        });
      }
    });
    // Rebuilds on every keystroke so the fiat estimate below stays
    // current -- setState with no controller-derived state change is
    // fine here since build() reads straight from each controller's
    // current text.
    _recipients.first.amountController.addListener(() => setState(() {}));
  }

  void _addRecipient() {
    setState(() {
      final row = _RecipientRow();
      row.amountController.addListener(() => setState(() {}));
      _recipients.add(row);
    });
  }

  void _removeRecipient(int index) {
    setState(() {
      _recipients[index].dispose();
      _recipients.removeAt(index);
    });
  }

  Future<void> _scanQr(int index) async {
    final result = await Navigator.of(context).push<String>(
      MaterialPageRoute(builder: (_) => const QrScanScreen(title: 'Scan address')),
    );
    if (result != null) {
      final parsed = parseBip21(result);
      setState(() {
        _recipients[index].addressController.text = parsed.address;
        if (parsed.amount != null) _recipients[index].amountController.text = parsed.amount.toString();
      });
    }
  }

  void _onAddressChanged(int index, String value) {
    final parsed = parseBip21(value);
    if (parsed.address != value) {
      _recipients[index].addressController.text = parsed.address;
      if (parsed.amount != null) _recipients[index].amountController.text = parsed.amount.toString();
    }
  }

  Future<void> _openAddressBook(int index) async {
    final wallet = context.read<WalletService>();
    final entries = await wallet.loadAddressBook();
    if (!mounted) return;
    final picked = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => _AddressBookSheet(
        entries: entries,
        onSave: (updated) => wallet.saveAddressBook(updated),
      ),
    );
    if (picked != null) {
      setState(() => _recipients[index].addressController.text = picked);
    }
  }

  Future<void> _send() async {
    setState(() {
      _sending = true;
      _error = null;
      _txid = null;
    });
    try {
      final wallet = context.read<WalletService>();
      final recipients = <SendRecipient>[];
      for (final r in _recipients) {
        final address = r.addressController.text.trim();
        final amountFic = double.tryParse(r.amountController.text.trim());
        if (address.isEmpty || amountFic == null || amountFic <= 0) {
          throw ArgumentError('Enter a valid address and amount for every recipient');
        }
        recipients.add(SendRecipient(address: address, amountSatoshis: (amountFic * 100000000).round()));
      }
      final amountTotalSatoshis = recipients.fold<int>(0, (sum, r) => sum + r.amountSatoshis);

      final allUtxos = await wallet.gatherAllUtxos();
      if (allUtxos.isEmpty) {
        throw StateError('No spendable funds found');
      }

      final feeJson = await wallet.gateway.feeEstimate();
      final minRate = int.tryParse(feeJson['fee_rate_sat_per_vbyte']?.toString() ?? '') ?? 1;
      _minFeeRate = minRate; // keep in sync in case it drifted since the screen loaded
      // Use the user's chosen rate only if it's still above the current
      // floor -- protects against a stale override surviving a floor
      // increase and getting rejected again.
      final feeRate = _feeRateOverride != null && _feeRateOverride! > minRate ? _feeRateOverride! : minRate;

      // Output count scales with recipient count now (N destinations +
      // 1 change), not the fixed 2 a single-recipient send always had.
      final outputCount = recipients.length + 1;
      var totalIn = 0;
      final chosen = <tx.Utxo>[];
      for (final u in allUtxos) {
        chosen.add(u);
        totalIn += u.valueSatoshis;
        final estimatedVsize = 10 + chosen.length * 148 + outputCount * 34;
        // Round up, not down -- the node's own CFeeRate::GetFee() rounds up
        // (ceil), so truncating division here computes exactly 1 satoshi
        // too little on almost every real transaction and gets rejected as
        // bad-txns-fee-not-enough.
        final feeSatoshis = (feeRate * estimatedVsize + 999) ~/ 1000;
        if (totalIn >= amountTotalSatoshis + feeSatoshis) break;
      }
      final finalVsize = 10 + chosen.length * 148 + outputCount * 34;
      final feeSatoshis = (feeRate * finalVsize + 999) ~/ 1000;
      if (totalIn < amountTotalSatoshis + feeSatoshis) {
        throw StateError('Insufficient funds: have $totalIn, need ${amountTotalSatoshis + feeSatoshis}');
      }

      final txid = await wallet.sendTransaction(
        utxos: chosen,
        recipients: recipients,
        feeSatoshis: feeSatoshis,
      );
      setState(() {
        _txid = txid;
        for (final r in _recipients.skip(1)) {
          r.dispose();
        }
        _recipients
          ..clear()
          ..add(_RecipientRow());
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  void dispose() {
    for (final r in _recipients) {
      r.dispose();
    }
    _feeRateController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Send')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          for (var i = 0; i < _recipients.length; i++) ...[
            if (i > 0) const Divider(height: 32),
            if (_recipients.length > 1)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Recipient ${i + 1}', style: Theme.of(context).textTheme.labelLarge),
                  IconButton(
                    icon: const Icon(Icons.close, size: 18),
                    tooltip: 'Remove recipient',
                    onPressed: () => _removeRecipient(i),
                  ),
                ],
              ),
            TextField(
              controller: _recipients[i].addressController,
              onChanged: (v) => _onAddressChanged(i, v),
              decoration: InputDecoration(
                labelText: 'Destination address',
                border: const OutlineInputBorder(),
                suffixIcon: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.contacts_outlined),
                      tooltip: 'Address book',
                      onPressed: () => _openAddressBook(i),
                    ),
                    IconButton(
                      icon: const Icon(Icons.qr_code_scanner),
                      tooltip: 'Scan QR',
                      onPressed: () => _scanQr(i),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _recipients[i].amountController,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Amount (FIC)',
                border: OutlineInputBorder(),
              ),
            ),
          ],
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _addRecipient,
            icon: const Icon(Icons.add),
            label: const Text('Add recipient'),
          ),
          const SizedBox(height: 16),
          if (_minFeeRate != null) ...[
            Row(
              children: [
                Text('Network fee', style: Theme.of(context).textTheme.labelLarge),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.remove_circle_outline),
                  tooltip: 'Decrease fee rate',
                  onPressed: () => _setFeeRate(_effectiveFeeRate - 10),
                ),
                SizedBox(
                  width: 64,
                  child: TextField(
                    controller: _feeRateController,
                    textAlign: TextAlign.center,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(isDense: true, border: OutlineInputBorder()),
                    onSubmitted: (v) => _setFeeRate(int.tryParse(v) ?? _minFeeRate!),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.add_circle_outline),
                  tooltip: 'Increase fee rate',
                  onPressed: () => _setFeeRate(_effectiveFeeRate + 10),
                ),
                TextButton(
                  onPressed: () => _setFeeRate(_minFeeRate!),
                  child: const Text('Reset'),
                ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                'sat/vB -- recommended: $_minFeeRate sat/vB (this coin has a '
                'single fixed network minimum, not a real congestion '
                'market, so the rate can\'t go lower)',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey),
              ),
            ),
          ],
          const SizedBox(height: 8),
          if (_error != null) Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Text(_error!, style: const TextStyle(color: Colors.red)),
          ),
          if (_txid != null) Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Text('Broadcast: $_txid',
                style: const TextStyle(color: Colors.green)),
          ),
          FilledButton(
            onPressed: _sending ? null : _send,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: _sending
                  ? const SizedBox(
                      height: 20, width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(_recipients.length > 1 ? 'Send to ${_recipients.length} recipients' : 'Send'),
            ),
          ),
        ],
      ),
    );
  }
}

class _AddressBookSheet extends StatefulWidget {
  final List<Map<String, String>> entries;
  final Future<void> Function(List<Map<String, String>>) onSave;
  const _AddressBookSheet({required this.entries, required this.onSave});

  @override
  State<_AddressBookSheet> createState() => _AddressBookSheetState();
}

class _AddressBookSheetState extends State<_AddressBookSheet> {
  late List<Map<String, String>> _entries;
  final _labelController = TextEditingController();
  final _addressController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _entries = List.of(widget.entries);
  }

  Future<void> _add() async {
    final label = _labelController.text.trim();
    final address = _addressController.text.trim();
    if (label.isEmpty || address.isEmpty) return;
    setState(() => _entries = [..._entries, {'label': label, 'address': address}]);
    await widget.onSave(_entries);
    _labelController.clear();
    _addressController.clear();
  }

  Future<void> _remove(int index) async {
    setState(() => _entries = [..._entries]..removeAt(index));
    await widget.onSave(_entries);
  }

  @override
  void dispose() {
    _labelController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16, right: 16, top: 16,
        bottom: 16 + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Address book', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (_entries.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('No saved addresses yet.'),
              )
            else
              ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 260),
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: _entries.length,
                  itemBuilder: (context, i) {
                    final e = _entries[i];
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(e['label'] ?? ''),
                      subtitle: Text(e['address'] ?? '', style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
                      onTap: () => Navigator.of(context).pop(e['address']),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete_outline),
                        onPressed: () => _remove(i),
                      ),
                    );
                  },
                ),
              ),
            const Divider(),
            TextField(
              controller: _labelController,
              decoration: const InputDecoration(labelText: 'Label'),
            ),
            TextField(
              controller: _addressController,
              decoration: const InputDecoration(labelText: 'Address'),
              style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
            ),
            const SizedBox(height: 8),
            OutlinedButton(onPressed: _add, child: const Text('Save address')),
          ],
        ),
      ),
    );
  }
}
