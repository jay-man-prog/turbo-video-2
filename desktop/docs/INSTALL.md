# Turbo Video 1.0.0 — Installation and First Launch

## Install on this Mac

Use the following installation sequence exactly: **(1)** open `Turbo-Video-1.0.0-arm64.dmg`; **(2)** drag **Turbo Video.app** into `/Applications`; **(3)** eject the Turbo Video disk image; and **(4)** launch **Turbo Video** from `/Applications`. This build targets Apple Silicon Macs only. It is a self-contained local application: normal use does not require Terminal, Homebrew, a browser tab, or an already-running Streamlit process.

The application is locally ad-hoc signed rather than notarised. macOS may therefore block the first launch. Do **not** disable Gatekeeper globally. Instead, in Finder, Control-click **Turbo Video.app**, choose **Open**, then confirm **Open** in the macOS dialog. If macOS still blocks it, use **System Settings → Privacy & Security → Open Anyway** for this application only.

## First launch and migration

On its first launch, Turbo Video creates the following private writable locations. The app bundle itself remains read-only after installation.

| Purpose | Location |
|---|---|
| Configuration | `~/Library/Application Support/Turbo Video/config.toml` |
| User music | `~/Library/Application Support/Turbo Video/Music` |
| Projects and task metadata | `~/Library/Application Support/Turbo Video/Projects` |
| Cache | `~/Library/Caches/Turbo Video` |
| Logs | `~/Library/Logs/Turbo Video` |
| Default exports | `~/Movies/Turbo Video` |

When it finds `~/AI/MoneyPrinterTurbo`, Turbo Video asks whether to import existing data. The import copies the working configuration, eligible top-level music tracks, and task project files; it never moves or deletes originals. The music importer includes only readable top-level `.mp3`, `.wav`, and `.m4a` files. It excludes hidden files, unsupported files, nested directories, and the archived music directory. Existing same-named destination tracks are retained rather than overwritten.

> **Credentials remain local.** The migration UI reports only connected/not-connected or file-count status. It never displays API-key values, and no working `config.toml` is embedded in the app or DMG.

## Everyday use

Open **Turbo Video** from Applications. The native window starts and manages a localhost-only backend automatically, with no external browser chrome. R&H Essendon Simple Mode remains the default workflow; Advanced Mode remains available.

The native menus provide **Open Projects Folder**, **Open Music Folder**, **Open Finished Videos**, **Save Video As…**, **Reload Interface**, **Restart Local Backend**, **View Logs**, and safe diagnostic information. Completed projects are preserved separately from temporary render work.

## Move to another Apple Silicon Mac

Copy the DMG to the other Mac and repeat the installation. On first launch there, Turbo Video independently offers to import that Mac’s local MoneyPrinterTurbo configuration, eligible music, and projects. It does not transfer credentials, music, projects, or absolute paths between Macs.

## Uninstall without deleting projects

Quit Turbo Video, then move **Turbo Video.app** from Applications to the Bin and empty the Bin. This does **not** remove your configuration, music, projects, logs, cache, or finished videos.

If you deliberately want to erase user data after making your own backup, remove only the following folders manually:

```text
~/Library/Application Support/Turbo Video
~/Library/Caches/Turbo Video
~/Library/Logs/Turbo Video
~/Movies/Turbo Video
```

Do not remove your original `~/AI/MoneyPrinterTurbo` installation until Turbo Video has been accepted and its migration has been confirmed.

## Licence notices

The application bundle includes the original MoneyPrinterTurbo MIT licence and FFmpeg licence notices under `Turbo Video.app/Contents/Resources/licenses`. The bundled FFmpeg and FFprobe runtime is version 9.0.1; its notices are included in the bundle and build manifest.
