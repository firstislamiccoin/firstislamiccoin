/// Native mobile push notification registration -- see PARAMETERS.md
/// section 34. Requests notification permission, fetches this device's
/// FCM token, and registers it with the gateway against a specific
/// address. Every method here is a no-op-with-a-clear-reason if
/// firebase_config.dart's placeholder values haven't been filled in
/// yet (isFirebaseConfigured == false) -- this file, and everything
/// that calls it, must never crash or block on that.
library;

import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'firebase_config.dart';
import 'gateway_api.dart';

class PushService {
  bool _initialized = false;

  Future<void> _ensureInitialized() async {
    if (_initialized) return;
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(options: firebaseOptions);
    }
    _initialized = true;
  }

  /// Requests notification permission and, if granted, registers this
  /// device's FCM token with the gateway for [address]. Returns a
  /// human-readable reason on failure (not configured yet, permission
  /// denied, etc.), or null on success.
  Future<String?> enableForAddress(GatewayApi gateway, String address) async {
    if (!isFirebaseConfigured) {
      return "Push notifications aren't set up on this build yet.";
    }
    try {
      await _ensureInitialized();
      final settings = await FirebaseMessaging.instance.requestPermission();
      if (settings.authorizationStatus == AuthorizationStatus.denied) {
        return 'Notification permission was denied.';
      }
      final token = await FirebaseMessaging.instance.getToken();
      if (token == null) {
        return 'Could not get a device token.';
      }
      await gateway.registerPushToken(
        address: address,
        platform: Platform.isIOS ? 'ios' : 'android',
        token: token,
      );
      return null;
    } catch (e) {
      return 'Could not enable notifications: $e';
    }
  }

  /// This device's current FCM token, or null if push isn't configured/
  /// permitted -- used by PriceAlertsScreen to list/delete alerts already
  /// registered under this token without re-registering it. Does not
  /// prompt for permission (call [enableForAddress] first for that).
  Future<String?> currentToken() async {
    if (!isFirebaseConfigured) return null;
    try {
      await _ensureInitialized();
      final settings = await FirebaseMessaging.instance.getNotificationSettings();
      if (settings.authorizationStatus == AuthorizationStatus.denied) return null;
      return await FirebaseMessaging.instance.getToken();
    } catch (e) {
      return null;
    }
  }
}
