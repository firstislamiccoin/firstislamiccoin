/// Biometric app lock. Gates *app access* on launch/resume -- not
/// per-transaction signing (see docs/store-compliance.md's note on this
/// being a deliberate scope simplification for this phase).
library;

import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';

class LockScreen extends StatefulWidget {
  final Widget child;
  const LockScreen({super.key, required this.child});

  @override
  State<LockScreen> createState() => _LockScreenState();
}

class _LockScreenState extends State<LockScreen> {
  final _auth = LocalAuthentication();
  bool _unlocked = false;
  bool _checking = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _attemptUnlock();
  }

  Future<void> _attemptUnlock() async {
    setState(() {
      _checking = true;
      _error = null;
    });
    try {
      final canCheck = await _auth.canCheckBiometrics || await _auth.isDeviceSupported();
      if (!canCheck) {
        // No biometric/passcode hardware available on this device/simulator
        // -- don't lock the user out of their own wallet because of that;
        // fall through unlocked. A production release should offer a
        // fallback PIN instead of silently skipping the lock entirely.
        setState(() {
          _unlocked = true;
          _checking = false;
        });
        return;
      }
      final didAuthenticate = await _auth.authenticate(
        localizedReason: 'Unlock your FirstIslamicCoin wallet',
        options: const AuthenticationOptions(biometricOnly: false, stickyAuth: true),
      );
      setState(() {
        _unlocked = didAuthenticate;
        _checking = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Authentication error: $e';
        _checking = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_unlocked) return widget.child;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.lock_outline, size: 64),
            const SizedBox(height: 16),
            const Text('FirstIslamicCoin Wallet is locked'),
            if (_error != null) Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
            const SizedBox(height: 24),
            _checking
                ? const CircularProgressIndicator()
                : ElevatedButton(onPressed: _attemptUnlock, child: const Text('Unlock')),
          ],
        ),
      ),
    );
  }
}
