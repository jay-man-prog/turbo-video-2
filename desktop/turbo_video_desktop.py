"""Native macOS launcher for the Turbo Video Streamlit application."""

from __future__ import annotations

import ast
import html
import importlib
import json
import pkgutil
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

import webview
from webview.menu import Menu, MenuAction, MenuSeparator


def _bootstrap_bundled_first_party_source() -> Path | None:
    """Put the physical bundled MoneyPrinterTurbo package ahead of any third-party ``app`` package."""

    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    candidates = (
        executable.parents[1] / "Resources" / "first_party",
        executable.parents[1] / "Frameworks" / "first_party",
        Path(getattr(sys, "_MEIPASS", executable.parent)) / "first_party",
    )
    for candidate in candidates:
        if (candidate / "app" / "__init__.py").is_file():
            candidate_text = str(candidate)
            if candidate_text in sys.path:
                sys.path.remove(candidate_text)
            sys.path.insert(0, candidate_text)
            os.environ["TURBO_VIDEO_FIRST_PARTY_ROOT"] = candidate_text
            return candidate
    return None


_BUNDLED_FIRST_PARTY_ROOT = _bootstrap_bundled_first_party_source()

from app.utils import runtime_paths



APP_VERSION = runtime_paths.APP_VERSION
HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 75.0
LOCK_FILENAME = "turbo-video.instance.lock"
MIGRATION_MARKER = "migration-v1.json"


@dataclass
class BackendState:
    port: int
    token: str
    process: subprocess.Popen[str]


class SingleInstanceLock:
    """A PID lock that only removes a demonstrably stale Turbo Video lock."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.acquired = False

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if self._is_stale():
                try:
                    self.path.unlink()
                except OSError:
                    return False
                return self.acquire()
            return False
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "started_at": time.time()}, stream)
        self.acquired = True
        return True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            self.path.unlink(missing_ok=True)
        finally:
            self.acquired = False

    def _is_stale(self) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            pid = int(payload.get("pid", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return True
        if pid <= 0:
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False


class TurboVideoDesktop:
    def __init__(self) -> None:
        self.window: webview.Window | None = None
        self.backend: BackendState | None = None
        self._lock = SingleInstanceLock(runtime_paths.application_support_dir(create=True) / LOCK_FILENAME)
        self._shutdown_started = threading.Event()
        self._boot_thread: threading.Thread | None = None

    def run(self) -> int:
        # The launcher is the desktop runtime even when executed from source for validation.
        os.environ["TURBO_VIDEO_PACKAGED"] = "1"
        runtime_paths.initialise_user_directories()
        if not self._lock.acquire():
            self._activate_existing_instance()
            return 0

        self.window = webview.create_window(
            "Turbo Video",
            html=self._loading_screen("Preparing Turbo Video…"),
            width=1280,
            height=880,
            min_size=(980, 680),
            resizable=True,
            background_color="#2B2B2B",
        )
        self.window.events.closing += self._confirm_close
        self.window.events.closed += self._on_closed
        self._boot_thread = threading.Thread(target=self._bootstrap, name="turbo-video-startup", daemon=True)
        self._boot_thread.start()
        try:
            webview.start(menu=self._application_menu(), gui="cocoa")
            return 0
        finally:
            self.shutdown()

    def _bootstrap(self) -> None:
        assert self.window is not None
        self.window.events.shown.wait(20)
        try:
            self._offer_initial_migration()
            self.start_backend()
            assert self.backend is not None
            self.window.load_url(self._backend_url())
        except Exception as exc:  # The detailed error is retained locally in the redacted log.
            self._log_startup_error(exc)
            self.window.load_html(self._startup_error_screen("Turbo Video could not start its local backend."))

    def _offer_initial_migration(self) -> None:
        marker = runtime_paths.application_support_dir(create=True) / MIGRATION_MARKER
        if marker.exists():
            return
        source = runtime_paths.discover_legacy_installation()
        if source is None:
            self._write_migration_marker({"source_found": False, "action": "not_available"})
            return
        assert self.window is not None
        answer = self.window.create_confirmation_dialog(
            "Import existing Turbo Video data?",
            "An existing MoneyPrinterTurbo installation was found. Import its configuration, eligible top-level music tracks, and saved project files now? Existing files will be copied only; nothing will be moved or deleted.",
        )
        if answer:
            result = runtime_paths.migrate_legacy_installation(source)
            payload = result.as_dict()
            payload["action"] = "imported"
        else:
            payload = {"source_found": True, "action": "skipped"}
        self._write_migration_marker(payload)

    def start_backend(self) -> None:
        if self.backend and self.backend.process.poll() is None:
            return
        port = self._free_port()
        token = secrets.token_urlsafe(32)
        environment = os.environ.copy()
        environment.update(
            {
                "TURBO_VIDEO_PACKAGED": "1",
                "TURBO_VIDEO_LAUNCH_TOKEN": token,
                "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
                "MPLCONFIGDIR": str(runtime_paths.cache_dir(create=True) / "matplotlib"),
            }
        )
        ffmpeg = runtime_paths.ffmpeg_path()
        ffprobe = runtime_paths.ffprobe_path()
        if ffmpeg:
            environment["IMAGEIO_FFMPEG_EXE"] = str(ffmpeg)
            environment["PATH"] = f"{ffmpeg.parent}{os.pathsep}{environment.get('PATH', '')}"
        if ffprobe:
            environment["TURBO_VIDEO_FFPROBE"] = str(ffprobe)
        entrypoint = runtime_paths.webui_root() / "Main.py"
        streamlit_arguments = [
            "run",
            str(entrypoint),
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
        command = (
            [sys.executable, "--turbo-video-backend", *streamlit_arguments]
            if getattr(sys, "frozen", False)
            else [sys.executable, "-m", "streamlit", *streamlit_arguments]
        )
        log_path = runtime_paths.logs_dir(create=True) / "desktop-backend.log"
        log_handle = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(
            command,
            cwd=runtime_paths.code_root(),
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.backend = BackendState(port=port, token=token, process=process)
        if not self._wait_for_backend():
            self.stop_backend()
            raise RuntimeError("The local backend did not become ready before the startup timeout.")

    def stop_backend(self) -> None:
        if self.backend is None:
            return
        process = self.backend.process
        self.backend = None
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def restart_backend(self) -> None:
        if self.window is None:
            return
        self.window.load_html(self._loading_screen("Restarting the local backend…"))
        try:
            self.stop_backend()
            self.start_backend()
            self.window.load_url(self._backend_url())
        except Exception as exc:
            self._log_startup_error(exc)
            self.window.load_html(self._startup_error_screen("Turbo Video could not restart its local backend."))

    def open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(path)], check=False)

    def save_latest_video_as(self) -> None:
        assert self.window is not None
        candidates = sorted(runtime_paths.export_dir(create=True).glob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            self.window.create_confirmation_dialog("Save Video As…", "No completed Turbo Video export is currently available.")
            return
        destination = self.window.create_file_dialog(
            webview.SAVE,
            save_filename=candidates[0].name,
            file_types=("MPEG-4 video (*.mp4)",),
        )
        if destination:
            shutil.copy2(candidates[0], Path(destination))

    def show_diagnostics(self) -> None:
        assert self.window is not None
        diagnostics = self._diagnostics()
        rows = "".join(
            f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
            for label, value in diagnostics.items()
        )
        self.window.load_html(
            "<html><body style='font-family:-apple-system;padding:32px;background:#f6f5f2;color:#2b2b2b'>"
            "<h1>Turbo Video Diagnostics</h1><table>"
            f"{rows}</table><p>Close this view or choose Reload Interface to return to Turbo Video.</p></body></html>"
        )

    def reload_interface(self) -> None:
        if self.window is not None and self.backend and self.backend.process.poll() is None:
            self.window.load_url(self._backend_url())

    def shutdown(self) -> None:
        if self._shutdown_started.is_set():
            return
        self._shutdown_started.set()
        try:
            self.stop_backend()
        finally:
            self._lock.release()

    def _application_menu(self) -> list[Menu]:
        return [
            Menu(
                "Turbo Video",
                [
                    MenuAction("About Turbo Video", self.show_diagnostics),
                    MenuAction("Preferences and Diagnostics", self.show_diagnostics),
                    MenuSeparator(),
                    MenuAction("Quit Turbo Video", self._quit),
                ],
            ),
            Menu(
                "File",
                [
                    MenuAction("Open Projects Folder", lambda: self.open_folder(runtime_paths.projects_dir(create=True))),
                    MenuAction("Open Music Folder", lambda: self.open_folder(runtime_paths.music_dir(create=True))),
                    MenuAction("Open Finished Videos", lambda: self.open_folder(runtime_paths.export_dir(create=True))),
                    MenuAction("Save Video As…", self.save_latest_video_as),
                ],
            ),
            Menu(
                "View",
                [
                    MenuAction("Reload Interface", self.reload_interface),
                    MenuAction("Restart Local Backend", self.restart_backend),
                    MenuAction("View Logs", lambda: self.open_folder(runtime_paths.logs_dir(create=True))),
                ],
            ),
        ]

    def _confirm_close(self) -> bool:
        if self._shutdown_started.is_set():
            return True
        assert self.window is not None
        accepted = self.window.create_confirmation_dialog(
            "Quit Turbo Video?",
            "Quitting closes the local backend. If a render is active, it will be interrupted; choose Cancel to keep Turbo Video running.",
        )
        if accepted:
            self.shutdown()
            return True
        return False

    def _on_closed(self) -> None:
        self.shutdown()

    def _quit(self) -> None:
        self.shutdown()
        if self.window is not None:
            self.window.destroy()

    def _backend_url(self) -> str:
        assert self.backend is not None
        return f"http://{HOST}:{self.backend.port}/?turbo_token={self.backend.token}"

    def _wait_for_backend(self) -> bool:
        assert self.backend is not None
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        health_url = f"http://{HOST}:{self.backend.port}/_stcore/health"
        while time.monotonic() < deadline:
            if self.backend.process.poll() is not None:
                return False
            try:
                with urlopen(health_url, timeout=1.0) as response:
                    if response.status == 200:
                        return True
            except OSError:
                time.sleep(0.25)
        return False

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind((HOST, 0))
            return int(listener.getsockname()[1])

    @staticmethod
    def _loading_screen(message: str) -> str:
        return (
            "<html><body style='margin:0;display:flex;align-items:center;justify-content:center;"
            "height:100vh;background:#2b2b2b;color:white;font-family:-apple-system'>"
            "<section style='text-align:center'><h1 style='font-weight:400'>Turbo Video</h1>"
            f"<p>{html.escape(message)}</p></section></body></html>"
        )

    @staticmethod
    def _startup_error_screen(message: str) -> str:
        return (
            "<html><body style='margin:0;display:flex;align-items:center;justify-content:center;"
            "height:100vh;background:#2b2b2b;color:white;font-family:-apple-system'>"
            "<section style='max-width:520px;text-align:center'><h1 style='font-weight:400'>Turbo Video needs attention</h1>"
            f"<p>{html.escape(message)}</p><p>Use the View menu to open the local log folder or restart the local backend.</p>"
            "</section></body></html>"
        )

    @staticmethod
    def _activate_existing_instance() -> None:
        bundle_path = Path(sys.argv[0]).resolve().parents[2] if getattr(sys, "frozen", False) else None
        if bundle_path and bundle_path.suffix == ".app":
            subprocess.run(["open", "-a", str(bundle_path)], check=False)

    @staticmethod
    def _write_migration_marker(payload: dict[str, object]) -> None:
        marker = runtime_paths.application_support_dir(create=True) / MIGRATION_MARKER
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(marker)

    @staticmethod
    def _log_startup_error(exc: Exception) -> None:
        # Avoid secrets and full paths in startup UI; the log records only error type and message.
        log_path = runtime_paths.logs_dir(create=True) / "desktop-startup.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {type(exc).__name__}: {exc}\n")

    @staticmethod
    def _diagnostics() -> dict[str, str]:
        backend = "Running" if False else "Managed locally"
        ffmpeg = runtime_paths.ffmpeg_path()
        ffprobe = runtime_paths.ffprobe_path()
        return {
            "Turbo Video version": APP_VERSION,
            "macOS architecture": os.uname().machine,
            "Backend": backend,
            "FFmpeg": "Available" if ffmpeg and ffmpeg.is_file() else "Not bundled",
            "FFprobe": "Available" if ffprobe and ffprobe.is_file() else "Not bundled",
            "Configuration": "Present" if runtime_paths.config_path().is_file() else "Not imported",
            "Application Support": "Writable" if os.access(runtime_paths.application_support_dir(create=True), os.W_OK) else "Unavailable",
            "Music folder": "Writable" if os.access(runtime_paths.music_dir(create=True), os.W_OK) else "Unavailable",
        }


def run_embedded_streamlit_backend() -> int:
    """Run Streamlit from the bundled executable instead of requiring a second Python binary."""

    from streamlit.web import cli as streamlit_cli

    arguments = sys.argv[sys.argv.index("--turbo-video-backend") + 1 :]
    sys.argv = ["streamlit", *arguments]
    streamlit_cli.main()
    return 0


def run_packaged_import_smoke() -> int:
    """Import all packaged first-party modules and prove they resolve from the app bundle."""

    if _BUNDLED_FIRST_PARTY_ROOT is None:
        raise RuntimeError("The packaged first-party source root was not activated.")
    bundle_root = _BUNDLED_FIRST_PARTY_ROOT.resolve()
    resources_root = bundle_root.parent.resolve()
    required = {
        "app",
        "app.models",
        "app.models.llm_provider",
        "app.services.rh_essendon",
        "app.services.material",
        "app.services.task",
        "app.services.video",
        "app.services.voice",
        "app.services.subtitle",
        "app.config.config",
        "app.controllers",
    }
    app_root = bundle_root / "app"
    entrypoint = resources_root / "webui" / "Main.py"
    entrypoint_tree = ast.parse(entrypoint.read_text(encoding="utf-8"), filename=str(entrypoint))
    for node in ast.walk(entrypoint_tree):
        if not isinstance(node, ast.ImportFrom) or not node.module or not node.module.startswith("app"):
            continue
        required.add(node.module)
        for imported_name in node.names:
            if imported_name.name == "*":
                continue
            candidate = bundle_root / f"{node.module.replace('.', '/')}/{imported_name.name}"
            if candidate.with_suffix(".py").is_file() or (candidate / "__init__.py").is_file():
                required.add(f"{node.module}.{imported_name.name}")
    required.update(
        module.name
        for module in pkgutil.walk_packages([str(app_root)], prefix="app.")
    )
    locations: dict[str, str] = {}
    for module_name in sorted(required):
        module = importlib.import_module(module_name)
        required_root = bundle_root if module_name == "app" or module_name.startswith("app.") else resources_root
        module_file = getattr(module, "__file__", None)
        if module_file:
            resolved = Path(module_file).resolve()
            try:
                resolved.relative_to(required_root)
            except ValueError as exc:
                raise RuntimeError(f"{module_name} resolved outside its required Turbo Video bundle location: {resolved}") from exc
            locations[module_name] = str(resolved)
            continue
        namespace_paths = [Path(path).resolve() for path in getattr(module, "__path__", ())]
        if not namespace_paths:
            raise RuntimeError(f"{module_name} has no auditable module location.")
        for namespace_path in namespace_paths:
            try:
                namespace_path.relative_to(required_root)
            except ValueError as exc:
                raise RuntimeError(f"{module_name} namespace resolved outside its required Turbo Video bundle location: {namespace_path}") from exc
        locations[module_name] = ";".join(str(path) for path in namespace_paths)
    # This diagnostic is invoked only by the local build check, never by the UI.
    print(json.dumps({"first_party_root": str(bundle_root), "modules": locations}, indent=2, sort_keys=True))
    return 0


def run_packaged_render_smoke(output_directory: Path) -> int:
    """Render two local branded fixtures without provider calls for package verification."""

    from app.models.schema import VideoAspect, VideoParams
    from app.services import video

    output_directory.mkdir(parents=True, exist_ok=True)
    ffmpeg = runtime_paths.ffmpeg_path()
    if ffmpeg is None:
        raise RuntimeError("The packaged FFmpeg executable is unavailable.")
    fixture_video = output_directory / "fixture-footage.mp4"
    fixture_audio = output_directory / "fixture-narration.m4a"
    fixture_music = output_directory / "fixture-music.m4a"
    fixture_subtitles = output_directory / "fixture-subtitles.srt"
    commands = (
        [str(ffmpeg), "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=25", "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(fixture_video)],
        [str(ffmpeg), "-y", "-f", "lavfi", "-i", "sine=frequency=660:sample_rate=44100", "-t", "3", "-c:a", "aac", str(fixture_audio)],
        [str(ffmpeg), "-y", "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100", "-t", "20", "-c:a", "aac", str(fixture_music)],
    )
    for command in commands:
        subprocess.run(command, capture_output=True, check=True, text=True)
    fixture_subtitles.write_text(
        """1
00:00:00,000 --> 00:00:02,500
Turbo Video packaged render smoke test.

""",
        encoding="utf-8",
    )

    results: dict[str, bool] = {}
    for contact_card, filename in (("jayden_manno", "personal-contact-card.mp4"), ("rh_essendon_office", "office-contact-card.mp4")):
        params = VideoParams(
            video_subject="Local packaged smoke test",
            video_aspect=VideoAspect.portrait,
            subtitle_enabled=True,
            rh_essendon_branding=True,
            rh_background_music_enabled=True,
            rh_final_contact_card=contact_card,
        )
        output = output_directory / filename
        results[contact_card] = video.generate_video(
            str(fixture_video),
            str(fixture_audio),
            str(fixture_subtitles),
            str(output),
            params,
            bgm_file_override=str(fixture_music),
        )
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Packaged smoke render failed for {contact_card}.")
    (output_directory / "render-results.json").write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def main() -> int:
    if "--turbo-video-import-smoke" in sys.argv:
        return run_packaged_import_smoke()
    if "--turbo-video-backend" in sys.argv:
        return run_embedded_streamlit_backend()
    if "--turbo-video-render-smoke" in sys.argv:
        index = sys.argv.index("--turbo-video-render-smoke")
        if len(sys.argv) <= index + 1:
            raise SystemExit("A smoke-test output directory is required.")
        return run_packaged_render_smoke(Path(sys.argv[index + 1]))
    return TurboVideoDesktop().run()


if __name__ == "__main__":
    raise SystemExit(main())
