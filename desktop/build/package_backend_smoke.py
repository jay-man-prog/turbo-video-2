"""No-provider smoke test for the packaged Turbo Video executable."""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


HOST = "127.0.0.1"
APP = Path(__file__).resolve().parents[2] / "desktop" / "dist" / "Turbo Video.app"
EXECUTABLE = APP / "Contents" / "MacOS" / "Turbo Video"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((HOST, 0))
        return int(listener.getsockname()[1])


def main() -> int:
    assert EXECUTABLE.is_file(), EXECUTABLE
    port = free_port()
    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="turbo-video-packaged-smoke-") as temporary:
        root = Path(temporary)
        environment = os.environ.copy()
        environment.update(
            {
                "TURBO_VIDEO_PACKAGED": "1",
                "TURBO_VIDEO_LAUNCH_TOKEN": token,
                "TURBO_VIDEO_APP_SUPPORT": str(root / "Application Support"),
                "TURBO_VIDEO_CACHE": str(root / "Caches"),
                "TURBO_VIDEO_LOGS": str(root / "Logs"),
                "TURBO_VIDEO_EXPORTS": str(root / "Exports"),
                "TURBO_VIDEO_CONFIG_PATH": str(root / "Application Support" / "config.toml"),
                "TURBO_VIDEO_MIGRATION_SOURCE": str(root / "missing-installation"),
            }
        )
        command = [
            str(EXECUTABLE),
            "--turbo-video-backend",
            "run",
            str(APP / "Contents" / "Resources" / "webui" / "Main.py"),
            "--server.address",
            HOST,
            "--server.port",
            str(port),
            "--browser.serverAddress",
            HOST,
            "--browser.gatherUsageStats",
            "false",
            "--global.developmentMode",
            "false",
            "--server.headless",
            "true",
            "--server.enableCORS",
            "false",
            "--server.enableXsrfProtection",
            "true",
            "--logger.hideWelcomeMessage",
            "true",
        ]
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            health_url = f"http://{HOST}:{port}/_stcore/health"
            deadline = time.monotonic() + 70
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout else ""
                    raise RuntimeError(f"Packaged backend exited early: {output[-2000:]}")
                try:
                    with urlopen(health_url, timeout=2) as response:
                        assert response.status == 200
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise TimeoutError("Packaged backend did not become ready.")
            with urlopen(f"http://{HOST}:{port}/?turbo_token={token}", timeout=10) as response:
                assert response.status == 200
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
