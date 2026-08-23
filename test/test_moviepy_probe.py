from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.utils import moviepy_compat, runtime_paths


OPENING_ASSET = (
    Path(__file__).resolve().parents[1]
    / "resource"
    / "branding"
    / "Ampersand animation_without bg.mov"
)


def _metadata_payload(*, duration: str = "5.005000", include_video: bool = True):
    streams = [
        {
            "index": 0,
            "codec_type": "video",
            "codec_name": "prores",
            "profile": "4444",
            "width": 2417,
            "height": 2417,
            "pix_fmt": "yuva444p12le",
            "r_frame_rate": "30000/1001",
            "avg_frame_rate": "30000/1001",
            "bit_rate": "158614000",
        },
        {
            "index": 1,
            "codec_type": "audio",
            "codec_name": "pcm_s16le",
            "sample_rate": "48000",
            "channels": 2,
            "bit_rate": "1536000",
        },
        {
            "index": 2,
            "codec_type": "data",
            "codec_name": "none",
        },
    ]
    if not include_video:
        streams = streams[1:]
    return {"format": {"duration": duration}, "streams": streams}


def _patch_ffprobe(monkeypatch, payload, *, returncode: int = 0, stderr: str = ""):
    monkeypatch.setattr(moviepy_compat, "_resolve_binary", lambda name: f"/controlled/{name}")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=returncode, stdout=json.dumps(payload), stderr=stderr)

    monkeypatch.setattr(moviepy_compat.subprocess, "run", run)
    return calls


def test_structured_probe_reads_prores_alpha_pcm_and_timecode_stream(monkeypatch, tmp_path):
    media = tmp_path / "Opening asset with spaces.mov"
    media.write_bytes(b"fixture")
    calls = _patch_ffprobe(monkeypatch, _metadata_payload())

    infos = moviepy_compat.moviepy_ffprobe_parse_infos(str(media))

    assert calls[0][0][0] == "/controlled/ffprobe"
    assert calls[0][0][-1] == str(media)
    assert infos["duration"] == pytest.approx(5.005)
    assert infos["video_size"] == [2417, 2417]
    assert infos["video_fps"] == pytest.approx(30000 / 1001)
    assert infos["video_has_alpha"] is True
    assert infos["audio_found"] is True
    assert infos["audio_codec_name"] == "pcm_s16le"
    assert any(stream["codec_type"] == "data" for stream in infos["inputs"][0]["streams"])


def test_probe_does_not_parse_or_depend_on_ffmpeg_no_output_exit(monkeypatch, tmp_path):
    media = tmp_path / "valid.mov"
    media.write_bytes(b"fixture")
    calls = _patch_ffprobe(monkeypatch, _metadata_payload())

    moviepy_compat.moviepy_ffprobe_parse_infos(str(media))

    assert all(command[0] == "/controlled/ffprobe" for command, _ in calls)
    assert all("-i" not in command for command, _ in calls)


def test_probe_rejects_genuine_ffprobe_failure(monkeypatch, tmp_path):
    media = tmp_path / "corrupt.mov"
    media.write_bytes(b"not media")
    _patch_ffprobe(monkeypatch, {}, returncode=1, stderr="Invalid data found when processing input")

    with pytest.raises(moviepy_compat.MediaProbeError, match="Invalid data"):
        moviepy_compat.ffprobe_metadata(media)


def test_probe_rejects_missing_file_without_invoking_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(moviepy_compat, "_resolve_binary", lambda name: pytest.fail("binary should not run"))

    with pytest.raises(FileNotFoundError):
        moviepy_compat.ffprobe_metadata(tmp_path / "missing.mov")


def test_probe_requires_positive_duration(monkeypatch, tmp_path):
    media = tmp_path / "zero-duration.mov"
    media.write_bytes(b"fixture")
    _patch_ffprobe(monkeypatch, _metadata_payload(duration="0"))

    with pytest.raises(moviepy_compat.MediaProbeError, match="positive duration"):
        moviepy_compat.ffprobe_metadata(media)


def test_configure_moviepy_runtime_uses_controlled_binary_and_replaces_both_reader_paths(monkeypatch, tmp_path):
    from moviepy import config as moviepy_config
    from moviepy.audio.io import readers as audio_readers
    from moviepy.video.io import ffmpeg_reader

    original = (
        moviepy_config.FFMPEG_BINARY,
        ffmpeg_reader.FFMPEG_BINARY,
        audio_readers.FFMPEG_BINARY,
        ffmpeg_reader.ffmpeg_parse_infos,
        audio_readers.ffmpeg_parse_infos,
    )
    ffmpeg = tmp_path / "ffmpeg"
    ffprobe = tmp_path / "ffprobe"
    for binary in (ffmpeg, ffprobe):
        binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        binary.chmod(0o755)
    monkeypatch.setenv("TURBO_VIDEO_FFMPEG", str(ffmpeg))
    monkeypatch.setenv("TURBO_VIDEO_FFPROBE", str(ffprobe))
    monkeypatch.setenv("PATH", "")

    try:
        moviepy_compat.configure_moviepy_runtime()

        assert moviepy_config.FFMPEG_BINARY == str(ffmpeg.resolve())
        assert ffmpeg_reader.FFMPEG_BINARY == str(ffmpeg.resolve())
        assert audio_readers.FFMPEG_BINARY == str(ffmpeg.resolve())
        assert ffmpeg_reader.ffmpeg_parse_infos is moviepy_compat.moviepy_ffprobe_parse_infos
        assert audio_readers.ffmpeg_parse_infos is moviepy_compat.moviepy_ffprobe_parse_infos
    finally:
        (
            moviepy_config.FFMPEG_BINARY,
            ffmpeg_reader.FFMPEG_BINARY,
            audio_readers.FFMPEG_BINARY,
            ffmpeg_reader.ffmpeg_parse_infos,
            audio_readers.ffmpeg_parse_infos,
        ) = original


def test_actual_opening_asset_has_structured_duration_alpha_audio_and_timecode():
    metadata = moviepy_compat.ffprobe_metadata(OPENING_ASSET)
    infos = moviepy_compat.moviepy_ffprobe_parse_infos(str(OPENING_ASSET))

    assert metadata["_turbo_video_duration"] == pytest.approx(5.005, rel=0.01)
    assert infos["video_size"] == [2417, 2417]
    assert infos["video_has_alpha"] is True
    assert infos["audio_found"] is True
    assert any(stream.get("codec_type") == "data" for stream in metadata["streams"])


def test_packaged_ffprobe_resolution_is_independent_of_working_directory(monkeypatch, tmp_path):
    bundle = tmp_path / "Bundle with spaces"
    binary_dir = bundle / "bin"
    binary_dir.mkdir(parents=True)
    ffprobe = binary_dir / "ffprobe"
    ffprobe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ffprobe.chmod(0o755)
    monkeypatch.setenv("TURBO_VIDEO_PACKAGED", "1")
    monkeypatch.setenv("TURBO_VIDEO_BUNDLE_ROOT", str(bundle))
    monkeypatch.setenv("PATH", "")
    monkeypatch.chdir(tmp_path)

    assert runtime_paths.ffprobe_path() == ffprobe
    assert moviepy_compat._resolve_binary("ffprobe") == str(ffprobe)


def test_actual_opening_asset_opens_with_moviepy_after_structured_probe_configuration():
    from moviepy import VideoFileClip

    moviepy_compat.configure_moviepy_runtime()
    clip = VideoFileClip(str(OPENING_ASSET), audio=False, has_mask=True)
    try:
        assert clip.duration == pytest.approx(5.005, rel=0.01)
        assert tuple(clip.size) == (2417, 2417)
        frame = clip.get_frame(0)
        assert frame.shape[:2] == (2417, 2417)
    finally:
        clip.close()
