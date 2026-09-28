# Responsive frontend implementation

**Latest change: original upload design restored at the user's request.** The original heading/copy, heading-and-preview hero, customer table (Name, Email, Signup date, Country; all six rows), animated badges, summary counters, upload area below the hero and centred Run Assessment button are restored. Responsive wrapping and shrinkable tracks remain; ScanPreview has no scrolling container or fixed minimum width. The earlier redesigned upload layout described below is historical and has been superseded. Normal vertical page scrolling may be needed on smaller screens.

Restoration verification: all 11 browser viewport runs passed (55 page/viewport checks), with no internal preview overflow or page-level horizontal overflow. Real upload, navigation, evidence, PDF and file-picker checks passed. All 9 frontend tests, lint and build passed. The existing bundle-size warning remains.


## Changes

- `src/components/Header.jsx`: native expandable mobile menu, semantic navigation buttons, active-page labels, keyboard support and Escape handling. Menu closes on navigation and occupies document flow rather than covering content.
- `src/components/DashboardNav.jsx`: accessible desktop/tablet sidebar buttons; mobile navigation is provided by the header.
- `src/pages/UploadPage.jsx`: compact heading, upload controls before the preview on mobile and beside it from 768px; file upload, API request, validation and loading behaviour retained.
- `src/pages/OverviewPage.jsx`: shrinkable dashboard sections and fluid two-column tracks on wide screens.
- `src/pages/IssuesPage.jsx`, `ActionsPage.jsx`: shrinkable content within the shared responsive dashboard shell.
- `src/pages/ByFieldPage.jsx`: flexible chart/content columns; field cards stay readable at intermediate widths.
- `src/components/StatCards.jsx`: single-column summary at 320px, three columns from 375px; two issue-stat columns on narrow screens and four on laptops/desktops; responsive padding.
- `src/components/IssueCard.jsx`: wrapping title/severity row and 14px explanation/evidence text, preserving legacy-response compatibility.
- `src/components/RecommendedActions.jsx`: wrapping action text, enlarged checkbox and clickable-label targets; PDF button retains existing behaviour.
- `src/components/IssuesByFieldChart.jsx`: fluid SVG with preserved viewBox/calculations and wrapping legends, accessible chart label.
- `src/components/Dropzone.jsx`: labelled file input, wrapping filenames and limits, touch-friendly spacing and announced errors.
- `src/components/ScanPreview.jsx`: naturally sized three-column example with four flagged rows and one additional valid row from 640px; no internal scrolling or minimum table width; reduced-motion-aware scanning animation.
- `src/index.css`: bounded fluid dashboard shell, safe long-text wrapping, shrinkable containers, 44px button/summary minimum heights and visible keyboard focus. No page-level overflow hiding.
- `responsive_smoke.mjs`: repeatable Edge browser tests using isolated backend/browser processes and real CSV uploads.
- Existing backend `browser_smoke.mjs`: selectors updated for semantic navigation buttons and the new mobile menu. No backend application or assessment logic changed.
- `dist`: regenerated production build.

No new dependencies or UI framework. Existing Tailwind defaults remain (sm 640px,
md 768px, lg 1024px, xl 1280px), with a 375px summary-grid adjustment. The shared
dashboard shell expands to 1800px; inner content has readable bounded widths.
The PDF generator and printable page sizes are unchanged.

## Actual verification

Headless Microsoft Edge **154.0.4258.37** on Windows tested all five pages (Upload,
Overview, Issues, By field, Actions) at:

| Width | Height |
| --- | --- |
| 320 | 640 |
| 375 | 812 |
| 430 | 932 |
| 768 | 1024 |
| 1024 | 768 |
| 1366 | 768 |
| 1440 | 900 |
| 1920 | 1080 |
| 812 | 375 |
| 1024 | 600 |
| 2560 | 1440 |

All 55 page/viewport combinations passed without page-level horizontal overflow
or offscreen main containers. Tests use actual assessed CSV data with a long
filename and a field name over 160 characters long, missing values, invalid email syntax and
an outlier. Native Enter-key menu navigation and evidence expansion/collapse,
menu closure, visible content and minimum button/summary heights passed.

Native file-picker opening and downloaded PDF headers were verified at 320px and
1920px. Action-checkbox interaction, reduced-motion beam suppression and malformed
upload errors passed. No uncaught browser exceptions occurred. The expected error
message from the deliberately malformed upload is logged by the existing handler.

Screenshots at 320px, 768px and 1920px were visually reviewed. Browser version and
viewport results are in `responsive-test-artifacts/results.json`; screenshots are
in the same directory. Re-run from this frontend directory with
`node responsive_smoke.mjs` (requires installed Edge, Python backend dependencies,
and port 5173 free; browser launch may require sandbox approval).

The existing **9 frontend tests**, ESLint and production build passed.

## Limits

These are browser viewport/emulation tests, not physical-device tests. Safari,
Firefox, iOS file-picker behaviour, screen-reader testing and OS download UX were
not verified. The illustrative preview fits its container without internal scrolling. Very short landscape screens and 320px screens with unusually long filenames can need normal page scrolling to reach the controls.
Long assessments require normal vertical scrolling. The existing production
warning for a bundle exceeding 500 kB remains.



## Upload layout follow-up

Modified `UploadPage.jsx`, `ScanPreview.jsx`, `Dropzone.jsx`, `index.css` and
`responsive_smoke.mjs` to keep the assessment action accessible without scrolling
inside the illustration. Production output was rebuilt. API behaviour, submit
conditions, validation limits and printable PDF layout are unchanged.

The browser test now checks empty and selected-file states separately, rejects
any visible preview content overflow or auto/scroll container, verifies that the
preview and upload controls do not overlap, and asserts the button is above the
fold on the requested laptop/tablet/mobile sizes. Selected-file screenshots use
a deliberately long filename. Button bottom positions measured from viewport top:

| Viewport | Empty | Selected long filename |
| --- | --- | --- |
| 1366 x 768 | 492px | 540px |
| 1440 x 900 | 500px | 524px |
| 1920 x 1080 | 500px | 524px |
| 768 x 1024 | 556px | 652px |
| 375 x 812 | 547px | 619px |

Additional sizes passed: 320x640, 430x932, 1024x768, 812x375, 1024x600,
2560x1440. At 320x640 the stress-test filename puts the button bottom at 701px;
at 812x375 it is 652px. These require ordinary page scrolling, with upload
controls still before the illustration in mobile layouts. No preview scrolling
is used to conceal content.

All 9 existing frontend tests, lint, build, real CSV submissions, PDF downloads,
file-picker opening, evidence expansion/collapse and upload error handling passed.
The unchanged large-bundle warning remains. Selected and unselected screenshots
are saved as `responsive-test-artifacts/upload-WIDTH-STATE.png`; the 1366px and
375px selected screenshots were visually reviewed.
