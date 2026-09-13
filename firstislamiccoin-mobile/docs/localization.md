# Localization status

The master prompt's Phase 5 spec calls for English (default), Arabic, Urdu,
Bahasa Indonesia, Malay, and Turkish, with Arabic/Urdu rendered right-to-left.
This is a real, working localization pipeline (`flutter gen-l10n`, wired into
`main.dart`), not a placeholder -- but its **coverage** is intentionally
partial. Read this before assuming any given screen is localized.

## What's actually wired up

- `l10n.yaml` + `lib/l10n/app_en.arb` + `lib/l10n/app_ar.arb`: real ARB
  source files, code-generated into `lib/l10n/generated/app_localizations.dart`
  by `flutter gen-l10n` (triggered automatically by `pubspec.yaml`'s
  `flutter: generate: true` on `flutter pub get`/`flutter build`/`flutter run`).
- `main.dart`'s `MaterialApp` has `localizationsDelegates` and
  `supportedLocales: [Locale('en'), Locale('ar')]` wired up, plus
  `onGenerateTitle` reading from `AppLocalizations`. Flutter derives RTL
  layout automatically from the resolved locale -- there is no separate
  "RTL mode" flag to set, so once Arabic is genuinely selected (device
  locale or a future in-app language switcher), every built-in Material
  widget mirrors itself correctly with no extra code.
- A representative sample of screens reads real strings through
  `AppLocalizations.of(context)!`: `home_screen.dart`'s eight primary
  navigation button labels, `settings_screen.dart`'s section headers/
  network/theme radio labels/wipe-wallet action/cancel button, and
  `onboarding_screen.dart`'s create/restore/confirm-backup/continue
  buttons and app title.

## What's still English-only

The other ~90% of this app's UI strings -- every other screen (send,
receive, history, staking, multisig, watch, referrals, price alerts,
offline send/sign, tx detail, QR scan, lock screen) plus every error
message, hint text, and dialog body anywhere -- are still plain Dart
string literals, not ARB-backed. This is a large, mechanical retrofit
(extract each literal to the template ARB, translate, wire
`AppLocalizations.of(context)!.xxx` in its place) that was out of scope to
finish this phase; the infrastructure and the pattern are proven, the
remaining ~90% is follow-up work.

## Why only Arabic has a translation

Every string in `app_ar.arb` is generic wallet/fintech vocabulary (send,
receive, staking, settings, mainnet, wipe wallet, and so on) with
well-established, unambiguous Arabic equivalents used consistently across
existing crypto-wallet UIs -- there was no string here touching religious
or Shariah-specific terminology to get subtly wrong. It should still get a
native-speaker review pass before shipping; nothing here has been checked
by an Arabic speaker.

Urdu, Bahasa Indonesia, Malay, and Turkish have **no ARB file at all** yet
-- not even a machine-translated draft. This project's own rule (see
`docs/CHANGELOG-FIC.md`) is not to fabricate content that requires human
judgment to get right, and per-language UI translation is exactly that
kind of content, doubly so for a project whose whole premise is religious
sensitivity: getting a wallet's "Send"/"Receive" wrong is a bug, but
getting a mistranslated reference to prayer, charity, or any other
Islamic concept wrong (however unlikely with buttons this generic) is a
credibility problem, not just a UX one. Adding these languages needs a
native speaker for each, not a machine translation pass -- tracked as
`TODO-HUMAN` in `docs/CHANGELOG-FIC.md`.

## What "Bismillah" and similar terms mean for this file

`docs/CHANGELOG-FIC.md` and the website both establish the convention of
never translating "Bismillah" or other explicitly religious phrases --
they stay as-is in every language, the same way a brand name would. If a
future translation pass adds religious terminology anywhere in this app
(it hasn't yet -- nothing in `app_en.arb` today needs it), that convention
applies here too.
