"""Structured FFprobe metadata support for MoviePy media readers.

MoviePy 2.2.1 probes input media by parsing human-readable ``ffmpeg -i``
stderr. That output is not a stable API: FFmpeg 9 adds stream-group records that
can make MoviePy's parser fail even when FFmpeg can decode the asset. This module
uses the controlled FFprobe binary and JSON metadata, then installs a compatible
metadata callable into MoviePy's video and audio readers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.utils import runtime_paths


class MediaProbeError(OSError):
    """Raised when FFprobe cannot establish usable media metadata."""


def _resolve_binary(name: str) -> str:
    """Resolve a controlled bundled binary first, without relying on a shell."""

    if name == "ffprobe":
        controlled = runtime_paths.ffprobe_path()
        configured = os.environ.get("TURBO_VIDEO_FFPROBE")
    elif name == "ffmpeg":
        controlled = runtime_paths.ffmpeg_path()
        configured = os.environ.get("IMAGEIO_FFMPEG_EXE") or os.environ.get("FFMPEG_BINARY")
    else:  # pragma: no cover - internal callers use only ffmpeg and ffprobe.
        raise ValueError(f"Unsupported media binary: {name}")

    if controlled and controlled.is_file() and os.access(controlled, os.X_OK):
        return str(controlled)
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
    discovered = shutil.which(name)
    if discovered:
        return str(Path(discovered).resolve())
    raise MediaProbeError(f"A usable {name} binary could not be found.")


def _fraction_to_float(value: object, default: float = 0.0) -> float:
    """Parse FFprobe frame-rate strings such as ``30000/1001`` safely."""

    text = str(value or "").strip()
    if not text or text in {"0", "0/0", "N/A"}:
        return default
    try:
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            divisor = float(denominator)
            return float(numerator) / divisor if divisor else default
        return float(text)
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def _number(value: object, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: object, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def ffprobe_metadata(filename: str | os.PathLike[str]) -> dict[str, Any]:
    """Return validated JSON metadata for one media file using absolute FFprobe."""

    path = Path(filename).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    if path.is_dir():
        raise IsADirectoryError(f"{path} is a directory")

    command = [
        _resolve_binary("ffprobe"),
        "-v",
        "error",
        "-show_entries",
        (
            "format=duration,bit_rate:"
            "stream=index,codec_type,codec_name,profile,width,height,pix_fmt,"
            "r_frame_rate,avg_frame_rate,bit_rate,sample_rate,channels,disposition"
        ),
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError as exc:
        raise MediaProbeError(f"FFprobe could not inspect {path.name}: {type(exc).__name__}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProbeError(f"FFprobe timed out while inspecting {path.name}.") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()[-1:] or ["unknown FFprobe error"]
        raise MediaProbeError(f"FFprobe could not inspect {path.name}: {detail[0]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError(f"FFprobe returned invalid metadata for {path.name}.") from exc

    streams = payload.get("streams")
    format_info = payload.get("format")
    if not isinstance(streams, list) or not isinstance(format_info, dict):
        raise MediaProbeError(f"FFprobe returned incomplete metadata for {path.name}.")
    duration = _number(format_info.get("duration"), default=None)
    if duration is None or duration <= 0:
        raise MediaProbeError(f"FFprobe did not report a positive duration for {path.name}.")

    payload["_turbo_video_duration"] = duration
    return payload


def moviepy_ffprobe_parse_infos(
    filename: str,
    check_duration: bool = True,
    fps_source: str = "fps",
    decode_file: bool = False,
    print_infos: bool = False,
) -> dict[str, Any]:
    """Provide the MoviePy reader contract using FFprobe JSON instead of ``ffmpeg -i`` text.

    The signature deliberately matches MoviePy's ``ffmpeg_parse_infos``. The
    normal non-zero exit from an inspection-only ``ffmpeg -i`` command is never
    consulted; genuine missing, corrupt, or undecodable files still raise a
    descriptive exception from FFprobe.
    """

    del fps_source, decode_file
    metadata = ffprobe_metadata(filename)
    streams = metadata["streams"]
    duration = float(metadata["_turbo_video_duration"])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)

    result: dict[str, Any] = {
        "duration": duration,
        "video_found": video_stream is not None,
        "audio_found": audio_stream is not None,
        "inputs": [{"input_number": 0, "streams": streams}],
    }
    if video_stream:
        width = _int(video_stream.get("width"), default=None)
        height = _int(video_stream.get("height"), default=None)
        if not width or not height:
            raise MediaProbeError(f"FFprobe did not report video dimensions for {Path(filename).name}.")
        frame_rate = _fraction_to_float(video_stream.get("r_frame_rate"))
        if frame_rate <= 0:
            frame_rate = _fraction_to_float(video_stream.get("avg_frame_rate"), default=1.0)
        result.update(
            {
                "video_size": [width, height],
                "video_fps": frame_rate,
                "video_duration": duration if check_duration else 0.0,
                "video_n_frames": int(duration * frame_rate) if check_duration else 0,
                "video_bitrate": _int(video_stream.get("bit_rate"), default=None),
                "video_codec_name": video_stream.get("codec_name"),
                "video_profile": video_stream.get("profile"),
                "video_pixel_format": video_stream.get("pix_fmt"),
                "video_has_alpha": "a" in str(video_stream.get("pix_fmt") or ""),
            }
        )
    else:
        result.update({"video_duration": 0.0, "video_n_frames": 0})

    if audio_stream:
        result.update(
            {
                "audio_fps": _int(audio_stream.get("sample_rate"), default=44100),
                "audio_bitrate": _int(audio_stream.get("bit_rate"), default=None),
                "audio_channels": _int(audio_stream.get("channels"), default=None),
                "audio_codec_name": audio_stream.get("codec_name"),
            }
        )
    else:
        result.update({"audio_fps": None, "audio_bitrate": None})

    if print_infos:
        print(json.dumps(metadata, sort_keys=True))
    return result


def configure_moviepy_runtime() -> None:
    """Route all imported MoviePy readers to controlled FFmpeg and FFprobe paths."""

    ffmpeg = _resolve_binary("ffmpeg")
    from moviepy import config as moviepy_config
    from moviepy.audio.io import readers as audio_readers
    from moviepy.video.io import ffmpeg_reader

    moviepy_config.FFMPEG_BINARY = ffmpeg
    # These modules import the value directly, so update their local bindings too.
    ffmpeg_reader.FFMPEG_BINARY = ffmpeg
    audio_readers.FFMPEG_BINARY = ffmpeg
    ffmpeg_reader.ffmpeg_parse_infos = moviepy_ffprobe_parse_infos
    audio_readers.ffmpeg_parse_infos = moviepy_ffprobe_parse_infos


def moviepy_runtime_values() -> dict[str, str]:
    """Return safe binary diagnostics without exposing user configuration."""

    from moviepy import config as moviepy_config

    return {
        "ffmpeg_binary": str(moviepy_config.FFMPEG_BINARY),
        "ffplay_binary": str(moviepy_config.FFPLAY_BINARY),
        "ffprobe_binary": _resolve_binary("ffprobe"),
    }
