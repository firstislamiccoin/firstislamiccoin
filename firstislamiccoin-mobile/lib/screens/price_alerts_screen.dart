/// Price-threshold alerts: get a native push notification once FIC's
/// estimated USD price crosses a level you set. No staking-service login
/// needed -- alerts are address+token-keyed, the same no-login convention
/// as the existing "notify me on incoming payment" push registration (see
/// settings_screen.dart's _PushNotificationsCard and PARAMETERS.md section
/// 34), reusing that same FCM token rather than a second registration
/// step. One-shot: the gateway's watcher marks an alert triggered the
/// first time its condition is met and never re-fires it (see
/// vps-gateway/price_alerts.py), so a fired alert simply drops out of the
/// list below instead of showing as "done".
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/firebase_config.dart';
import '../services/gateway_api.dart';
import '../services/push_service.dart';
import '../services/wallet_service.dart';

class PriceAlertsScreen extends StatefulWidget {
  const PriceAlertsScreen({super.key});

  @override
  State<PriceAlertsScreen> createState() => _PriceAlertsScreenState();
}

class _PriceAlertsScreenState extends State<PriceAlertsScreen> {
  final _pushService = PushService();
  final _thresholdController = TextEditingController();
  String _direction = 'above';

  bool _loading = true;
  bool _enabling = false;
  String? _token;
  double? _currentPrice;
  List<Map<String, dynamic>> _alerts = const [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void dispose() {
    _thresholdController.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final wallet = context.read<WalletService>();
    try {
      final price = await wallet.gateway.currentPrice();
      if (mounted) setState(() => _currentPrice = price);
    } catch (_) {
      // Non-fatal -- the form below still works without it.
    }
    final token = await _pushService.currentToken();
    if (!mounted) return;
    setState(() => _token = token);
    if (token != null) {
      try {
        final alerts = await wallet.gateway.listPriceAlerts(address: wallet.activeAddress(), token: token);
        if (mounted) setState(() => _alerts = alerts.where((a) => a['triggered_at'] == null).toList());
      } catch (e) {
        if (mounted) setState(() => _error = e is GatewayException ? e.message : e.toString());
      }
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _enablePush() async {
    setState(() => _enabling = true);
    final wallet = context.read<WalletService>();
    final failureReason = await _pushService.enableForAddress(wallet.gateway, wallet.activeAddress());
    if (!mounted) return;
    setState(() => _enabling = false);
    if (failureReason != null) {
      setState(() => _error = failureReason);
    } else {
      await _refresh();
    }
  }

  Future<void> _addAlert() async {
    final threshold = double.tryParse(_thresholdController.text.trim());
    if (threshold == null || threshold <= 0) {
      setState(() => _error = 'Enter a USD price to alert at.');
      return;
    }
    final token = _token;
    if (token == null) return;
    setState(() => _error = null);
    try {
      final wallet = context.read<WalletService>();
      await wallet.gateway.createPriceAlert(
        address: wallet.activeAddress(),
        token: token,
        direction: _direction,
        thresholdUsd: threshold,
      );
      _thresholdController.clear();
      await _refresh();
    } catch (e) {
      setState(() => _error = e is GatewayException ? e.message : e.toString());
    }
  }

  Future<void> _deleteAlert(int id) async {
    final token = _token;
    if (token == null) return;
    try {
      final wallet = context.read<WalletService>();
      await wallet.gateway.deletePriceAlert(address: wallet.activeAddress(), token: token, alertId: id);
      await _refresh();
    } catch (e) {
      setState(() => _error = e is GatewayException ? e.message : e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Price Alerts')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(padding: const EdgeInsets.all(24), children: _body(context)),
      ),
    );
  }

  List<Widget> _body(BuildContext context) {
    if (!isFirebaseConfigured) {
      return const [
        Text("Push notifications aren't set up on this build yet, so price alerts have nowhere to deliver to."),
      ];
    }
    if (_token == null) {
      return [
        const Text(
          'Price alerts are delivered as a push notification, the same '
          'mechanism as "notify me on incoming payment". Enable it once '
          'to use both.',
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: _enabling ? null : _enablePush,
          child: Text(_enabling ? 'Enabling...' : 'Enable notifications'),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Text(_error!, style: const TextStyle(color: Colors.red)),
          ),
      ];
    }
    return [
      Text(
        _currentPrice == null
            ? 'Current price: unavailable right now'
            : 'Current price: ~\$${_currentPrice!.toStringAsFixed(6)}',
        style: const TextStyle(color: Colors.grey),
      ),
      const SizedBox(height: 4),
      const Text(
        'Each alert fires once, then you can set a new one -- see the note '
        'on the wallet\'s price estimate about thin liquidity.',
        style: TextStyle(color: Colors.grey, fontSize: 12),
      ),
      const SizedBox(height: 16),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  DropdownButton<String>(
                    value: _direction,
                    items: const [
                      DropdownMenuItem(value: 'above', child: Text('Goes above')),
                      DropdownMenuItem(value: 'below', child: Text('Goes below')),
                    ],
                    onChanged: (v) => setState(() => _direction = v ?? 'above'),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: _thresholdController,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'USD price', border: OutlineInputBorder()),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              OutlinedButton(onPressed: _addAlert, child: const Text('Add alert')),
            ],
          ),
        ),
      ),
      if (_error != null)
        Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Text(_error!, style: const TextStyle(color: Colors.red)),
        ),
      const SizedBox(height: 16),
      Text('Active alerts', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      if (_alerts.isEmpty)
        const Text('No alerts set.', style: TextStyle(color: Colors.grey))
      else
        ..._alerts.map(_alertRow),
    ];
  }

  Widget _alertRow(Map<String, dynamic> a) {
    final direction = a['direction'] == 'above' ? 'Goes above' : 'Goes below';
    final threshold = (a['threshold_usd'] as num).toDouble();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text('$direction \$${threshold.toStringAsFixed(6)}'),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Remove',
            onPressed: () => _deleteAlert(a['id'] as int),
          ),
        ],
      ),
    );
  }
}
