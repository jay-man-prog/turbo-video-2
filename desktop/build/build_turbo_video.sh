#!/bin/zsh
# Build the self-contained Turbo Video macOS application and local DMG.
# This script intentionally touches only desktop/build and desktop/dist.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_ROOT="$ROOT/desktop/build/final"
STAGE="$BUILD_ROOT/stage"
WORK="$BUILD_ROOT/work"
SPEC="$BUILD_ROOT/spec"
DIST="$ROOT/desktop/dist"
APP_NAME="Turbo Video"
APP_PATH="$DIST/$APP_NAME.app"
FFMPEG_SOURCE="${TURBO_VIDEO_FFMPEG_SOURCE:-/opt/homebrew/bin/ffmpeg}"
FFPROBE_SOURCE="${TURBO_VIDEO_FFPROBE_SOURCE:-/opt/homebrew/bin/ffprobe}"

fail() {
  print -u2 -- "Build failed: $*"
  exit 1
}

VERSION="$(sed -nE 's/^APP_VERSION = "([^"]+)"/\1/p' "$ROOT/app/utils/runtime_paths.py" | head -n 1)"
[[ -n "$VERSION" ]] || fail "Unable to read APP_VERSION from app/utils/runtime_paths.py."
DMG_PATH="$DIST/Turbo-Video-${VERSION}-arm64.dmg"

[[ "$(uname -s)" == "Darwin" ]] || fail "Turbo Video packaging must run on macOS."
[[ "$(uname -m)" == "arm64" ]] || fail "This build script currently targets Apple Silicon only."
[[ -x "$FFMPEG_SOURCE" && -x "$FFPROBE_SOURCE" ]] || fail "Set TURBO_VIDEO_FFMPEG_SOURCE and TURBO_VIDEO_FFPROBE_SOURCE to executable media tools."
command -v dylibbundler >/dev/null || fail "dylibbundler is required to make FFmpeg and FFprobe self-contained."
command -v iconutil >/dev/null || fail "macOS iconutil is required."
command -v hdiutil >/dev/null || fail "macOS hdiutil is required."

rm -rf "$BUILD_ROOT" "$DIST"
mkdir -p "$STAGE" "$WORK" "$SPEC" "$DIST"

# Bundle only immutable official resources. User music is imported on first launch
# into Application Support and is deliberately excluded from the signed bundle.
mkdir -p "$STAGE/resource"
rsync -a --exclude='songs' "$ROOT/resource/" "$STAGE/resource/"
rsync -a --exclude='.streamlit/config.toml' --exclude='__pycache__' "$ROOT/webui/" "$STAGE/webui/"
# Keep a physical, auditable copy of every first-party module in the bundle.
# The launcher prepends this location before importing app, preventing shadowing.
rsync -a --exclude='__pycache__' "$ROOT/app/" "$STAGE/first_party/app/"
cp "$ROOT/config.example.toml" "$STAGE/config.example.toml"

# Generate a macOS icon from the existing official R&H gold mark; no artwork is generated.
ICONSET="$STAGE/TurboVideo.iconset"
mkdir -p "$ICONSET"
ICON_SOURCE="$ROOT/resource/branding/Ampersand-Gold-RGB.png"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ICON_SOURCE" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  doubled=$((size * 2))
  sips -z "$doubled" "$doubled" "$ICON_SOURCE" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$STAGE/TurboVideo.icns"

# Place independent media executables and their non-system dynamic-library closure
# under Resources. dylibbundler rewrites install names away from Homebrew paths.
mkdir -p "$STAGE/bin" "$STAGE/lib" "$STAGE/licenses"
cp "$FFMPEG_SOURCE" "$STAGE/bin/ffmpeg"
cp "$FFPROBE_SOURCE" "$STAGE/bin/ffprobe"
chmod 755 "$STAGE/bin/ffmpeg" "$STAGE/bin/ffprobe"
dylibbundler -x "$STAGE/bin/ffmpeg" -b -d "$STAGE/lib" -p '@executable_path/../lib' -of -cd -s /opt/homebrew/opt -s /opt/homebrew/Cellar
dylibbundler -x "$STAGE/bin/ffprobe" -b -d "$STAGE/lib" -p '@executable_path/../lib' -of -cd -s /opt/homebrew/opt -s /opt/homebrew/Cellar

# Preserve the applicable project and FFmpeg notices alongside the bundle.
cp "$ROOT/LICENSE" "$STAGE/licenses/MoneyPrinterTurbo-MIT-LICENSE.txt"
FFMPEG_PREFIX="${TURBO_VIDEO_FFMPEG_LICENSE_DIR:-$(brew --prefix ffmpeg)}"
for notice in LICENSE.md COPYING.LGPLv2.1 COPYING.LGPLv3 COPYING.GPLv2 COPYING.GPLv3; do
  [[ -f "$FFMPEG_PREFIX/$notice" ]] && cp "$FFMPEG_PREFIX/$notice" "$STAGE/licenses/FFmpeg-$notice.txt"
done
"$FFMPEG_SOURCE" -version > "$STAGE/licenses/FFmpeg-version.txt" 2>&1 || true

cd "$ROOT"
uv run --group desktop pyinstaller \
  --noconfirm \
  --clean \
  --distpath "$DIST" \
  --workpath "$WORK" \
  "$ROOT/desktop/build/TurboVideo.spec"

[[ -d "$APP_PATH" ]] || fail "PyInstaller did not produce $APP_PATH"
[[ -f "$APP_PATH/Contents/Resources/first_party/app/models/llm_provider.py" ]] || fail "The bundled first-party llm provider is missing."
WARNINGS_FILE="$WORK/$APP_NAME/warn-$APP_NAME.txt"
if [[ -f "$WARNINGS_FILE" ]] && grep -E "missing module named '?app(\\.|')" "$WARNINGS_FILE"; then
  fail "PyInstaller reported an unresolved first-party app module."
fi

# Use a Developer ID Application certificate if one is already configured; otherwise
# intentionally create a valid local ad-hoc build and report the Gatekeeper limit.
SIGNING_IDENTITY="$(security find-identity -v -p codesigning 2>/dev/null | sed -n 's/.*"\(Developer ID Application:.*\)".*/\1/p' | head -n 1)"
if [[ -n "$SIGNING_IDENTITY" ]]; then
  SIGNING_STATUS="Developer ID signed"
  find "$APP_PATH/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -111 \) -print0 | xargs -0 -I{} codesign --force --sign "$SIGNING_IDENTITY" --options runtime "{}"
  codesign --force --deep --sign "$SIGNING_IDENTITY" --options runtime "$APP_PATH"
else
  SIGNING_STATUS="Ad-hoc signed; notarisation not available"
  find "$APP_PATH/Contents" -type f \( -name '*.dylib' -o -name '*.so' -o -perm -111 \) -print0 | xargs -0 -I{} codesign --force --sign - "{}"
  codesign --force --deep --sign - "$APP_PATH"
fi
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

# Import every first-party module with the executable inside the finished bundle.
# This build-only diagnostic proves physical module locations and catches dynamic
# provider imports that static analysis does not discover.
IMPORT_SMOKE_ROOT="$(mktemp -d -t turbo-video-import-smoke)"
trap 'rm -rf "$IMPORT_SMOKE_ROOT"' EXIT
mkdir -p "$IMPORT_SMOKE_ROOT/Application Support"
cp "$STAGE/config.example.toml" "$IMPORT_SMOKE_ROOT/Application Support/config.toml"
chmod 600 "$IMPORT_SMOKE_ROOT/Application Support/config.toml"
TURBO_VIDEO_PACKAGED=1 \
TURBO_VIDEO_APP_SUPPORT="$IMPORT_SMOKE_ROOT/Application Support" \
TURBO_VIDEO_CACHE="$IMPORT_SMOKE_ROOT/Caches" \
TURBO_VIDEO_LOGS="$IMPORT_SMOKE_ROOT/Logs" \
TURBO_VIDEO_EXPORTS="$IMPORT_SMOKE_ROOT/Exports" \
TURBO_VIDEO_CONFIG_PATH="$IMPORT_SMOKE_ROOT/Application Support/config.toml" \
"$APP_PATH/Contents/MacOS/$APP_NAME" --turbo-video-import-smoke > "$BUILD_ROOT/packaged-import-smoke.json"
grep -q '"app.models.llm_provider"' "$BUILD_ROOT/packaged-import-smoke.json" || fail "Packaged import smoke did not load llm_provider."
grep -q '"app.services.video"' "$BUILD_ROOT/packaged-import-smoke.json" || fail "Packaged import smoke did not load video service."

# Require that neither the active development configuration nor any archive music
# has entered the application package.
if find "$APP_PATH" -type f \( -name 'config.toml' -o -path '*resource/songs/*' \) | grep -q .; then
  fail "A mutable configuration or music file was detected in the app bundle."
fi

MANIFEST="$DIST/BUILD-MANIFEST.txt"
{
  print -- "Turbo Video build manifest"
  print -- "Version: $VERSION"
  print -- "Architecture: $(uname -m)"
  print -- "Bundle identifier: au.com.raineandhorne.essendon.turbovideo"
  print -- "Build timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  print -- "Signing: $SIGNING_STATUS"
  print -- "FFmpeg: $($FFMPEG_SOURCE -version 2>/dev/null | head -n 1)"
  print -- "FFprobe: $($FFPROBE_SOURCE -version 2>/dev/null | head -n 1)"
  print -- "Bundle size: $(du -sh "$APP_PATH" | awk '{print $1}')"
  print -- "App SHA-256 inventory:"
  find "$APP_PATH" -maxdepth 6 -type f -print0 | sort -z | xargs -0 shasum -a 256
} > "$MANIFEST"

DMG_STAGING="$BUILD_ROOT/dmg"
mkdir -p "$DMG_STAGING"
cp -R "$APP_PATH" "$DMG_STAGING/"
[[ -f "$ROOT/desktop/docs/INSTALL.md" ]] && cp "$ROOT/desktop/docs/INSTALL.md" "$DMG_STAGING/Read Me.md"
hdiutil create -volname "Turbo Video" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_PATH" >/dev/null

print -- "Built application: $APP_PATH"
print -- "Built disk image: $DMG_PATH"
print -- "Build manifest: $MANIFEST"
