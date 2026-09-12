import 'package:flutter/material.dart';

/// FirstIslamicCoin (FIC) brand colors and Material 3 themes.
class FicColors {
  static const green = Color(0xFF0B6E4F);
  static const greenDeep = Color(0xFF08523B);
  static const gold = Color(0xFFD4AF37);
  static const goldDeep = Color(0xFFB8962E);
  static const goldLight = Color(0xFFE9CC6A);
  static const dark = Color(0xFF0A1F17);
  static const light = Color(0xFFF7F5EE);
}

ThemeData ficLightTheme() => ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(seedColor: FicColors.green, primary: FicColors.green, secondary: FicColors.gold, brightness: Brightness.light, surface: FicColors.light),
  scaffoldBackgroundColor: FicColors.light,
  fontFamily: 'Poppins',
);

ThemeData ficDarkTheme() => ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(seedColor: FicColors.green, primary: const Color(0xFF1B9A6E), secondary: FicColors.goldLight, brightness: Brightness.dark, surface: const Color(0xFF10291F)),
  scaffoldBackgroundColor: FicColors.dark,
  fontFamily: 'Poppins',
);
