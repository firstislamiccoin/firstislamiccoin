/// Firebase project configuration for native mobile push notifications
/// -- see PARAMETERS.md section 34. Fill these four values in from a
/// real Firebase project's `google-services.json` once one exists
/// (Firebase Console -> Project Settings -> your Android app -> download
/// config file) -- extract the values named below rather than adding the
/// raw JSON file to the Android project tree, since this app initializes
/// Firebase from Dart (FirebaseOptions) rather than the google-services
/// Gradle plugin, specifically so the app builds and runs completely
/// normally before these are filled in. Left blank, [isFirebaseConfigured]
/// is false and every push-registration code path is skipped.
library;

import 'package:firebase_core/firebase_core.dart';

/// google-services.json: client[0].api_key[0].current_key
const String _apiKey = '';

/// google-services.json: client[0].client_info.mobilesdk_app_id
const String _appId = '';

/// google-services.json: project_info.project_number
const String _messagingSenderId = '';

/// google-services.json: project_info.project_id
const String _projectId = '';

bool get isFirebaseConfigured =>
    _apiKey.isNotEmpty && _appId.isNotEmpty && _messagingSenderId.isNotEmpty && _projectId.isNotEmpty;

FirebaseOptions get firebaseOptions => const FirebaseOptions(
      apiKey: _apiKey,
      appId: _appId,
      messagingSenderId: _messagingSenderId,
      projectId: _projectId,
    );
