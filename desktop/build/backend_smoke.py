"""No-provider smoke test for Turbo Video's managed local backend."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from desktop.turbo_video_desktop import TurboVideoDesktop


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="turbo-video-backend-smoke-") as temporary:
        root = Path(temporary)
        os.environ.update(
            {
                "TURBO_VIDEO_PACKAGED": "1",
                "TURBO_VIDEO_BUNDLE_ROOT": str(Path(__file__).resolve().parents[2]),
                "TURBO_VIDEO_APP_SUPPORT": str(root / "Application Support"),
                "TURBO_VIDEO_CACHE": str(root / "Caches"),
                "TURBO_VIDEO_LOGS": str(root / "Logs"),
                "TURBO_VIDEO_EXPORTS": str(root / "Exports"),
                "TURBO_VIDEO_CONFIG_PATH": str(root / "Application Support" / "config.toml"),
                "TURBO_VIDEO_MIGRATION_SOURCE": str(root / "missing-installation"),
            }
        )
        desktop = TurboVideoDesktop()
        try:
            desktop.start_backend()
            assert desktop.backend is not None
            with urlopen(desktop._backend_url(), timeout=10) as response:
                assert response.status == 200
        finally:
            desktop.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
