# Turbo Video Desktop Conversion — Pre-change Audit

**Repository:** `/Users/jaydenmanno/AI/MoneyPrinterTurbo`  
**Checkpoint:** `../TurboVideo-checkpoints/pre-desktop-20260822-173743`  
**Platform:** macOS 26.5.2 on Apple Silicon (`arm64`)  
**Baseline executed:** 22 August 2026

## Preservation status

The working tree already contained customised tracked changes and untracked R&H branding, music, helper, and regression-test assets. No Git reset, checkout, pull, rebase, commit, push, or modification of `config.toml` was performed. The checkpoint stores the pre-change Git HEAD, status, tracked binary patch, staged patch, and a compressed untracked-file archive with owner-only permissions.

The relevant existing regression suite completed successfully before desktop work began: **131 passed, 3 skipped**. The suite emitted eleven pre-existing Pydantic deprecation warnings and one existing serialization warning; it produced no failures.

| Area | Verified current behaviour | Primary pull points |
|---|---|---|
| Default workflow | `R&H Essendon Simple Mode` is the selected default and sets branded portrait behaviour. | `webui/Main.py` |
| Project model | R&H fields, including contact-card identifier, music selections, visual plan, and portrait aspect, are persisted in task parameters. | `app/models/schema.py` |
| Task pipeline | Music is selected once per R&H task; task metadata records music and contact-card choices; semantic visual planning feeds script-ordered material acquisition and rendering. | `app/services/task.py`, `app/services/rh_essendon.py`, `app/services/material.py` |
| Video renderer | Portrait branded output applies the opening, watermark, subtitle treatment, selectable closing card, narration offset, music ducking, and two-second end fade. | `app/services/video.py` |
| Existing backend launcher | `webui.sh` already starts Streamlit on `127.0.0.1`, probes a free local port, suppresses browser auto-open, and disables telemetry. It is not a packaged desktop app. | `webui.sh` |
| Runtime paths | Existing helpers resolve resources and task storage relative to the repository, which must be replaced by a central development-versus-packaged path layer. | `app/utils/utils.py`, `app/config/config.py` |

## Asset manifest

The table identifies the fixed runtime assets used by the existing R&H portrait brand layer. All paths are repository-relative in development mode; packaged mode must resolve immutable assets from the bundle and mutable data from Application Support.

| Logical purpose | Existing source path | Type and verified properties | Bundle policy | Packaged runtime resolution |
|---|---|---|---|---|
| Branded opening | `resource/branding/Ampersand animation_without bg.mov` | ProRes MOV, 2417×2417, approximately 5.005 seconds | Read-only bundled | `Resources/resource/branding/...` via central path layer |
| Gold watermark | `resource/branding/Ampersand-Gold-RGB.png` | PNG, 480×542 | Read-only bundled | `Resources/resource/branding/...` via central path layer |
| Branded closing card base | `resource/branding/R&H_Charcoal 1080 x 1920 portrait.mp4` | H.264 MP4, 1080×1920, approximately 5.005 seconds | Read-only bundled | `Resources/resource/branding/...` via central path layer |
| R&H headline font | `resource/fonts/Raine&Horne-Thin.ttf` | TrueType | Read-only bundled | `Resources/resource/fonts/...` via central path layer |
| R&H secondary font | `resource/fonts/Raine&HorneLight.ttf` | OpenType | Read-only bundled | `Resources/resource/fonts/...` via central path layer |
| R&H subtitle font | `resource/fonts/Raine&HorneRegular.ttf` | OpenType | Read-only bundled | `Resources/resource/fonts/...` via central path layer |
| User background music | Eligible top-level files in `resource/songs` | Eleven readable MP3 files were verified. Hidden files and the nested `Archived music` directory are excluded. | User-replaceable, not used from the signed bundle after migration | `~/Library/Application Support/Turbo Video/Music` |
| Configuration | `config.toml` when present | Secret-bearing TOML; intentionally not read, copied, committed, or bundled | User-owned and restricted | `~/Library/Application Support/Turbo Video/config.toml` |
| Task projects and metadata | `storage/tasks` | Mutable project state and render artifacts | User-owned | `~/Library/Application Support/Turbo Video/Projects` |

## Current desktop-relevant constraints

The installed environment has an Apple Silicon Homebrew FFmpeg and FFprobe at `/opt/homebrew/bin/ffmpeg` and `/opt/homebrew/bin/ffprobe`, macOS packaging utilities (`codesign`, `hdiutil`), and one valid signing identity. The final build must nevertheless avoid relying on Homebrew at ordinary runtime. The desktop wrapper must package or otherwise control its media executables and must not ship the working configuration or any credentials.

No existing `*.app`, Finder launcher, or `.command` launcher was found within the repository. The existing `webui.sh` remains untouched and will continue to serve development use only.

## Baseline test command

```sh
.venv/bin/python -m pytest -q \
  test/services/test_rh_essendon_simple.py \
  test/services/test_rh_essendon_branding.py \
  test/services/test_rh_music_selection.py \
  test/services/test_webui_rh_simple_mode.py \
  test/services/test_webui_generation_defaults.py \
  test/services/test_video.py \
  test/services/test_material.py \
  test/services/test_task.py
```

This command is mock- and fixture-based; no paid provider calls were made.
