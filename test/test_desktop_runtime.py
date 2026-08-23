from __future__ import annotations

import os
import socket
from pathlib import Path

from app.utils import runtime_paths
from desktop.turbo_video_desktop import SingleInstanceLock, TurboVideoDesktop


def _configure_packaged_environment(monkeypatch, tmp_path: Path, bundle_root: Path) -> None:
    monkeypatch.setenv("TURBO_VIDEO_PACKAGED", "1")
    monkeypatch.setenv("TURBO_VIDEO_BUNDLE_ROOT", str(bundle_root))
    monkeypatch.setenv("TURBO_VIDEO_APP_SUPPORT", str(tmp_path / "Application Support"))
    monkeypatch.setenv("TURBO_VIDEO_CACHE", str(tmp_path / "Caches"))
    monkeypatch.setenv("TURBO_VIDEO_LOGS", str(tmp_path / "Logs"))
    monkeypatch.setenv("TURBO_VIDEO_EXPORTS", str(tmp_path / "Exports"))
    monkeypatch.setenv("TURBO_VIDEO_CONFIG_PATH", str(tmp_path / "Application Support" / "config.toml"))


def _make_bundle_root(root: Path) -> Path:
    (root / "resource" / "branding").mkdir(parents=True)
    (root / "resource" / "fonts").mkdir(parents=True)
    (root / "webui" / "i18n").mkdir(parents=True)
    (root / "webui" / "Main.py").write_text("# fixture entrypoint\n", encoding="utf-8")
    (root / "config.example.toml").write_text("[app]\n", encoding="utf-8")
    return root


def test_packaged_paths_are_independent_of_current_working_directory(monkeypatch, tmp_path):
    bundle = _make_bundle_root(tmp_path / "Bundle")
    _configure_packaged_environment(monkeypatch, tmp_path, bundle)
    unrelated = tmp_path / "A folder with spaces"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    directories = runtime_paths.initialise_user_directories()

    assert runtime_paths.resource_root() == bundle / "resource"
    assert runtime_paths.webui_root() == bundle / "webui"
    assert runtime_paths.config_path() == tmp_path / "Application Support" / "config.toml"
    assert all(directory.is_dir() for directory in directories.values())
    assert runtime_paths.music_dir() == tmp_path / "Application Support" / "Music"
    assert runtime_paths.projects_dir() == tmp_path / "Application Support" / "Projects"


def test_migration_copies_only_top_level_supported_music_and_preserves_projects(monkeypatch, tmp_path):
    bundle = _make_bundle_root(tmp_path / "Bundle")
    legacy = tmp_path / "MoneyPrinterTurbo"
    (legacy / "app").mkdir(parents=True)
    (legacy / "webui").mkdir()
    songs = legacy / "resource" / "songs"
    archive = songs / "archive"
    archive.mkdir(parents=True)
    (songs / "track.MP3").write_bytes(b"fixture music")
    (songs / ".hidden.mp3").write_bytes(b"hidden")
    (songs / "not-audio.txt").write_text("ignored", encoding="utf-8")
    (archive / "archived.mp3").write_bytes(b"excluded")
    (legacy / "config.toml").write_text("[app]\n", encoding="utf-8")
    task_file = legacy / "storage" / "tasks" / "task-1" / "params.json"
    task_file.parent.mkdir(parents=True)
    task_file.write_text("{}", encoding="utf-8")
    _configure_packaged_environment(monkeypatch, tmp_path, bundle)
    monkeypatch.setattr(runtime_paths, "_is_readable_audio", lambda _: True)

    result = runtime_paths.migrate_legacy_installation(legacy)

    assert result.configuration_found is True
    assert result.configuration_copied is True
    assert result.eligible_music_tracks == 1
    assert result.music_copied == 1
    assert result.music_excluded == 3
    assert result.project_files_copied == 1
    assert (runtime_paths.music_dir() / "track.MP3").is_file()
    assert not (runtime_paths.music_dir() / "archived.mp3").exists()
    assert (runtime_paths.projects_dir() / "tasks" / "task-1" / "params.json").is_file()


def test_migration_does_not_overwrite_existing_music(monkeypatch, tmp_path):
    bundle = _make_bundle_root(tmp_path / "Bundle")
    legacy = tmp_path / "MoneyPrinterTurbo"
    (legacy / "app").mkdir(parents=True)
    (legacy / "webui").mkdir()
    songs = legacy / "resource" / "songs"
    songs.mkdir(parents=True)
    (songs / "same-name.mp3").write_bytes(b"source")
    _configure_packaged_environment(monkeypatch, tmp_path, bundle)
    monkeypatch.setattr(runtime_paths, "_is_readable_audio", lambda _: True)
    runtime_paths.music_dir(create=True).joinpath("same-name.mp3").write_bytes(b"existing")

    result = runtime_paths.migrate_legacy_installation(legacy, include_config=False, include_projects=False)

    assert result.music_copied == 0
    assert result.music_skipped_as_duplicates == 1
    assert (runtime_paths.music_dir() / "same-name.mp3").read_bytes() == b"existing"


def test_packaged_media_resolver_prefers_controlled_binaries(monkeypatch, tmp_path):
    bundle = _make_bundle_root(tmp_path / "Bundle")
    media_dir = bundle / "bin"
    media_dir.mkdir()
    ffmpeg = media_dir / "ffmpeg"
    ffprobe = media_dir / "ffprobe"
    ffmpeg.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ffprobe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ffmpeg.chmod(0o755)
    ffprobe.chmod(0o755)
    _configure_packaged_environment(monkeypatch, tmp_path, bundle)

    assert runtime_paths.ffmpeg_path() == ffmpeg
    assert runtime_paths.ffprobe_path() == ffprobe


def test_single_instance_lock_recovers_invalid_stale_lock(tmp_path):
    lock = SingleInstanceLock(tmp_path / "Turbo Video.lock")
    lock.path.write_text("not json", encoding="utf-8")

    assert lock.acquire() is True
    assert lock.path.is_file()
    lock.release()
    assert not lock.path.exists()


def test_desktop_port_is_loopback_only():
    port = TurboVideoDesktop._free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        assert connection.connect_ex(("127.0.0.1", port)) != 0


def test_packaged_identity_uses_turbo_video_version_and_skips_upstream_update_polling():
    source_root = Path(__file__).resolve().parents[1]
    webui_source = (source_root / "webui" / "Main.py").read_text(encoding="utf-8")

    assert runtime_paths.APP_NAME == "Turbo Video"
    assert runtime_paths.APP_VERSION == "1.0.0"
    assert TurboVideoDesktop.__module__ == "desktop.turbo_video_desktop"
    assert '<span class="mpt-brand__name">Turbo Video</span>' in webui_source
    assert 'if runtime_paths.is_packaged():\n            _render_brand()' in webui_source
    assert 'if not runtime_paths.is_packaged():\n    _desktop_menu_items["Report a bug"]' in webui_source
