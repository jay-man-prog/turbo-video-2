#!/usr/bin/env bash
set -euo pipefail

: "${RENDERER_SERVICE_TOKEN:?Set RENDERER_SERVICE_TOKEN before starting the renderer}"
export LISTEN_HOST="${LISTEN_HOST:-0.0.0.0}"
export PORT="${PORT:-8080}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg is required. Install it before starting Turbo Video Manus." >&2
  exit 1
fi

# The upstream app reads listen_port from config.toml. Keep the default 8080,
# or set listen_port there to match PORT before launching on another host.
exec uv run python main.py
