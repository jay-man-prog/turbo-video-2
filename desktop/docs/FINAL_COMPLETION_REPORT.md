# Turbo Video 1.0.0 — Completion Report

## Delivery summary

Turbo Video has been built as a self-contained **Apple Silicon macOS desktop application**. It preserves the customised MoneyPrinterTurbo application logic, presents the existing Streamlit interface in a native PyWebView Cocoa window, starts and manages its own localhost-only backend, and includes a distributable disk image.

| Item | Final result |
|---|---|
| Source repository used | `/Users/jaydenmanno/AI/MoneyPrinterTurbo` |
| Application name | Turbo Video |
| Bundle identifier | `au.com.raineandhorne.essendon.turbovideo` |
| Application version | `1.0.0` |
| Supported architecture | Apple Silicon (`arm64`) only; the connected Mac is arm64. No Intel or universal claim is made because another Mac architecture was not available for verification. |
| Application artifact | `desktop/dist/Turbo Video.app` |
| Installer artifact | `desktop/dist/Turbo-Video-1.0.0-arm64.dmg` |
| Bundle / installer size | 773 MB / 405 MB |
| Signing | Ad-hoc signed and verified. A Developer ID Application identity was not available, so the artifact is not notarised. |
| Bundle verification | `codesign --verify --deep --strict` passed; `hdiutil verify` passed. |
| Credential and mutable-data exclusion | The final bundle contains zero `config.toml` files and zero files under `resource/songs`. |

## Safe baseline and source preservation

The customised local repository was used as the source of truth. No upstream pull, reset, rebase, checkout-overwrite, commit, or push was performed. The original pre-existing Git modifications and untracked R&H, music, runtime-path, desktop, and test work were preserved.

A protected reversible checkpoint was created before edits:

```text
/Users/jaydenmanno/AI/MoneyPrinterTurbo-checkpoints/Turbo-Video-prepackage-20260822-194958
```

It contains the baseline Git status, binary working-tree patch, staged patch, restore notes, and a 3,610,311,832-byte source snapshot. Its SHA-256 is:

```text
dccead8ba5ca43f7b28c984a53b0a502be55e34c36dedf835f23073c5d14b515
```

## Selected desktop architecture

Turbo Video uses a **PyInstaller one-directory macOS bundle** containing the existing Python and Streamlit application, official immutable assets, a controlled FFmpeg/FFprobe runtime, and a PyWebView Cocoa shell. The shell chooses a free port, launches Streamlit on `127.0.0.1`, provides a per-launch URL token, waits on the local health endpoint, and closes its managed backend on application shutdown.

This route was retained because it preserves the existing R&H Simple Mode, Advanced Mode, task handling, provider integration, rendering pipeline, branding, music selection, subtitles, and contact-card logic without rewriting the working application in another frontend technology. The native window has no browser toolbar, address bar, or tabs.

The following packaging and identity adjustments were completed in this pass:

| Area | Completion |
|---|---|
| Desktop-facing identity | The packaged interface now displays **Turbo Video v1.0.0** rather than the legacy application title. Packaged builds do not poll or advertise upstream MoneyPrinterTurbo updates. |
| Version source | `app.utils.runtime_paths.APP_VERSION` is the central version constant. The launcher and repeatable build script derive their displayed / artifact version from it. |
| Asset record | Added `desktop/docs/ASSET_MANIFEST.md`, documenting current opening, watermark, portrait closing, fonts, packaged locations, and user-music handling. |
| Visual quality record | Added `desktop/docs/VISUAL_QA.md` and captured `desktop/build/qa/turbo-video-home-final.png`. |
| Regression coverage | Added a focused desktop identity regression assertion, while preserving the existing desktop, R&H, video, material, task, voice, and UI regression tests. |

## Runtime locations and migration

The immutable application bundle contains official brand assets and the controlled media tools. It contains neither real configuration values nor mutable user music. On first launch, Turbo Video creates the following per-user writable locations:

| Purpose | Location |
|---|---|
| Configuration | `~/Library/Application Support/Turbo Video/config.toml` |
| User music | `~/Library/Application Support/Turbo Video/Music` |
| Projects and task metadata | `~/Library/Application Support/Turbo Video/Projects` |
| Cache | `~/Library/Caches/Turbo Video` |
| Logs | `~/Library/Logs/Turbo Video` |
| Finished videos | `~/Movies/Turbo Video` |

When a development installation is found, first launch asks before copying, never moving, its configuration, eligible top-level music, and saved projects. The migration uses private permissions for configuration and excludes nested folders, archived music, hidden files, unsupported extensions, and unreadable tracks. No real configuration or music was imported during the isolated tests, so your existing development data remains untouched. The automated migration test confirms fixture configuration and projects copy correctly, while an archived fixture track remains excluded.

## Branding, media, and product behaviour preserved

The packaged renderer continues to use the approved R&H assets and the existing portrait pipeline. Its R&H Simple Mode default remains selected, Advanced Mode remains available, and the visible final-contact-card default remains **Jayden Manno — Director and Auctioneer**. The local smoke renderer successfully generated both `jayden_manno` and `rh_essendon_office` branded variants without LLM, stock-footage, text-to-speech, or other provider calls.

The bundle packages FFmpeg and FFprobe under `Contents/Resources/bin`, resolves them through the central runtime-path layer, and does not require Homebrew or a shell `PATH` for normal installed use. The earlier packaged smoke inspection verified H.264 video, AAC audio, and exact 1080 × 1920 output for both final-contact-card variants; the final post-build smoke render again completed both variants in the rebuilt bundle.

## Test and QA evidence

| Check | Result |
|---|---|
| Pre-edit focused baseline | 210 passed, 6 skipped, 12 warnings, 50 subtests passed in 12.69 seconds. |
| Post-edit focused suite | 211 passed, 6 skipped, 12 warnings, 50 subtests passed in 12.03 seconds. |
| Rebuilt bundle signature | Passed `codesign --verify --deep --strict`. |
| Rebuilt DMG integrity | Passed `hdiutil verify`. |
| Packaging security check | Zero active configuration files and zero `resource/songs` files in the bundle. |
| Packaged import smoke | Passed during the repeatable build. |
| Final no-provider render smoke | Passed for both personal and office contact-card variants. |
| Native-window visual QA | Passed for the home screen; no browser chrome, Turbo Video title/version, R&H Simple Mode default, readable controls, and readable contact-card selector. |
| Process QA | The isolated visual-QA launcher and its managed backend were terminated after capture; no isolated QA process remained. |
| Source whitespace integrity | `git diff --check` passed. |

Build artifact hashes are recorded for traceability:

```text
Turbo Video.app archive SHA-256: 20d89b911f950405b29743e90bb261ee7c1d7e0e491f931b8fcc838d19d2262d
Turbo-Video-1.0.0-arm64.dmg SHA-256: c5faffff688c665896e3408a8c0eab4d24bec744cb30db7a10f0cdd47aaf8a6c
```

## Installation and first launch

1. Open `Turbo-Video-1.0.0-arm64.dmg` in Finder.
2. Drag **Turbo Video.app** to `/Applications`.
3. Eject the disk image.
4. Open **Turbo Video** from `/Applications`.
5. On first launch, accept the optional import prompt if you want to copy the current MoneyPrinterTurbo configuration, eligible top-level music, and existing project files. The original installation is not changed.
6. If macOS blocks first launch, Control-click **Turbo Video.app** in Finder and choose **Open**, or use the application-specific **Open Anyway** control in **System Settings → Privacy & Security**. Do not disable Gatekeeper globally.

Within the app menu, choose **File → Open Music Folder**, **File → Open Projects Folder**, or **File → Open Finished Videos**. The **File → Save Video As…** action copies the most recent completed MP4 to a location selected with a native save dialog.

## Uninstalling without deleting projects

Move `Turbo Video.app` from `/Applications` to the Bin and remove the `.dmg` if it is no longer needed. This does **not** delete configuration, music, projects, logs, or finished videos. Remove those locations manually only if you explicitly intend to erase your Turbo Video data.

## Remaining limitation and recommended next improvement

The deliverable is correctly structured and ad-hoc signed for local use but is **not Developer ID signed or notarised**. This is the genuine reason macOS may show an initial Gatekeeper warning. The next improvement is to obtain and configure a Developer ID Application certificate and authorised notarisation credentials, then rebuild and notarise this same tested bundle; no product rewrite is required.

The final installer is ready at `desktop/dist/Turbo-Video-1.0.0-arm64.dmg`.
