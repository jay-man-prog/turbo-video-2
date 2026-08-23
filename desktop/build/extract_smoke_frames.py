"""Extract closing-card frames from the packaged local-render smoke outputs."""

from __future__ import annotations

from pathlib import Path

import imageio.v3 as iio
from moviepy import VideoFileClip


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "desktop" / "build" / "packaged-smoke-output"
FRAMES = OUTPUT / "frames"


def main() -> int:
    FRAMES.mkdir(parents=True, exist_ok=True)
    for stem in ("personal-contact-card", "office-contact-card"):
        with VideoFileClip(str(OUTPUT / f"{stem}.mp4")) as clip:
            frame = clip.get_frame(11.0)
        iio.imwrite(FRAMES / f"{stem}-closing.png", frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
