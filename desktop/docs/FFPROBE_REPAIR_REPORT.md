# Turbo Video FFprobe Repair Report

## Outcome

The packaged branded-opening failure has been repaired, the application and disk image have been rebuilt, and the repaired app is installed at:

```text
/Applications/Turbo Video.app
```

The failed installed build was preserved rather than overwritten:

```text
/Applications/Turbo Video.app.backup-20260822-210733
```

An older preserved application backup also remains at `/Applications/Turbo Video.app.backup-20260822-203716`.

## Actual root cause

The official opening asset was valid. The failure was a **MoviePy 2.2.1 parser compatibility defect with FFmpeg 9’s human-readable stream-group output**, not a damaged MOV, missing codec, provider error, path quoting issue, or normal FFmpeg inspection exit.

| Diagnostic item | Result |
|---|---|
| Failing application call | `app/services/video.py`, `_open_video_clip_quietly()`, line 535, when it constructs `VideoFileClip(video_path, audio=..., has_mask=...)`. |
| Failing dependency function | `moviepy.video.io.ffmpeg_reader.ffmpeg_parse_infos()` line 910 re-raised `OSError: Error passing ffmpeg -i command output`. |
| Underlying parser failure | `FFmpegInfosParser.parse()` treats any line beginning with `Stream ` as a normal stream. FFmpeg 9 emits `Stream group #...: Track Reference:` before the actual streams. The normal-stream regex does not match that line, leaving `main_info_match` empty before `.groups()` at line 474. |
| Normal `ffmpeg -i` exit | Exit code `1` with `At least one output file must be specified`; this is normal for an input-only inspection and was not evidence that the MOV was invalid. |
| Asset integrity | Source and packaged opening files are byte-for-byte identical; SHA-256: `6d5c33e42e0eaa71ceb6a5e2238d434dec26759f1ccc9dfc2364f23f92f4e724`. |
| FFprobe metadata | Valid 5.005-second MOV with ProRes 4444 `yuva444p12le` video at 2417 × 2417, PCM stereo audio, and a timecode/data stream. |

The installed error log confirms that the media reached `generate_video()`, then failed as the branded opening was opened. The error was logged by the task pipeline after MoviePy re-raised its parser exception. No provider request was involved in this failure.

## Media-tool and MoviePy configuration findings

| Runtime | FFmpeg | FFprobe | MoviePy probe behaviour |
|---|---|---|---|
| Previous packaged build | Controlled app-bundled FFmpeg 9.0.1 was selected through the launcher’s `IMAGEIO_FFMPEG_EXE` environment. MoviePy still used its built-in human-readable `ffmpeg -i` parser. | Bundled FFprobe 9.0.1 was present but unused by MoviePy. | `FFMPEG_BINARY` was derived by MoviePy from its `ffmpeg-imageio` configuration. `FFPLAY_BINARY` remained MoviePy’s optional auto-detected preview configuration; it is not required for rendering. |
| Development installation | FFmpeg 9.0.1 from `/opt/homebrew/bin/ffmpeg`. | FFprobe 9.0.1 from `/opt/homebrew/bin/ffprobe`. | The source helper could resolve these binaries, but MoviePy’s parser still depended on human-readable FFmpeg text. |
| Repaired packaged build | `FFMPEG_BINARY` is explicitly set at runtime to the absolute controlled app-bundled FFmpeg path. | The structured probe resolves the absolute app-bundled FFprobe path first. | Both MoviePy video and audio reader metadata callbacks are replaced with an FFprobe-JSON-compatible callable. `FFPLAY_BINARY` is unchanged because preview playback is not used by the render pipeline. |

The relevant output format difference is between ImageIO’s packaged FFmpeg 7.1 and the controlled FFmpeg 9.0.1. FFmpeg 9 introduces the `Stream group ... Track Reference` text that MoviePy 2.2.1’s parser does not recognise. The timecode track is valid; it only becomes problematic because the preceding stream-group line is misclassified by the text parser.

## Repair implementation

A new `app.utils.moviepy_compat` module performs a machine-readable FFprobe call equivalent to:

```text
ffprobe -v error -show_entries format=duration -show_streams -of json <input>
```

It validates that the file exists, is not a directory, has a positive duration, and contains usable metadata. It parses duration, video dimensions, frame rate, codec, pixel format/alpha, audio codec/sample rate, and data streams. It rejects genuine FFprobe failures and never treats FFmpeg’s expected input-only `-i` exit as a validity signal.

During `app.services` package initialisation, the repair configures the MoviePy config module plus its video and audio readers. Both reader paths use the controlled absolute FFmpeg binary for decoding and the FFprobe JSON adapter for metadata. This covers `VideoFileClip` and `AudioFileClip`, rather than correcting only an unrelated duration helper.

The repair also constrains background music to the actual complete branded-video duration after loop/override handling. This prevents a long local fixture or provider override from extending the audio stream beyond the final video frame; it keeps the existing two-second R&H music fade anchored to the end of the final video timeline.

| Changed file | Purpose |
|---|---|
| `app/utils/moviepy_compat.py` | New structured FFprobe probe, metadata validation, MoviePy compatibility adapter, and safe binary resolution. |
| `app/services/__init__.py` | Installs the compatibility adapter before any service opens a MoviePy audio or video reader. |
| `app/services/video.py` | Keeps background music duration aligned to the full branded video timeline before applying the final fade. |
| `test/test_moviepy_probe.py` | Nine new focused local probe and actual-opening-reader tests. |
| `test/services/test_video.py` | Extends the lightweight fake MoviePy clip fixture to exercise the duration constraint. |

No official asset was converted, altered, or replaced.

## Test results

| Check | Result |
|---|---|
| Structured probe unit suite | 9 passed in 0.70 seconds. |
| Focused probe, video, and branding regressions | 55 passed, 11 warnings, 10 subtests passed in 2.33 seconds. |
| Full focused Turbo Video regression suite | 220 passed, 6 skipped, 12 warnings, 50 subtests passed in 15.78 seconds. |
| Actual ProRes 4444 opening reader | Passed: opened through MoviePy with the structured probe and produced a frame. |
| Paths with spaces | Covered by the local structured-probe test. |
| PCM audio and timecode/data stream | Covered by actual opening-asset FFprobe metadata test. |
| Invalid and missing media | Covered by local failure and missing-file tests. |
| PATH-independent packaged resolution | Covered by test using a packaged bundle root with spaces and an empty `PATH`. |

No paid LLM, Pexels, ElevenLabs, or other provider calls were made during diagnosis, testing, packaging, smoke rendering, or installation.

## Final packaged smoke render

The rebuilt package rendered both final contact-card variants using the **actual ProRes 4444 opening**, local test-pattern footage, synthetic narration, local music, existing subtitle flow, and existing closing card.

| Verification | Personal card | Office card |
|---|---:|---:|
| Render completed | Yes | Yes |
| Opening probe error / traceback | None | None |
| Video | H.264, 1080 × 1920, 8.000 seconds | H.264, 1080 × 1920, 8.000 seconds |
| Audio | AAC, 8.000 seconds | AAC, 8.000 seconds |
| Opening / closing | Visually verified | Rendered by the same package path |

The personal-card opening frame and closing frame are recorded in `desktop/docs/PROBE_REPAIR_QA.md`. Audio samples demonstrate the final fade: mean level fell from −35.8 dB before the fade to −57.7 dB near the end, with a sampled maximum of −32.5 dB. The final smoke log contained no `Error passing ffmpeg -i command output` message and no traceback.

## Packaging, security, and installation

| Item | Result |
|---|---|
| Rebuilt app | `~/AI/MoneyPrinterTurbo/desktop/dist/Turbo Video.app` |
| Rebuilt DMG | `~/AI/MoneyPrinterTurbo/desktop/dist/Turbo-Video-1.0.0-arm64.dmg` |
| Installed app | `/Applications/Turbo Video.app` |
| Signing / integrity | Ad-hoc signature verified with `codesign --verify --deep --strict`; DMG checksum verified with `hdiutil verify`. |
| App SHA-256 archive | `b74e9c8f819c604d5fb95c227a4c71fe2fe17f3138152c7124a7640d954df80b` |
| DMG SHA-256 | `9460ce6cf3920fed12c8e37e8779612c88455fe35dd7535457ed3426ff85e93e` |
| Mutable data in installed bundle | Zero active `config.toml` files and zero `resource/songs` files. |
| Credential inspection | No credential value was found. Three conservative text-pattern matches were inspected with all match text redacted; they were source-code exception/class identifiers, not credentials. |
| Installed startup | Repaired installed app launched in an isolated profile, backend health returned `ok`, and the temporary startup records contained zero probe errors, import errors, and tracebacks. The QA launcher and its child backend were terminated cleanly. |

The installer was ejected after installation. The source repository, user configuration, API keys, music, and projects were not modified. No commit or push was performed. No password or graphical security approval was required.
