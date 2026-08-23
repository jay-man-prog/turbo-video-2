# -*- mode: python ; coding: utf-8 -*-
"""Deterministic PyInstaller specification for the Turbo Video macOS bundle."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata


ROOT = Path(SPECPATH).resolve().parents[1]
STAGE = ROOT / "desktop" / "build" / "final" / "stage"
APP_NAME = "Turbo Video"
BUNDLE_ID = "au.com.raineandhorne.essendon.turbovideo"
FIRST_PARTY_DESTINATION = "first_party"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def staged_tree(source: Path, destination: str) -> list[tuple[str, str]]:
    """Collect every staged source file under an explicit relative destination."""

    if not source.is_dir():
        raise SystemExit(f"Missing required staged directory: {source}")
    return [
        (str(path), str(Path(destination) / path.relative_to(source).parent))
        for path in source.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]


def staged_file(source: Path, destination: str) -> tuple[str, str]:
    if not source.is_file():
        raise SystemExit(f"Missing required staged file: {source}")
    return str(source), destination


# This physical source tree is deliberately bundled independently of PYZ. The
# launcher prepends it to sys.path before importing any first-party code, making
# the source location auditable and preventing a third-party ``app`` package from
# taking precedence. ``collect_submodules`` also covers Python imports PyInstaller
# cannot infer from runtime provider selection.
datas: list[tuple[str, str]] = []
datas += staged_tree(STAGE / "first_party", FIRST_PARTY_DESTINATION)
datas += staged_tree(STAGE / "webui", "webui")
datas += staged_tree(STAGE / "resource", "resource")
datas += staged_tree(STAGE / "bin", "bin")
datas += staged_tree(STAGE / "lib", "lib")
datas += staged_tree(STAGE / "licenses", "licenses")
datas.append(staged_file(STAGE / "config.example.toml", "."))

hiddenimports = set(collect_submodules("app"))
hiddenimports.update(
    {
        "streamlit.web.cli",
        "streamlit.runtime",
        "imageio_ffmpeg",
    }
)
binaries: list[tuple[str, str]] = []
for package in ("webview", "streamlit", "streamlit_tour", "moviepy", "imageio", "imageio_ffmpeg"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports.update(package_hiddenimports)
for package in ("streamlit", "streamlit_tour", "moviepy", "imageio", "imageio_ffmpeg"):
    datas += copy_metadata(package)

analysis = Analysis(
    [str(ROOT / "desktop" / "turbo_video_desktop.py")],
    pathex=[str(ROOT), str(STAGE / FIRST_PARTY_DESTINATION)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(hiddenimports),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(STAGE / "TurboVideo.icns"),
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=str(STAGE / "TurboVideo.icns"),
    bundle_identifier=BUNDLE_ID,
)
