"""Service package initialisation for the Turbo Video runtime."""

from app.utils.moviepy_compat import configure_moviepy_runtime

# Install the structured FFprobe metadata adapter before any service creates a
# MoviePy audio or video reader. This prevents FFmpeg 9 human-readable probe
# output from being treated as an application-level media failure.
configure_moviepy_runtime()
