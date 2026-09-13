/// Generic camera QR scanner, returning the decoded text via
/// Navigator.pop. Shared by the send screen (destination address) and
/// the multisig screen (proposal JSON) -- same camera overlay, different
/// caller-side handling of the result.
library;

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class QrScanScreen extends StatelessWidget {
  final String title;
  const QrScanScreen({super.key, this.title = 'Scan QR code'});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: MobileScanner(
        onDetect: (capture) {
          final barcodes = capture.barcodes;
          if (barcodes.isNotEmpty && barcodes.first.rawValue != null) {
            Navigator.of(context).pop(barcodes.first.rawValue);
          }
        },
        errorBuilder: (context, error, child) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              'Could not access the camera: ${error.errorCode.name}. '
              'Check that camera access is allowed for this app in your '
              'device settings.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ),
    );
  }
}
