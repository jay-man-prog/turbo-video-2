"""Temporary native-webview feasibility harness for Turbo Video packaging.

This starts the existing Streamlit UI locally, displays it in a macOS WKWebView
window, waits for the health endpoint, and exits automatically after a short
observation period. It never invokes video generation or external providers.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

import webview


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STREAMLIT_ENTRYPOINT = REPOSITORY_ROOT / "webui" / "Main.py"
HOST = "127.0.0.1"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((HOST, 0))
        return int(listener.getsockname()[1])


def streamlit_ready(url: str, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{url}/_stcore/health", timeout=1.0) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.25)
    return False


def close_after(window: webview.Window, seconds: float) -> None:
    time.sleep(seconds)
    window.destroy()


def main() -> int:
    if not STREAMLIT_ENTRYPOINT.is_file():
        raise RuntimeError(f"Missing Streamlit entrypoint: {STREAMLIT_ENTRYPOINT}")

    port = free_port()
    url = f"http://{HOST}:{port}"
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(REPOSITORY_ROOT),
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        }
    )
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(STREAMLIT_ENTRYPOINT),
        "--server.address",
        HOST,
        "--server.port",
        str(port),
        "--browser.serverAddress",
        HOST,
        "--browser.gatherUsageStats",
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
    backend = subprocess.Popen(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not streamlit_ready(url):
            output = backend.stdout.read() if backend.stdout else ""
            raise RuntimeError(f"Streamlit did not become ready. Output: {output[-1000:]}")
        window = webview.create_window("Turbo Video feasibility", url, width=1200, height=820)
        threading.Thread(target=close_after, args=(window, 8.0), daemon=True).start()
        webview.start(gui="cocoa")
        return 0
    finally:
        if backend.poll() is None:
            backend.terminate()
            try:
                backend.wait(timeout=8)
            except subprocess.TimeoutExpired:
                backend.kill()
                backend.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
