# Turbo Video Visual QA

## Native-window verification

The rebuilt `Turbo Video.app` was launched from its packaged executable in an isolated writable profile and captured at the normal macOS desktop resolution. The native window title is **Turbo Video** and the application content is rendered inside the native window without a browser toolbar, address bar, or tabs.

The current capture is saved as `desktop/build/qa/turbo-video-home-final.png`. It shows the corrected product heading **Turbo Video v1.0.0**, with R&H Essendon Simple Mode selected by default and Advanced Mode still immediately available.

| Visual checkpoint | Result |
|---|---|
| Native application identity | Pass. Both the macOS window and the in-app heading identify the product as Turbo Video. |
| Browser chrome inside the application | Pass. The Streamlit interface is contained inside the native application window with no browser controls. |
| Simple Mode default | Pass. `R&H Essendon Simple Mode` is selected on launch. |
| Critical Simple Mode controls | Pass. The topic field, background-music toggle, content-type selector, target-length selector, final-contact-card selector, additional-instructions field, voice status, and narration/visual-plan action are visible and readable. |
| Contact-card default | Pass. `Jayden Manno — Director and Auctioneer` is visible as the selected default. |
| Responsive baseline | Pass at the captured normal desktop size. The main controls are not clipped and no horizontal scrolling is visible. |
| Provider privacy | Pass for this isolated test profile. The page shows a compact fallback-voice status rather than any credential value. |

The capture only evaluates the home state because this verification uses an isolated example configuration and intentionally makes no paid provider calls. Packaged no-provider smoke rendering separately verifies both final contact-card variants.
