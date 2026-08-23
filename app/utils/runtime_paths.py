"""Runtime paths and safe user-data migration for Turbo Video.

The original project runs directly from a repository.  Turbo Video additionally
runs from a read-only macOS app bundle, so all mutable data must be redirected to
standard per-user locations while official resources remain bundled.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


APP_NAME = "Turbo Video"
APP_VERSION = "1.0.0"
BUNDLE_IDENTIFIER = "au.com.raineandhorne.essendon.turbovideo"
_ENV_PACKAGED = "TURBO_VIDEO_PACKAGED"
_ENV_BUNDLE_ROOT = "TURBO_VIDEO_BUNDLE_ROOT"
_ENV_APP_SUPPORT = "TURBO_VIDEO_APP_SUPPORT"
_ENV_CACHE = "TURBO_VIDEO_CACHE"
_ENV_LOGS = "TURBO_VIDEO_LOGS"
_ENV_EXPORTS = "TURBO_VIDEO_EXPORTS"
_ENV_CONFIG = "TURBO_VIDEO_CONFIG_PATH"
_ENV_MIGRATION_SOURCE = "TURBO_VIDEO_MIGRATION_SOURCE"
_ENV_FFMPEG = "TURBO_VIDEO_FFMPEG"
_ENV_FFPROBE = "TURBO_VIDEO_FFPROBE"
_SUPPORTED_MUSIC_EXTENSIONS = {".mp3", ".wav", ".m4a"}


@dataclass(frozen=True)
class MigrationResult:
    """A secret-free summary of a legacy-installation import attempt."""

    source_found: bool
    source: str | None
    configuration_found: bool
    configuration_copied: bool
    eligible_music_tracks: int
    music_copied: int
    music_skipped_as_duplicates: int
    music_excluded: int
    projects_found: bool
    project_files_copied: int
    project_files_skipped: int
    destinations: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def is_packaged() -> bool:
    """Return whether the process is executing as a Turbo Video app bundle."""

    return os.environ.get(_ENV_PACKAGED) == "1" or bool(getattr(sys, "frozen", False))


def development_root() -> Path:
    """Return the source repository root without depending on the working directory."""

    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    """Return PyInstaller's immutable data root in packaged mode."""

    override = os.environ.get(_ENV_BUNDLE_ROOT)
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        # In a macOS one-directory PyInstaller app, user-added data is placed in
        # Contents/Frameworks. Resolving from the executable remains stable even
        # when PyInstaller changes its internal extraction path.
        executable = Path(sys.executable).resolve()
        if len(executable.parents) >= 2:
            frameworks = executable.parents[1] / "Frameworks"
            if frameworks.is_dir():
                return frameworks
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return development_root()


def _first_existing(candidates: Iterable[Path]) -> Path:
    candidates = tuple(candidates)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def resource_root() -> Path:
    """Locate immutable assets in the source tree or in the packaged bundle."""

    if not is_packaged():
        return development_root() / "resource"
    root = bundle_root()
    return _first_existing(
        (
            root / "resource",
            root.parent / "Resources" / "resource",
            root.parent / "Frameworks" / "resource",
        )
    )


def webui_root() -> Path:
    """Locate Streamlit styles and translations in source or packaged mode."""

    if not is_packaged():
        return development_root() / "webui"
    root = bundle_root()
    return _first_existing(
        (
            root / "webui",
            root.parent / "Resources" / "webui",
            root.parent / "Frameworks" / "webui",
        )
    )


def bundle_bin_dir() -> Path:
    """Locate package-controlled executable tools when running from the app bundle."""

    root = bundle_root()
    return _first_existing(
        (
            root / "bin",
            root.parent / "Resources" / "bin",
            root.parent / "Frameworks" / "bin",
        )
    )


def code_root() -> Path:
    """Return the immutable application root used for bundled read-only files."""

    return bundle_root() if is_packaged() else development_root()


def _configured_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


def application_support_dir(create: bool = False) -> Path:
    directory = _configured_path(
        _ENV_APP_SUPPORT,
        Path.home() / "Library" / "Application Support" / APP_NAME,
    )
    if create:
        _ensure_private_directory(directory)
    return directory


def cache_dir(create: bool = False) -> Path:
    directory = _configured_path(_ENV_CACHE, Path.home() / "Library" / "Caches" / APP_NAME)
    if create:
        _ensure_private_directory(directory)
    return directory


def logs_dir(create: bool = False) -> Path:
    directory = _configured_path(_ENV_LOGS, Path.home() / "Library" / "Logs" / APP_NAME)
    if create:
        _ensure_private_directory(directory)
    return directory


def projects_dir(create: bool = False) -> Path:
    directory = application_support_dir(create=create) / "Projects" if is_packaged() else development_root() / "storage"
    if create:
        _ensure_private_directory(directory) if is_packaged() else directory.mkdir(parents=True, exist_ok=True)
    return directory


def music_dir(create: bool = False) -> Path:
    directory = application_support_dir(create=create) / "Music" if is_packaged() else resource_root() / "songs"
    if create:
        _ensure_private_directory(directory) if is_packaged() else directory.mkdir(parents=True, exist_ok=True)
    return directory


def export_dir(create: bool = False) -> Path:
    directory = _configured_path(_ENV_EXPORTS, Path.home() / "Movies" / APP_NAME)
    if create:
        _ensure_private_directory(directory)
    return directory


def config_path(create_parent: bool = False) -> Path:
    override = os.environ.get(_ENV_CONFIG)
    if override:
        path = Path(override).expanduser().resolve()
    elif is_packaged():
        path = application_support_dir(create=create_parent) / "config.toml"
    else:
        path = development_root() / "config.toml"
    if create_parent:
        _ensure_private_directory(path.parent) if is_packaged() else path.parent.mkdir(parents=True, exist_ok=True)
    return path


def example_config_path() -> Path:
    """Locate the read-only example configuration across source and PyInstaller layouts."""

    if not is_packaged():
        return development_root() / "config.example.toml"
    root = bundle_root()
    candidates = [
        root / "config.example.toml",
        root / "config.example.toml" / "config.example.toml",
        root / "Resources" / "config.example.toml",
        root / "Resources" / "config.example.toml" / "config.example.toml",
        root / "Frameworks" / "config.example.toml",
        root / "Frameworks" / "config.example.toml" / "config.example.toml",
    ]
    for parent in root.parents:
        candidates.extend(
            (
                parent / "Resources" / "config.example.toml",
                parent / "Resources" / "config.example.toml" / "config.example.toml",
                parent / "Frameworks" / "config.example.toml",
                parent / "Frameworks" / "config.example.toml" / "config.example.toml",
            )
        )
        if parent.name == "Contents":
            break
    return _first_existing(candidates)


def task_temp_dir(task_id: str | None = None) -> Path:
    prefix = "turbo-video" if not task_id else f"turbo-video-{_safe_name(task_id)}"
    return Path(tempfile.mkdtemp(prefix=f"{prefix}-"))


def ffmpeg_path() -> Path | None:
    override = os.environ.get(_ENV_FFMPEG)
    if override:
        return Path(override).expanduser().resolve()
    if is_packaged():
        candidate = bundle_bin_dir() / "ffmpeg"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def ffprobe_path() -> Path | None:
    override = os.environ.get(_ENV_FFPROBE)
    if override:
        return Path(override).expanduser().resolve()
    if is_packaged():
        candidate = bundle_bin_dir() / "ffprobe"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def initialise_user_directories() -> dict[str, Path]:
    """Create only Turbo Video-owned writable directories with private permissions."""

    return {
        "application_support": application_support_dir(create=True),
        "projects": projects_dir(create=True),
        "music": music_dir(create=True),
        "cache": cache_dir(create=True),
        "logs": logs_dir(create=True),
        "exports": export_dir(create=True),
    }


def discover_legacy_installation() -> Path | None:
    """Find a conventional MoneyPrinterTurbo source installation without opening its config."""

    override = os.environ.get(_ENV_MIGRATION_SOURCE)
    candidates = [Path(override).expanduser()] if override else []
    candidates.append(Path.home() / "AI" / "MoneyPrinterTurbo")
    for candidate in candidates:
        if (candidate / "app").is_dir() and (candidate / "webui").is_dir() and (candidate / "resource").is_dir():
            return candidate.resolve()
    return None


def migrate_legacy_installation(source: Path | None = None, *, include_config: bool = True, include_music: bool = True, include_projects: bool = True) -> MigrationResult:
    """Copy eligible legacy data without moving, overwriting, or reading credentials.

    This function is deliberately opt-in. It returns a summary that is safe to
    show in the user interface and never includes TOML values, API keys, or file
    content.
    """

    source = source or discover_legacy_installation()
    destinations = {
        "configuration": str(config_path(create_parent=True)),
        "music": str(music_dir(create=True)),
        "projects": str(projects_dir(create=True)),
    }
    if source is None:
        return MigrationResult(False, None, False, False, 0, 0, 0, 0, False, 0, 0, destinations)

    source_config = source / "config.toml"
    configuration_found = source_config.is_file()
    configuration_copied = False
    if include_config and configuration_found and not config_path(create_parent=True).exists():
        shutil.copy2(source_config, config_path(create_parent=True))
        _make_private(config_path())
        configuration_copied = True

    eligible_music_tracks = 0
    music_copied = 0
    music_skipped = 0
    music_excluded = 0
    source_music = source / "resource" / "songs"
    if include_music and source_music.is_dir():
        for candidate in source_music.iterdir():
            if not candidate.is_file() or candidate.name.startswith("."):
                music_excluded += 1
                continue
            if candidate.suffix.lower() not in _SUPPORTED_MUSIC_EXTENSIONS or not _is_readable_audio(candidate):
                music_excluded += 1
                continue
            eligible_music_tracks += 1
            destination = music_dir(create=True) / candidate.name
            if destination.exists():
                music_skipped += 1
                continue
            shutil.copy2(candidate, destination)
            music_copied += 1

    projects_found = (source / "storage" / "tasks").is_dir()
    project_copied = 0
    project_skipped = 0
    if include_projects and projects_found:
        source_tasks = source / "storage" / "tasks"
        destination_tasks = projects_dir(create=True) / "tasks"
        for candidate in source_tasks.rglob("*"):
            if not candidate.is_file():
                continue
            destination = destination_tasks / candidate.relative_to(source_tasks)
            if destination.exists():
                project_skipped += 1
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, destination)
            project_copied += 1

    return MigrationResult(
        True,
        str(source),
        configuration_found,
        configuration_copied,
        eligible_music_tracks,
        music_copied,
        music_skipped,
        music_excluded,
        projects_found,
        project_copied,
        project_skipped,
        destinations,
    )


def _is_readable_audio(path: Path) -> bool:
    if not os.access(path, os.R_OK) or path.stat().st_size <= 0:
        return False
    probe = ffprobe_path() or _which_path("ffprobe")
    if probe is None:
        return True
    completed = subprocess.run(
        [str(probe), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return completed.returncode == 0 and bool(completed.stdout.strip())


def _which_path(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _make_private(path)


def _make_private(path: Path) -> None:
    try:
        path.chmod(stat.S_IRWXU)
    except OSError:
        pass


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "-" for character in value)[:80]


def file_digest(path: Path) -> str:
    """Return a SHA-256 digest for tests and explicit duplicate checks."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
