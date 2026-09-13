/// Referral screen: view your own referral code, copy/share it, see who
/// you've referred and what you've earned, and withdraw available credit.
/// Mirrors web-wallet/index.html's #referral-card, gated on the same
/// staking-service login (see vps-gateway/referral.py) -- this doesn't
/// introduce a separate account system, it's the existing staking
/// account's referral program, just previously only viewable on web.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

import '../models/wallet_models.dart';
import '../services/gateway_api.dart';
import '../services/wallet_service.dart';
import 'staking_screen.dart';

class ReferralScreen extends StatefulWidget {
  const ReferralScreen({super.key});

  @override
  State<ReferralScreen> createState() => _ReferralScreenState();
}

class _ReferralScreenState extends State<ReferralScreen> {
  bool _loading = true;
  String? _error;
  String? _code;
  int _referredCount = 0;
  int _availableSatoshis = 0;
  List<Map<String, dynamic>> _history = const [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final wallet = context.read<WalletService>();
    if (!wallet.stakingLoggedIn) {
      setState(() => _loading = false);
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final status = await wallet.fetchReferralStatus();
      final history = await wallet.fetchReferralHistory();
      setState(() {
        _code = status['referral_code'] as String?;
        _referredCount = (status['referred_count'] as num?)?.toInt() ?? 0;
        _availableSatoshis = (status['available_satoshis'] as num?)?.toInt() ?? 0;
        _history = List<Map<String, dynamic>>.from(history['referrals'] as List? ?? const []);
      });
    } catch (e) {
      if (e is GatewayException && e.code == 'unauthorized') {
        await wallet.stakingLogout();
      } else {
        setState(() => _error = e is GatewayException ? e.message : e.toString());
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final loggedIn = context.watch<WalletService>().stakingLoggedIn;
    return Scaffold(
      appBar: AppBar(title: const Text('Referrals')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(24),
                children: loggedIn ? _statusView(context) : _loggedOutView(context),
              ),
      ),
    );
  }

  List<Widget> _loggedOutView(BuildContext context) {
    return [
      const Text(
        'Sign in to your staking account to view and share your referral '
        'code.',
      ),
      const SizedBox(height: 16),
      FilledButton(
        onPressed: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const StakingScreen()),
        ),
        child: const Text('Go to Staking sign-in'),
      ),
    ];
  }

  List<Widget> _statusView(BuildContext context) {
    final code = _code ?? '-';
    return [
      const Text(
        'Share your code. When someone signs up with it and makes their '
        'first deposit, you get 10% of that deposit, credited here -- '
        'withdraw it to any address whenever you like.',
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
                  Expanded(
                    child: SelectableText(
                      code,
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.copy),
                    tooltip: 'Copy',
                    onPressed: code == '-'
                        ? null
                        : () async {
                            await Clipboard.setData(ClipboardData(text: code));
                            if (context.mounted) {
                              ScaffoldMessenger.of(context)
                                  .showSnackBar(const SnackBar(content: Text('Referral code copied')));
                            }
                          },
                  ),
                  IconButton(
                    icon: const Icon(Icons.share),
                    tooltip: 'Share',
                    onPressed: code == '-'
                        ? null
                        : () => Share.share('Sign up for FirstIslamicCoin with my referral code: $code'),
                  ),
                ],
              ),
              const Divider(),
              _row('People referred', '$_referredCount'),
              _row('Available to withdraw', '${formatFic(BigInt.from(_availableSatoshis))} FIC'),
            ],
          ),
        ),
      ),
      const SizedBox(height: 16),
      _WithdrawCard(canWithdraw: _availableSatoshis > 0, onDone: _refresh),
      const SizedBox(height: 16),
      Text('Referral history', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 8),
      if (_history.isEmpty)
        const Text('No referrals yet.', style: TextStyle(color: Colors.grey))
      else
        ..._history.map(_historyRow),
      if (_error != null)
        Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Text(_error!, style: const TextStyle(color: Colors.red)),
        ),
    ];
  }

  Widget _historyRow(Map<String, dynamic> r) {
    final email = r['referred_email_masked'] as String? ?? '?';
    final joinedAt = (r['joined_at'] as num?)?.toDouble();
    final joined = joinedAt == null
        ? ''
        : DateTime.fromMillisecondsSinceEpoch((joinedAt * 1000).round()).toLocal().toString().split(' ').first;
    final amount = r['amount_satoshis'] as num?;
    final withdrawn = r['withdrawn'] == true;
    final status = amount == null
        ? 'no funded deposit yet'
        : '${formatFic(BigInt.from(amount.toInt()))} FIC earned (${withdrawn ? 'withdrawn' : 'available'})';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(child: Text('$email (joined $joined)', overflow: TextOverflow.ellipsis)),
          Text(status, style: const TextStyle(color: Colors.grey)),
        ],
      ),
    );
  }

  Widget _row(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [Text(label), Text(value)],
      ),
    );
  }
}

class _WithdrawCard extends StatefulWidget {
  final bool canWithdraw;
  final VoidCallback onDone;
  const _WithdrawCard({required this.canWithdraw, required this.onDone});

  @override
  State<_WithdrawCard> createState() => _WithdrawCardState();
}

class _WithdrawCardState extends State<_WithdrawCard> {
  final _address = TextEditingController();
  bool _submitting = false;
  String? _result;
  String? _error;

  @override
  void dispose() {
    _address.dispose();
    super.dispose();
  }

  Future<void> _withdraw() async {
    final toAddress = _address.text.trim();
    if (toAddress.isEmpty) {
      setState(() => _error = 'Enter a destination address.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
      _result = null;
    });
    try {
      final result = await context.read<WalletService>().referralWithdraw(toAddress);
      setState(() => _result = 'Withdrawal broadcast: ${result['txid']}');
      widget.onDone();
    } catch (e) {
      setState(() => _error = e is GatewayException ? e.message : e.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Withdraw referral credit', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _address,
              decoration: const InputDecoration(
                labelText: 'To address (your own wallet)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: _submitting || !widget.canWithdraw ? null : _withdraw,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: _submitting
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Withdraw all available credit'),
              ),
            ),
            if (_result != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: SelectableText(_result!, style: const TextStyle(color: Colors.green)),
              ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(_error!, style: const TextStyle(color: Colors.red)),
              ),
          ],
        ),
      ),
    );
  }
}
