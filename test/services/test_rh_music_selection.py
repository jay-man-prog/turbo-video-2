from pathlib import Path

import moviepy

from app.services import rh_essendon


class _Clip:
    duration = 10
    def __init__(self, path): self.path = path
    def close(self): pass


def test_top_level_supported_tracks_only(monkeypatch, tmp_path):
    for name in ("one.mp3", "two.WAV", "three.m4A", "skip.ogg", ".hidden.mp3", "~temp.mp3"):
        (tmp_path / name).write_bytes(b"audio")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "archived.mp3").write_bytes(b"audio")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "nested.wav").write_bytes(b"audio")
    monkeypatch.setattr(moviepy, "AudioFileClip", _Clip)

    assert rh_essendon.eligible_music_tracks(str(tmp_path)) == ["one.mp3", "three.m4A", "two.WAV"]


def test_selection_avoids_immediate_repeat(monkeypatch, tmp_path):
    monkeypatch.setattr(rh_essendon, "eligible_music_tracks", lambda: ["a.mp3", "b.mp3"])
    monkeypatch.setattr(rh_essendon.utils, "storage_dir", lambda *args, **kwargs: str(tmp_path))
    first, _ = rh_essendon.select_music_track("task-1", selector=lambda tracks: tracks[0])
    second, _ = rh_essendon.select_music_track("task-2", selector=lambda tracks: tracks[0])
    assert (first, second) == ("a.mp3", "b.mp3")


def test_empty_music_folder_has_no_archived_fallback(monkeypatch):
    monkeypatch.setattr(rh_essendon, "eligible_music_tracks", lambda: [])
    selected, warning = rh_essendon.select_music_track("task")
    assert selected == ""
    assert "No usable R&H music tracks" in warning
