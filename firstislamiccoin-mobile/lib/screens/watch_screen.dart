/// Monitor an arbitrary address's balance without holding its keys --
/// pure read-only utility, no send capability, separate from this
/// wallet's own derived addresses and from the address book (which is
/// for send-flow reuse, not monitoring).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../crypto/xpub.dart' as xpub;
import '../models/wallet_models.dart';
import '../services/wallet_service.dart';

class WatchScreen extends StatefulWidget {
  const WatchScreen({super.key});

  @override
  State<WatchScreen> createState() => _WatchScreenState();
}

class _WatchScreenState extends State<WatchScreen> {
  List<Map<String, String>> _entries = [];
  final Map<int, String> _balances = {};
  final _labelController = TextEditingController();
  final _addressController = TextEditingController();

  String? _myXpub;
  final _xpubLabelController = TextEditingController();
  final _xpubInputController = TextEditingController();
  final _xpubCountController = TextEditingController(text: '5');
  String? _xpubError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final wallet = context.read<WalletService>();
    final entries = await wallet.loadWatchList();
    if (!mounted) return;
    setState(() => _entries = entries);
    // Sequential, not fire-and-forget -- the gateway's balance lookup
    // runs a scantxoutset RPC, which the node only allows one of at a
    // time. Firing these concurrently made the loser of the race fail
    // with "Scan already in progress" and show a false "Could not
    // fetch balance" for an address that was actually fine.
    for (var i = 0; i < entries.length; i++) {
      await _fetchBalance(i, entries[i]['address']!);
    }
  }

  Future<void> _fetchBalance(int index, String address) async {
    try {
      final wallet = context.read<WalletService>();
      final json = await wallet.gateway.balance(address);
      final balance = Balance.fromJson(json);
      if (mounted) setState(() => _balances[index] = '${formatFic(balance.total)} FIC');
    } catch (e) {
      if (mounted) setState(() => _balances[index] = 'Could not fetch balance');
    }
  }

  Future<void> _add() async {
    final label = _labelController.text.trim();
    final address = _addressController.text.trim();
    if (label.isEmpty || address.isEmpty) return;
    final wallet = context.read<WalletService>();
    final entries = [..._entries, {'label': label, 'address': address}];
    await wallet.saveWatchList(entries);
    _labelController.clear();
    _addressController.clear();
    await _load();
  }

  Future<void> _remove(int index) async {
    final wallet = context.read<WalletService>();
    final entries = [..._entries]..removeAt(index);
    await wallet.saveWatchList(entries);
    await _load();
  }

  Future<void> _viewOnExplorer(String address) async {
    final uri = Uri.parse('https://explorer.firstislamiccoin.com/#/address/$address');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  void dispose() {
    _labelController.dispose();
    _addressController.dispose();
    _xpubLabelController.dispose();
    _xpubInputController.dispose();
    _xpubCountController.dispose();
    super.dispose();
  }

  void _toggleShowXpub(WalletService wallet) {
    if (_myXpub != null) {
      setState(() => _myXpub = null);
      return;
    }
    setState(() => _myXpub = wallet.exportAccountXpub());
  }

  Future<void> _addFromXpub(WalletService wallet) async {
    setState(() => _xpubError = null);
    final label = _xpubLabelController.text.trim();
    final xpubStr = _xpubInputController.text.trim();
    final count = int.tryParse(_xpubCountController.text.trim()) ?? 0;
    if (label.isEmpty || xpubStr.isEmpty) {
      setState(() => _xpubError = 'Enter a label and an xpub.');
      return;
    }
    if (count < 1 || count > 50) {
      setState(() => _xpubError = 'Choose between 1 and 50 addresses.');
      return;
    }
    try {
      final groupId = xpubStr.length >= 8 ? xpubStr.substring(xpubStr.length - 8) : xpubStr;
      final newEntries = [
        for (var i = 0; i < count; i++)
          {
            'label': '$label #$i',
            'address': xpub.deriveXpubAddress(xpub: xpubStr, network: wallet.network, index: i),
            'xpubGroup': groupId,
          },
      ];
      final entries = [..._entries, ...newEntries];
      await wallet.saveWatchList(entries);
      _xpubLabelController.clear();
      _xpubInputController.clear();
      await _load();
    } catch (e) {
      setState(() => _xpubError = 'Could not derive addresses from this xpub: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    final wallet = context.watch<WalletService>();
    return Scaffold(
      appBar: AppBar(title: const Text('Watch')),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Text(
            "Add any FirstIslamicCoin address to monitor its balance -- no keys "
            "involved, this can't spend anything. Useful for keeping an eye "
            "on an address that isn't part of this wallet.",
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 16),
          TextField(controller: _labelController, decoration: const InputDecoration(labelText: 'Label', border: OutlineInputBorder())),
          const SizedBox(height: 8),
          TextField(
            controller: _addressController,
            decoration: const InputDecoration(labelText: 'Address', border: OutlineInputBorder()),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
          ),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _add, child: const Text('Add address')),
          const Divider(height: 32),
          const Text('Your account xpub', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          const Text(
            "Share this so someone else -- or this wallet restored on "
            "another device, without its private key -- can watch your "
            "addresses' balances. Anyone with it can see every address "
            "this wallet generates and how much it's received, so don't "
            "share it publicly.",
            style: TextStyle(color: Colors.grey, fontSize: 12),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: () => _toggleShowXpub(wallet),
            child: Text(_myXpub == null ? 'Show my xpub' : 'Hide'),
          ),
          if (_myXpub != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: SelectableText(_myXpub!, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
            ),
          const Divider(height: 32),
          const Text('Watch from an xpub', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          const Text(
            'Add several addresses at once from an account xpub, instead '
            'of one at a time. Derives a fixed number of addresses you '
            'choose, not a full gap-limit scan.',
            style: TextStyle(color: Colors.grey, fontSize: 12),
          ),
          const SizedBox(height: 8),
          TextField(controller: _xpubLabelController, decoration: const InputDecoration(labelText: 'Label', border: OutlineInputBorder())),
          const SizedBox(height: 8),
          TextField(
            controller: _xpubInputController,
            maxLines: 2,
            decoration: const InputDecoration(labelText: 'xpub', border: OutlineInputBorder()),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _xpubCountController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: 'How many addresses', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: () => _addFromXpub(wallet), child: const Text('Add from xpub')),
          if (_xpubError != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(_xpubError!, style: const TextStyle(color: Colors.red)),
            ),
          const SizedBox(height: 24),
          if (_entries.isEmpty) const Text('No watched addresses yet.', style: TextStyle(color: Colors.grey)),
          for (var i = 0; i < _entries.length; i++)
            Card(
              child: ListTile(
                title: Text(_entries[i]['label'] ?? ''),
                subtitle: Text(
                  '${_entries[i]['address']}\n${_balances[i] ?? 'Loading balance...'}',
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                ),
                isThreeLine: true,
                trailing: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.open_in_new),
                      tooltip: 'Explorer',
                      onPressed: () => _viewOnExplorer(_entries[i]['address']!),
                    ),
                    IconButton(
                      icon: const Icon(Icons.delete_outline),
                      tooltip: 'Remove',
                      onPressed: () => _remove(i),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
