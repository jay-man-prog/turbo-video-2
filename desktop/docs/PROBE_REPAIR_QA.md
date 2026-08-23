# Turbo Video FFprobe Repair — Visual QA

The final packaged no-provider smoke render used the actual `Ampersand animation_without bg.mov` opening asset, local test-pattern footage, synthetic narration, local music, existing subtitles, and the existing personal contact card.

| Frame | Timestamp | Finding |
|---|---:|---|
| `desktop/build/qa/probe-repair/opening.png` | 0.8 seconds | The gold ampersand opening is visibly composited over the charcoal portrait background. The alpha-bearing opening asset loaded and rendered without the previous MoviePy metadata-probe error. |
| `desktop/build/qa/probe-repair/final-closing.png` | 6.4 seconds | The branded final contact card is present with the R&H identity, Jayden Manno, the approved title `Director and Auctioneer`, contact number, and office name. |

The final personal and office smoke outputs each contain H.264 1080 × 1920 video and AAC audio, with matched 8.0-second audio/video durations. The smoke log contains no `Error passing ffmpeg -i command output` message and no traceback. Audio-level sampling confirms the final two-second fade declines from −35.8 dB before the fade to −57.7 dB near the end, with a maximum sampled level of −32.5 dB, so the smoke output does not clip.
