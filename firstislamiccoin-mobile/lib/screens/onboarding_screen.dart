/// First-run flow: create a new wallet (show mnemonic once) or restore
/// from an existing recovery phrase. No network calls happen here.
library;

import 'dart:math';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n/generated/app_localizations.dart';
import '../services/wallet_service.dart';

class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.account_balance_wallet_outlined, size: 72),
              const SizedBox(height: 16),
              Text(
                l10n.appTitle,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 48),
              FilledButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const _CreateWalletFlow()),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(l10n.onboardingCreateWallet),
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const _RestoreWalletFlow()),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text(l10n.onboardingRestoreWallet),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CreateWalletFlow extends StatefulWidget {
  const _CreateWalletFlow();

  @override
  State<_CreateWalletFlow> createState() => _CreateWalletFlowState();
}

class _CreateWalletFlowState extends State<_CreateWalletFlow> {
  String? _mnemonic;
  bool _confirmed = false;
  bool _quizMode = false;
  List<int> _quizIndices = [];
  final List<TextEditingController> _quizControllers = [];
  String? _quizError;

  Future<void> _generate() async {
    final wallet = context.read<WalletService>();
    // Generate and hold in memory for display only; wallet_service already
    // persisted it to secure storage as part of createNewWallet().
    final mnemonic = await wallet.createNewWallet();
    setState(() => _mnemonic = mnemonic);
  }

  @override
  void initState() {
    super.initState();
    _generate();
  }

  @override
  void dispose() {
    for (final c in _quizControllers) {
      c.dispose();
    }
    super.dispose();
  }

  // Picks 3 random distinct word positions and asks the user to retype
  // them, so a mistyped or skipped word in the backup is caught here
  // rather than the first time it's actually needed (see PARAMETERS.md
  // section 23 for why this exists -- neither wallet checked this before).
  void _startQuiz() {
    final words = _mnemonic!.split(' ');
    final rand = Random();
    final indices = <int>{};
    while (indices.length < 3) {
      indices.add(rand.nextInt(words.length));
    }
    _quizIndices = indices.toList()..sort();
    for (final c in _quizControllers) {
      c.dispose();
    }
    _quizControllers
      ..clear()
      ..addAll(List.generate(_quizIndices.length, (_) => TextEditingController()));
    setState(() {
      _quizMode = true;
      _quizError = null;
    });
  }

  void _verifyQuiz() {
    final words = _mnemonic!.split(' ');
    for (var i = 0; i < _quizIndices.length; i++) {
      final expected = words[_quizIndices[i]];
      final entered = _quizControllers[i].text.trim().toLowerCase();
      if (entered != expected) {
        setState(() => _quizError =
            "One or more words don't match. Check your written-down phrase and try again.");
        return;
      }
    }
    Navigator.of(context).popUntil((r) => r.isFirst);
  }

  @override
  Widget build(BuildContext context) {
    if (_mnemonic == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Your recovery phrase')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }
    if (_quizMode) {
      return Scaffold(
        appBar: AppBar(title: const Text('Confirm your backup')),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Enter the requested words from the phrase you just wrote '
                'down, to make sure it was recorded correctly before it\'s '
                'needed.',
              ),
              const SizedBox(height: 20),
              for (var i = 0; i < _quizIndices.length; i++) ...[
                TextField(
                  controller: _quizControllers[i],
                  autocorrect: false,
                  decoration: InputDecoration(
                    labelText: 'Word #${_quizIndices[i] + 1}',
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
              ],
              if (_quizError != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(_quizError!, style: const TextStyle(color: Colors.red)),
                ),
              FilledButton(
                onPressed: _verifyQuiz,
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Verify & continue'),
                ),
              ),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => setState(() => _quizMode = false),
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Text('Show phrase again'),
                ),
              ),
            ],
          ),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Your recovery phrase')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Write down these 12 words in order and store them somewhere '
              'safe. Anyone with this phrase can spend your funds. '
              'FirstIslamicCoin cannot recover it for you.',
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                _mnemonic!,
                style: const TextStyle(fontSize: 18, height: 1.6),
              ),
            ),
            const SizedBox(height: 20),
            CheckboxListTile(
              value: _confirmed,
              onChanged: (v) => setState(() => _confirmed = v ?? false),
              controlAffinity: ListTileControlAffinity.leading,
              title: Text(AppLocalizations.of(context).onboardingConfirmedBackup),
            ),
            const Spacer(),
            FilledButton(
              onPressed: _confirmed ? _startQuiz : null,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(AppLocalizations.of(context).onboardingContinue),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RestoreWalletFlow extends StatefulWidget {
  const _RestoreWalletFlow();

  @override
  State<_RestoreWalletFlow> createState() => _RestoreWalletFlowState();
}

class _RestoreWalletFlowState extends State<_RestoreWalletFlow> {
  final _controller = TextEditingController();
  String? _error;
  bool _busy = false;

  Future<void> _restore() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await context.read<WalletService>().restoreWallet(_controller.text.trim());
      if (mounted) Navigator.of(context).popUntil((r) => r.isFirst);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Restore wallet')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Enter your 12-word recovery phrase, separated by spaces.'),
            const SizedBox(height: 16),
            TextField(
              controller: _controller,
              maxLines: 3,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: 'word1 word2 word3 ...',
              ),
            ),
            if (_error != null) Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: _busy ? null : _restore,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: _busy
                    ? const SizedBox(
                        height: 20, width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Restore'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
