# Turbo Video Desktop Architecture

## Selected approach

Turbo Video will use a **PyInstaller one-directory macOS application bundle** containing the existing Python/Streamlit backend, immutable branding resources, a controlled FFmpeg/FFprobe runtime, and a small **PyWebView Cocoa shell**. The shell owns the application lifecycle and displays the existing Streamlit UI inside a native macOS window backed by WKWebView. This preserves the customised business and rendering logic rather than rewriting it.

| Component | Responsibility | Rationale |
|---|---|---|
| PyInstaller | Produces `Turbo Video.app` for Apple Silicon and bundles Python dependencies, source, resources, and the native shell. | A local feasibility build produced a valid Apple Silicon macOS application bundle. |
| PyWebView Cocoa | Creates the visible native macOS window, standard window behaviour, lifecycle events, and application menus. | The feasibility harness started the existing Streamlit interface in a native WKWebView window without browser chrome. |
| Streamlit | Remains the local application backend and UI renderer. | It preserves all existing R&H Simple Mode, Advanced Mode, task, provider, and rendering customisations. |
| Central runtime-path module | Resolves immutable bundle resources separately from Application Support, caches, logs, exports, and temporary task files. | It removes repository-current-directory assumptions while retaining development-mode paths. |
| Desktop launcher | Acquires a single-instance lock, generates a local launch token, reserves a localhost port, starts Streamlit, waits for readiness, then loads the tokenised local URL. | It prevents orphan backends and avoids a network-exposed service. |
| Controlled media runtime | Resolves FFmpeg and FFprobe from bundled `Contents/Resources/bin` first; development mode retains the existing compatible resolver. | Ordinary installed use must not depend on Homebrew or shell `PATH`. |

## Security and storage boundaries

The Streamlit backend will bind only to `127.0.0.1` on a dynamically selected port. The desktop launcher will generate a per-launch random token and the backend will validate it before allowing normal UI content. Browser auto-launch and telemetry remain disabled.

| Data class | Location | Policy |
|---|---|---|
| Immutable code and official assets | `Turbo Video.app/Contents/Resources` | Bundled read-only; no credentials or mutable project data. |
| User configuration | `~/Library/Application Support/Turbo Video/config.toml` | Copied from a detected development installation only after a safe first-launch migration; mode `0600`. |
| User music | `~/Library/Application Support/Turbo Video/Music` | Eligible top-level development tracks are copied, never moved; archived nested tracks are excluded. |
| Projects and task metadata | `~/Library/Application Support/Turbo Video/Projects` | Persistent and user-owned. |
| Logs | `~/Library/Logs/Turbo Video` | Redacted diagnostic records only. |
| Cache | `~/Library/Caches/Turbo Video` | Safely clearable. |
| Temporary renders | Per-task macOS temporary directories | Cleaned only after successful completion. |
| Finished videos | `~/Movies/Turbo Video` by default, with native reveal/save actions | Persistent user-visible exports. |

## Feasibility evidence

The selected Python environment was extended with PyWebView 5.4 and PyInstaller 6.16.0. A native-window harness started the existing Streamlit UI on a dynamically selected `127.0.0.1` port, waited for Streamlit’s health endpoint, displayed it using the Cocoa webview backend, and shut down its child backend. A PyInstaller one-directory feasibility bundle was built successfully; it is an Apple Silicon Mach-O application, approximately 37 MB, and passed deep signature verification with the tool’s ad-hoc signature.

This is an architecture feasibility result, not yet the final product build. The final package must additionally include the customised application source, resources, media tools, migration flow, and full lifecycle logic.

## Packaging and signing strategy

The deliverable will target **Apple Silicon** because the connected Mac is `arm64`. No Intel or universal compatibility will be claimed without a separate tested build. A signing identity is available on this Mac, but identity material and name will not be exposed. The final build will attempt proper nested signing and verification. Notarisation will be performed only if existing authorised credentials are already configured; otherwise the final report will state the real Gatekeeper first-open limitation.

## Why alternatives were not selected

A browser shortcut or shell launcher would fail the native-window requirement. Electron or Tauri would require a parallel frontend and potentially duplicate lifecycle work without improving preservation of the existing Python/Streamlit logic. Briefcase was not selected because the tested PyInstaller and PyWebView combination already produces a valid Apple Silicon Cocoa bundle and can keep the implementation in the current Python environment.
