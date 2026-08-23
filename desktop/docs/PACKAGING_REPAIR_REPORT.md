# Turbo Video — Packaging Import Repair Report

## Root cause

The source file `app/models/llm_provider.py` **exists**. It was not available to the failing package at a physical bundle location. The broken bundle did not contain `Turbo Video.app/Contents/Frameworks/app/models/llm_provider.py`, and inspection of its PyInstaller `PYZ` archive showed that the `app` collection contained only a small subset of first-party modules, such as `app.config`, `app.models.const`, `app.models.schema`, and `app.services.video`. It did **not** contain `app.models.llm_provider`, `app.services.rh_essendon`, `app.services.material`, or `app.services.task`.

The actual defect was therefore incomplete first-party module collection, not a missing source file, API configuration problem, package initialisation problem, or a macOS App Translocation defect. The previous command-line packaging approach relied on PyInstaller analysis plus an incomplete collection result, leaving runtime-selected provider modules out of the archive. The bundle also lacked an auditable physical first-party source tree, so startup could not independently prove that the local MoneyPrinterTurbo `app` package, rather than a third-party package named `app`, took precedence.

| Audit question | Finding |
|---|---|
| Does source `app/models/llm_provider.py` exist? | **Yes**. |
| Did the broken bundle expose it physically? | **No**. |
| Did the broken PYZ archive contain it? | **No**. |
| Are `app/__init__.py` and `app/models/__init__.py` present in source? | **Yes**. |
| Is `app.controllers` a namespace-style directory? | **Yes**; the smoke test validates its physical namespace location. |
| Did first-party warning scanning identify unresolved `app.*` imports in the repaired build? | **No**. |
| Does the repair use `Path.cwd()`, the development repository, Homebrew Python, or `PYTHONPATH`? | **No**. |

## Repair applied

The package build now uses `desktop/build/TurboVideo.spec` rather than a fragile expanding command-line list. The specification adds the repository root to `pathex`, uses `collect_submodules("app")`, collects Streamlit and renderer runtime package data and metadata, and stages a full physical copy of the first-party `app` tree under:

```text
Turbo Video.app/Contents/Resources/first_party/app
```

That physical tree includes all `app` packages and submodules, including models, services, configuration, controllers, dynamic providers, voice services, subtitles, R&H services, media services, and task modules. The full `webui` tree and required non-Python data are staged separately.

The desktop launcher now derives the bundle resource root from `sys.executable` and inserts the verified physical `first_party` location at the beginning of `sys.path` before importing `app.utils.runtime_paths` or starting Streamlit. The Streamlit entrypoint consumes the exported verified location and likewise puts it first on `sys.path`. This prevents a third-party package named `app` from shadowing MoneyPrinterTurbo’s package and works for `/Applications`, arbitrary working directories, App Translocation, and user paths containing spaces.

The build fails if `app.models.llm_provider.py` is absent, if PyInstaller’s warning report contains an unresolved `app.*` module, or if the exact bundled executable cannot import the maintained first-party manifest. Module locations are printed only by the build-only `--turbo-video-import-smoke` diagnostic, never by normal user-facing startup.

## Packaged import validation

The exact executable inside the finished application was run with `--turbo-video-import-smoke`. It recursively imports the physical `app` tree, parses every first-party import declared by `webui/Main.py`, and validates that the resolved location is inside the bundle. The required modules resolved successfully from:

```text
/Applications/Turbo Video.app/Contents/Resources/first_party/app/...
```

The verified set includes `app`, `app.models`, `app.models.llm_provider`, `app.services.rh_essendon`, `app.services.material`, `app.services.task`, `app.services.video`, `app.services.voice`, `app.services.subtitle`, `app.config.config`, and every discoverable `app` submodule.

## Installed and translocated launch validation

A copy of the repaired application was installed at:

```text
/Applications/Turbo Video.app
```

It was opened through macOS, which launched it from an App Translocation path. The managed backend started successfully from the translocated bundle, bound only to `127.0.0.1` on a dynamic port, and returned `ok` from the Streamlit health endpoint. This directly validates that the repair is not dependent on the development repository or a fixed installation path.

The installed executable was then run from an arbitrary working directory with `PYTHONPATH` cleared and a temporary writable profile whose path contained spaces. The import diagnostic confirmed that `app.models.llm_provider` and the required service modules resolved from `/Applications/Turbo Video.app/Contents/Resources/first_party`, not from the repository or development environment.

A local no-provider branded render also completed through the installed executable. It produced both personal and office contact-card H.264/AAC 1080×1920 MP4 outputs, with no LLM, search, TTS, or external provider call.

## Tests and deliverables

| Check | Result |
|---|---|
| Focused packaging and R&H regression suite | **27 passed**. |
| Exact packaged import smoke | **Passed**. |
| Source `llm_provider.py` physical bundle check | **Passed**. |
| Installed `/Applications` App Translocation launch | **Passed**. |
| Local package render smoke | **Passed**. |
| `codesign --verify --deep --strict` | **Passed**. |
| `git diff --check` | **Passed**. |
| Bundle configuration/music exclusion | **Passed**: no working `config.toml` or user music was bundled. |
| Credential-pattern scan of final app | **Passed**: no matching real API-key patterns found. |
| Full project suite | **597 passed, 36 failed, 11 skipped**. The 36 failures are existing WebUI widget assertions in background-music, LoomLoom, TTS settings, and voice-preview test groups; they reproduced in isolation and are not import/package failures. The packaging-specific and affected R&H suites pass. |

The final application and disk image are:

```text
/Users/jaydenmanno/AI/MoneyPrinterTurbo/desktop/dist/Turbo Video.app
/Users/jaydenmanno/AI/MoneyPrinterTurbo/desktop/dist/Turbo-Video-1.0.0-arm64.dmg
```

## Replacement installation instructions

1. Open `Turbo-Video-1.0.0-arm64.dmg`.
2. Drag **Turbo Video.app** into `/Applications`.
3. Eject the Turbo Video disk image.
4. Launch **Turbo Video** from `/Applications`.

The application is ad-hoc signed rather than Developer ID notarised. If Gatekeeper blocks the first launch, Control-click the app in Finder and choose **Open**, or use the app-specific **Open Anyway** control under **System Settings → Privacy & Security**. Do not disable Gatekeeper globally.
