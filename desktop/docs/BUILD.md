# Turbo Video — Build and Verification Guide

## Requirements

Build on an Apple Silicon Mac with the project’s locked `uv` environment, FFmpeg and FFprobe available at the controlled build paths, `dylibbundler`, Xcode command-line signing tools, and `hdiutil`. The build dependencies are pinned in the `desktop` dependency group of `pyproject.toml` and the repository `uv.lock`.

The build script targets `arm64` only. Do not label the result universal or Intel-compatible without a separately tested build.

## Standard maintenance commands

| Task | Command |
|---|---|
| Run the development UI | `./webui.sh` |
| Run desktop-focused tests | `.venv/bin/python -m pytest -q test/test_desktop_runtime.py` |
| Run relevant product regression tests | `.venv/bin/python -m pytest -q test/services/test_rh_essendon_simple.py test/services/test_rh_essendon_branding.py test/services/test_rh_music_selection.py test/services/test_webui_rh_simple_mode.py test/services/test_webui_generation_defaults.py test/services/test_video.py test/services/test_material.py test/services/test_task.py` |
| Build the app and DMG | `desktop/build/build_turbo_video.sh` |
| Run package backend smoke test | `.venv/bin/python desktop/build/package_backend_smoke.py` |
| Inspect the final manifest | `sed -n '1,80p' desktop/dist/BUILD-MANIFEST.txt` |

The build creates `desktop/dist/Turbo Video.app`, `desktop/dist/Turbo-Video-1.0.0-arm64.dmg`, and `desktop/dist/BUILD-MANIFEST.txt`. It stages official resources and licence notices, excludes the complete `resource/songs` directory and `config.toml`, bundles controlled FFmpeg and FFprobe executables with their dynamic-library closure, verifies nested signatures, and produces a manifest including build time, architecture, signing status, media-runtime versions, bundle size, and SHA-256 inventory.

## Controlled clean

The build script itself safely removes only `desktop/build/final` and `desktop/dist` before rebuilding. For a manual clean, run:

```sh
rm -rf desktop/build/final desktop/dist
```

Do not use broad cleanup commands against the repository root, the `storage` directory, the working configuration, or Application Support folders.

## Signing and notarisation

The build script uses a pre-existing **Developer ID Application** identity only when one is already available. Otherwise it creates a functioning ad-hoc-signed local build. It verifies the resulting bundle with:

```sh
codesign --verify --deep --strict --verbose=2 "desktop/dist/Turbo Video.app"
```

Notarisation is intentionally not attempted without separately authorised Apple credentials. In that case, first-open Gatekeeper handling is described in `INSTALL.md`.

## Functional verification scope

The package smoke test verifies that the bundled executable launches Streamlit from the managed app process, binds only to `127.0.0.1` on a dynamic port, and responds to the desktop launch token. The local renderer smoke verifier creates two 1080×1920 H.264/AAC MP4s using generated local test footage, sine-wave narration, local music, and the actual branded renderer: one with `jayden_manno` and one with `rh_essendon_office`. It does not call LLM, Pexels, ElevenLabs, Azure, or any paid provider.
