#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/desktop/dist/Turbo Video.app"
CAPTURE="$ROOT/desktop/build/package-visual-smoke.png"
TEMP_ROOT="$(mktemp -d -t turbo-video-visual)"
cleanup() {
  osascript -e 'tell application id "au.com.raineandhorne.essendon.turbovideo" to quit' >/dev/null 2>&1 || true
  sleep 3
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT

export TURBO_VIDEO_APP_SUPPORT="$TEMP_ROOT/Application Support"
export TURBO_VIDEO_CACHE="$TEMP_ROOT/Caches"
export TURBO_VIDEO_LOGS="$TEMP_ROOT/Logs"
export TURBO_VIDEO_EXPORTS="$TEMP_ROOT/Exports"
export TURBO_VIDEO_CONFIG_PATH="$TEMP_ROOT/Application Support/config.toml"
export TURBO_VIDEO_MIGRATION_SOURCE="$TEMP_ROOT/no-legacy-installation"
open -n "$APP"
sleep 18
screencapture -x "$CAPTURE"
test -s "$CAPTURE"
print -- "$CAPTURE"
