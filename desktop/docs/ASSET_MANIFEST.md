# Turbo Video Asset Manifest

This manifest records the immutable R&H Essendon assets that the current renderer resolves through `app.services.video.rh_essendon_branding_assets()`, plus the deliberately user-writable music location. Source paths are repository-relative; packaged paths are relative to `Turbo Video.app/Contents/Resources`.

| Logical purpose | Development source path | Type and verified dimensions | Packaging policy | Packaged runtime resolution |
|---|---|---|---|---|
| Branded opening mark | `resource/branding/Ampersand animation_without bg.mov` | ProRes MOV; 2417 × 2417 | Bundled read-only. The portrait renderer uses up to the first 2.0 seconds over the charcoal opening background. | `resource/branding/Ampersand animation_without bg.mov` |
| Gold watermark | `resource/branding/Ampersand-Gold-RGB.png` | PNG; 480 × 542 | Bundled read-only. Used as the in-video R&H watermark. | `resource/branding/Ampersand-Gold-RGB.png` |
| Portrait branded closing background | `resource/branding/R&H_Charcoal 1080 x 1920 portrait.mp4` | H.264 MP4; 1080 × 1920 | Bundled read-only. The renderer uses up to the first 3.0 seconds as the final contact-card base. | `resource/branding/R&H_Charcoal 1080 x 1920 portrait.mp4` |
| R&H headline font | `resource/fonts/Raine&Horne-Thin.ttf` | TrueType font | Bundled read-only. Used for final-card headline typography. | `resource/fonts/Raine&Horne-Thin.ttf` |
| R&H secondary font | `resource/fonts/Raine&HorneLight.ttf` | TrueType font | Bundled read-only. Used for final-card supporting typography. | `resource/fonts/Raine&HorneLight.ttf` |
| R&H subtitle font | `resource/fonts/Raine&HorneRegular.ttf` | TrueType font | Bundled read-only. Used with white text, charcoal rounded background, and the established portrait safe-area treatment. | `resource/fonts/Raine&HorneRegular.ttf` |
| Application icon source | `resource/branding/Ampersand-Gold-RGB.png` | PNG; 480 × 542 | Converted during the repeatable build to `TurboVideo.icns`; no generated branding artwork is used. | `TurboVideo.icns` in the application bundle metadata |
| Supporting official branding collection | `resource/branding/*` excluding user music | PNG, MOV, and MP4 assets; see source collection | Bundled read-only to preserve existing application references and future approved branding variants. | `resource/branding/*` |
| User-created background music | Eligible immediate files in `resource/songs` with `.mp3`, `.wav`, or `.m4a` suffixes, case-insensitive | User media; validated as readable before use | Never bundled. On first launch, eligible top-level source tracks may be copied, never moved, to the user-owned music directory. Nested files, hidden files, temporary files, unreadable files, unsupported extensions, and the archived-music subdirectory are excluded. | `~/Library/Application Support/Turbo Video/Music` |

The application bundle intentionally excludes the active `config.toml` file and all music tracks. The selected configuration is copied on opt-in migration to `~/Library/Application Support/Turbo Video/config.toml` with private permissions, while mutable project state resolves to `~/Library/Application Support/Turbo Video/Projects`.

The packaging build stages all immutable `resource` content except `resource/songs`. The current asset resolver centralises development and packaged lookup in `app.utils.runtime_paths`, so resource discovery does not depend on the current working directory, installation location, or user name.

> Approved R&H brand assets must not be substituted with generated approximations. Any future change to an official logo, watermark, opening, or closing treatment should update this manifest and be visually validated in a portrait smoke render.
