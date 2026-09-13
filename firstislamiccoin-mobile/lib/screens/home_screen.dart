/// Main wallet screen: balance + navigation to send/receive/history/
/// staking/settings. Balance is fetched once on open and via pull-to-refresh
/// -- no polling timers (see docs/store-compliance.md, "no background work").
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n/generated/app_localizations.dart';
import '../models/wallet_models.dart';
import '../services/wallet_service.dart';
import '../widgets/fiat_placeholder.dart';
import 'history_screen.dart';
import 'multisig_screen.dart';
import 'offline_send_screen.dart';
import 'offline_sign_screen.dart';
import 'price_alerts_screen.dart';
import 'receive_screen.dart';
import 'referral_screen.dart';
import 'send_screen.dart';
import 'settings_screen.dart';
import 'staking_screen.dart';
import 'watch_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Balance? _balance;
  String? _error;
  bool _loading = true;
  int _newTxCount = 0;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final wallet = context.read<WalletService>();
      final json = await wallet.fetchBalance();
      setState(() => _balance = Balance.fromJson(json));
      // Best-effort: a failure here shouldn't block the balance refresh
      // that's the actual point of this pull.
      try {
        final newCount = await wallet.checkForNewTransactions();
        if (mounted) setState(() => _newTxCount = newCount);
      } catch (_) {}
    } catch (e) {
      setState(() => _error = 'Could not reach the network: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final wallet = context.watch<WalletService>();
    final l10n = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(
        title: const Text('FirstIslamicCoin'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            if (_newTxCount > 0)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Material(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(8),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: () {
                      setState(() => _newTxCount = 0);
                      Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const HistoryScreen()),
                      );
                    },
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              _newTxCount == 1 ? '1 new transaction' : '$_newTxCount new transactions',
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
              ),
            Text(
              wallet.network.name,
              style: Theme.of(context).textTheme.labelLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Center(
              child: _loading
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 24),
                      child: CircularProgressIndicator(),
                    )
                  : Column(
                      children: [
                        Text(
                          '${formatFic(_balance?.total ?? BigInt.zero)} FIC',
                          style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 4),
                        FiatPlaceholder(ficAmount: (_balance?.total ?? BigInt.zero).toDouble() / 1e8),
                      ],
                    ),
            ),
            if (_error != null) Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_error!, textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red)),
            ),
            const SizedBox(height: 32),
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    icon: Icons.arrow_upward,
                    label: l10n.navSend,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const SendScreen()),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionButton(
                    icon: Icons.arrow_downward,
                    label: l10n.navReceive,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const ReceiveScreen()),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    icon: Icons.history,
                    label: l10n.navHistory,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const HistoryScreen()),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionButton(
                    icon: Icons.savings_outlined,
                    label: l10n.navStaking,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const StakingScreen()),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    icon: Icons.groups_outlined,
                    label: l10n.navMultisig,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const MultisigScreen()),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionButton(
                    icon: Icons.visibility_outlined,
                    label: l10n.navWatch,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const WatchScreen()),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    icon: Icons.card_giftcard_outlined,
                    label: l10n.navReferrals,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const ReferralScreen()),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionButton(
                    icon: Icons.notifications_active_outlined,
                    label: l10n.navPriceAlerts,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const PriceAlertsScreen()),
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 40),
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    icon: Icons.send_to_mobile_outlined,
                    label: l10n.navOfflineSend,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const OfflineSendScreen()),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionButton(
                    icon: Icons.airplanemode_active,
                    label: l10n.navSignOffline,
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const OfflineSignScreen()),
                    ),
                  ),
                ),
              ],
            ),
            const Padding(
              padding: EdgeInsets.only(top: 6),
              child: Text(
                'Air-gapped signing: keep your seed on a second, offline '
                'device instead of a Ledger/Trezor -- neither vendor '
                'supports an unlisted coin like FIC. "Offline Send" builds '
                'an unsigned request from a watch-only xpub; "Sign Offline" '
                'signs it on the device holding the seed.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 11, color: Colors.grey),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _ActionButton({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
      child: Column(
        children: [
          Icon(icon),
          const SizedBox(height: 4),
          Text(label),
        ],
      ),
    );
  }
}
