package com.firstislamiccoin.wallet

import io.flutter.embedding.android.FlutterFragmentActivity

// local_auth (biometric app lock, see lib/screens/lock_screen.dart) requires
// its host Activity to be a FragmentActivity to show the system biometric
// prompt -- plain FlutterActivity throws "no_fragment_activity" the moment
// the lock screen tries to authenticate. Found live: a fresh install got
// stuck on the lock screen with that exact error, unable to reach the rest
// of the app at all.
class MainActivity: FlutterFragmentActivity()
