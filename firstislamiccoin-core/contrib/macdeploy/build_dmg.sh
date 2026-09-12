#!/bin/bash
# Build a redistributable CodexaCoin-Core-macOS.dmg from a native macOS
# build. Requires a completed `./configure --with-gui=yes && make` first
# (see doc/build-osx.md) and Qt's `macdeployqt` on PATH (installed
# alongside `qt@5` via Homebrew).
#
# This produces a *locally-built* dmg, portable to other Macs (macdeployqt
# bundles the Qt frameworks in), but not a codesigned/notarized one -- see
# the TODO at the bottom for the manual steps required before any public
# distribution.
#
# Usage (from the repo root, after building):
#   ./contrib/macdeploy/build_dmg.sh

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
REPO_ROOT="$PWD"
APP_NAME="CodexaCoin-Qt.app"
DMG_NAME="CodexaCoin-Core-macOS.dmg"
VOLNAME="CodexaCoin Core"

if ! command -v macdeployqt >/dev/null 2>&1; then
    echo "macdeployqt not found on PATH. Install Qt5 (brew install qt@5) and" >&2
    echo "add /usr/local/opt/qt@5/bin (or the equivalent for your Homebrew prefix) to PATH." >&2
    exit 1
fi

echo "=== Assembling $APP_NAME bundle (make target) ==="
make \
    "$APP_NAME/Contents/PkgInfo" \
    "$APP_NAME/Contents/Resources/empty.lproj" \
    "$APP_NAME/Contents/Resources/bitcoin.icns" \
    "$APP_NAME/Contents/Info.plist" \
    "$APP_NAME/Contents/MacOS/CodexaCoin-Qt" \
    "$APP_NAME/Contents/Resources/Base.lproj/InfoPlist.strings"

echo "=== Bundling Qt frameworks (macdeployqt) ==="
macdeployqt "$APP_NAME"

echo "=== Verifying the bundle no longer depends on external Qt/Homebrew paths ==="
if otool -L "$APP_NAME/Contents/MacOS/CodexaCoin-Qt" | grep -q "/usr/local/opt/qt@5"; then
    echo "ERROR: bundle still references external Qt frameworks; macdeployqt did not fully bundle them." >&2
    exit 1
fi

echo "=== Packaging $DMG_NAME ==="
STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT
cp -R "$APP_NAME" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

rm -f "$DMG_NAME"
hdiutil create -volname "$VOLNAME" -srcfolder "$STAGING_DIR" -ov -format UDZO "$DMG_NAME"
hdiutil verify "$DMG_NAME"

echo ""
echo "=== Done: $REPO_ROOT/$DMG_NAME ==="
echo ""
echo "TODO before any public distribution (not done by this script -- needs"
echo "a real Apple Developer ID certificate, which this environment doesn't"
echo "have):"
echo ""
echo "  # 1. Code-sign the app (replace with your actual Developer ID Application identity):"
echo "  codesign --deep --force --verify --verbose \\"
echo "    --sign \"Developer ID Application: YOUR NAME (TEAMID)\" \\"
echo "    --options runtime \\"
echo "    \"$APP_NAME\""
echo ""
echo "  # 2. Re-create the dmg from the now-signed app (repeat the hdiutil"
echo "  #    create step above), then sign the dmg itself:"
echo "  codesign --force --verify --verbose \\"
echo "    --sign \"Developer ID Application: YOUR NAME (TEAMID)\" \\"
echo "    \"$DMG_NAME\""
echo ""
echo "  # 3. Notarize with Apple (requires an app-specific password or API key,"
echo "  #    set up via 'xcrun notarytool store-credentials' first):"
echo "  xcrun notarytool submit \"$DMG_NAME\" --keychain-profile \"AC_PASSWORD\" --wait"
echo ""
echo "  # 4. Staple the notarization ticket so it works offline:"
echo "  xcrun stapler staple \"$DMG_NAME\""
