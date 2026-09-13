/// Staking screen: sign in (or sign up) to the custodial staking gateway
/// account, then view status and deposit/withdraw. Read-only + remote-
/// calls-only by design -- this screen never computes a reward, mints a
/// coinstake, or runs anything on a timer. All figures come from the
/// gateway's /staking/status endpoint; deposit/withdraw are single
/// explicit-tap HTTP calls, matching web-wallet/app.js's flow exactly.
/// See docs/store-compliance.md for why "no background work" matters here.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/wallet_models.dart';
import '../services/gateway_api.dart';
import '../services/wallet_service.dart';

class StakingScreen extends StatefulWidget {
  const StakingScreen({super.key});

  @override
  State<StakingScreen> createState() => _StakingScreenState();
}

class _StakingScreenState extends State<StakingScreen> {
  StakingStatus? _status;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final wallet = context.read<WalletService>();
    if (!wallet.stakingLoggedIn) {
      setState(() {
        _status = null;
        _loading = false;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final json = await wallet.fetchStakingStatus();
      setState(() => _status = StakingStatus.fromJson(json));
    } catch (e) {
      if (e is GatewayException && e.code == 'unauthorized') {
        // Token expired/invalid server-side -- drop back to the login form
        // rather than showing a confusing error, matching web-wallet.
        await wallet.stakingLogout();
        setState(() => _status = null);
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
      appBar: AppBar(title: const Text('Staking')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(24),
                children: loggedIn
                    ? _statusView(context)
                    : [_StakingAuthForm(onDone: _refresh)],
              ),
      ),
    );
  }

  List<Widget> _statusView(BuildContext context) {
    final status = _status ?? StakingStatus.notOptedIn;
    return [
      Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Custodial staking pool', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              _row('Delegated', '${formatFic(status.delegatedAmount)} FIC'),
              _row('Accrued rewards', '${formatFic(status.accruedRewards)} FIC'),
              _row('Rate', '${status.effectiveMonthlyRateBp / 100}% / month'),
              _row('Pool fee', '${status.poolFeeBp / 100}%'),
            ],
          ),
        ),
      ),
      const SizedBox(height: 16),
      const Text(
        'Rewards accrue automatically on the network -- no need to keep '
        'this app open or online. This screen only displays status '
        'reported by FirstIslamicCoin\'s custodial staking pool; staking itself '
        'never runs on this device.',
        style: TextStyle(color: Colors.grey),
      ),
      const SizedBox(height: 24),
      _DepositCard(onDone: _refresh),
      const SizedBox(height: 16),
      _WithdrawCard(canWithdraw: status.canWithdraw, onDone: _refresh),
      const SizedBox(height: 16),
      TextButton(
        onPressed: () async {
          await context.read<WalletService>().stakingLogout();
          _refresh();
        },
        child: const Text('Sign out of staking account'),
      ),
      if (_error != null)
        Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Text(_error!, style: const TextStyle(color: Colors.red)),
        ),
    ];
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

/// Login/signup form for the custodial staking gateway account. Signup
/// fields mirror web-wallet/index.html's #signup-only-fields exactly --
/// self-attested, not identity-verified (see vps-gateway/kyc.py).
class _StakingAuthForm extends StatefulWidget {
  final VoidCallback onDone;
  const _StakingAuthForm({required this.onDone});

  @override
  State<_StakingAuthForm> createState() => _StakingAuthFormState();
}

class _StakingAuthFormState extends State<_StakingAuthForm> {
  bool _signUp = false;
  bool _submitting = false;
  String? _error;

  final _email = TextEditingController();
  final _password = TextEditingController();
  final _fullName = TextEditingController();
  final _dateOfBirth = TextEditingController();
  String _idType = 'nic';
  final _idNumber = TextEditingController();
  final _referralCode = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _fullName.dispose();
    _dateOfBirth.dispose();
    _idNumber.dispose();
    _referralCode.dispose();
    super.dispose();
  }

  Future<void> _pickDateOfBirth() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime(now.year - 25),
      firstDate: DateTime(1900),
      lastDate: now,
    );
    if (picked != null) {
      _dateOfBirth.text =
          '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
    }
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final wallet = context.read<WalletService>();
      if (_signUp) {
        await wallet.stakingSignup(
          email: _email.text.trim(),
          password: _password.text,
          fullName: _fullName.text.trim(),
          dateOfBirth: _dateOfBirth.text.trim(),
          idType: _idType,
          idNumber: _idNumber.text.trim(),
          referralCode: _referralCode.text.trim(),
        );
      } else {
        await wallet.stakingLogin(_email.text.trim(), _password.text);
      }
      widget.onDone();
    } catch (e) {
      setState(() => _error = e is GatewayException ? e.message : e.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          'Sign in to the staking pool to deposit, withdraw, and see '
          'accrued rewards.',
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _password,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Password', border: OutlineInputBorder()),
        ),
        if (_signUp) ...[
          const SizedBox(height: 16),
          const Text(
            'Signing up also requires the fields below. This is '
            'self-attested information, not verified identity checking.',
            style: TextStyle(color: Colors.grey),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _fullName,
            decoration: const InputDecoration(labelText: 'Full name', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _dateOfBirth,
            readOnly: true,
            onTap: _pickDateOfBirth,
            decoration: const InputDecoration(
              labelText: 'Date of birth',
              border: OutlineInputBorder(),
              suffixIcon: Icon(Icons.calendar_today_outlined),
            ),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: _idType,
            decoration: const InputDecoration(labelText: 'ID type', border: OutlineInputBorder()),
            items: const [
              DropdownMenuItem(value: 'nic', child: Text('National ID card')),
              DropdownMenuItem(value: 'passport', child: Text('Passport')),
            ],
            onChanged: (v) => setState(() => _idType = v ?? 'nic'),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _idNumber,
            decoration: const InputDecoration(labelText: 'ID number', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _referralCode,
            decoration: const InputDecoration(
              labelText: 'Referral code (optional)',
              border: OutlineInputBorder(),
              hintText: 'Leave blank if none',
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Your ID number is encrypted before storage; your name and '
            'date of birth are not.',
            style: TextStyle(color: Colors.grey, fontSize: 12),
          ),
          const SizedBox(height: 8),
          const Text(
            'By signing up you agree to the Terms & Conditions, Privacy '
            'Policy, and AML/KYC Policy at firstislamiccoin.com/legal/.',
            style: TextStyle(color: Colors.grey, fontSize: 12),
          ),
        ],
        const SizedBox(height: 20),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: _submitting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(_signUp ? 'Sign up' : 'Log in'),
          ),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: _submitting ? null : () => setState(() => _signUp = !_signUp),
          child: Text(_signUp ? 'Already have an account? Log in' : "Don't have an account? Sign up"),
        ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(_error!, style: const TextStyle(color: Colors.red)),
          ),
      ],
    );
  }
}

class _DepositCard extends StatefulWidget {
  final VoidCallback onDone;
  const _DepositCard({required this.onDone});

  @override
  State<_DepositCard> createState() => _DepositCardState();
}

class _DepositCardState extends State<_DepositCard> {
  final _amount = TextEditingController();
  bool _submitting = false;
  String? _result;
  String? _error;

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  Future<void> _deposit() async {
    final amountFic = double.tryParse(_amount.text.trim());
    if (amountFic == null || amountFic <= 0) return;
    setState(() {
      _submitting = true;
      _error = null;
      _result = null;
    });
    try {
      final amountSatoshis = (amountFic * 100000000).round();
      final result = await context.read<WalletService>().stakingDeposit(amountSatoshis);
      setState(() => _result = 'Send funds to: ${result['deposit_address']}');
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
            Text('Deposit', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _amount,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Amount (FIC)', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: _submitting ? null : _deposit,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: _submitting
                    ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Get deposit address'),
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

class _WithdrawCard extends StatefulWidget {
  final bool canWithdraw;
  final VoidCallback onDone;
  const _WithdrawCard({required this.canWithdraw, required this.onDone});

  @override
  State<_WithdrawCard> createState() => _WithdrawCardState();
}

class _WithdrawCardState extends State<_WithdrawCard> {
  final _amount = TextEditingController();
  final _address = TextEditingController();
  bool _submitting = false;
  String? _result;
  String? _error;

  @override
  void dispose() {
    _amount.dispose();
    _address.dispose();
    super.dispose();
  }

  Future<void> _withdraw() async {
    final amountFic = double.tryParse(_amount.text.trim());
    final toAddress = _address.text.trim();
    if (amountFic == null || amountFic <= 0 || toAddress.isEmpty) {
      setState(() => _error = 'Enter an amount and destination address.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
      _result = null;
    });
    try {
      final amountSatoshis = (amountFic * 100000000).round();
      final result = await context.read<WalletService>().stakingWithdraw(amountSatoshis, toAddress);
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
            Text('Withdraw', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextField(
              controller: _amount,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Amount (FIC)', border: OutlineInputBorder()),
            ),
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
                    : const Text('Withdraw'),
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
