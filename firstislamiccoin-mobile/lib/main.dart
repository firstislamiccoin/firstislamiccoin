import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'l10n/generated/app_localizations.dart';
import 'services/wallet_service.dart';
import 'screens/lock_screen.dart';
import 'screens/onboarding_screen.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const FicWalletApp());
}

// Brand green, from firstislamiccoin-brand/tokens/theme.css (--fic-green).
const _brandSeed = Color(0xFF0B6E4F);

final ThemeData _darkTheme = ThemeData(
  colorSchemeSeed: _brandSeed,
  brightness: Brightness.dark,
  useMaterial3: true,
);
final ThemeData _lightTheme = ThemeData(
  colorSchemeSeed: _brandSeed,
  brightness: Brightness.light,
  useMaterial3: true,
);

ThemeMode _themeModeFor(String stored) {
  switch (stored) {
    case 'dark':
      return ThemeMode.dark;
    case 'light':
      return ThemeMode.light;
    default:
      return ThemeMode.system;
  }
}

class FicWalletApp extends StatelessWidget {
  const FicWalletApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => WalletService(),
      // Consumer (not a plain child) so MaterialApp rebuilds with the new
      // themeMode as soon as Settings changes it -- no app restart needed.
      child: Consumer<WalletService>(
        builder: (context, wallet, _) => MaterialApp(
          onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          // Only English and Arabic have a reviewed translation today --
          // see docs/localization.md for Urdu/Bahasa/Malay/Turkish's
          // status (ARB scaffolding exists, translation doesn't yet).
          // Arabic exercises the RTL layout path; Flutter derives text
          // direction from the resolved locale automatically, no
          // separate flag needed.
          supportedLocales: const [Locale('en'), Locale('ar')],
          theme: _lightTheme,
          darkTheme: _darkTheme,
          themeMode: _themeModeFor(wallet.themeMode),
          home: const _Bootstrap(),
        ),
      ),
    );
  }
}

/// Loads wallet state (does it exist? which network?) before deciding
/// whether to show onboarding, the biometric lock screen, or the home
/// screen directly.
class _Bootstrap extends StatefulWidget {
  const _Bootstrap();

  @override
  State<_Bootstrap> createState() => _BootstrapState();
}

class _BootstrapState extends State<_Bootstrap> {
  @override
  void initState() {
    super.initState();
    context.read<WalletService>().bootstrap();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<WalletService>(
      builder: (context, wallet, _) {
        if (!wallet.loaded) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (!wallet.hasWallet) {
          return const OnboardingScreen();
        }
        return const LockScreen(child: HomeScreen());
      },
    );
  }
}
