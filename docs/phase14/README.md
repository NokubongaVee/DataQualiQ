# Phase 14: final network PDF report

Updated the existing jsPDF export rather than replacing the report system. Backend recommendations, model, preprocessing, quality rules, App memory state, storage and generic assessment PDF remain unchanged. Reports still exports from the active analysis only; refresh without an active result displays the existing empty state instead of an export button.

## Content and layout

The title is Network Intrusion Analysis Report with DataQualiQ branding, actual filename and analysed count. No analysis timestamp is invented because the response does not supply one.

Nine sections: executive summary; data quality; current-upload intrusion detection; Model Performance - Official Test Evaluation; predictive-input reliability; suspicious/important records; backend security recommendations; limitations, preceded by the report header. Data quality distinguishes errors, quality issues and analytical/security anomalies. Normal/Malicious percentages use classified records, excluding rejected rows. Model probability and input reliability are separate. Official metrics and confusion matrix are gated by saved evaluation provenance and explicitly not current-upload results. False negatives are missed malicious traffic.

PDF formatting uses A4, 18 mm side margins, 11-point body type, section bands, a recurring navy header, wrapped paragraphs, page breaks and numbered footers. Text and collection lengths are bounded; no huge tables or raw audit structures are exported.

## Selection and bounds

At most twenty important records are selected only from the returned page. Ordering: Malicious + Review, Malicious + Low, rejected records, Malicious + High. Ties use original source-row positions. Rejected status takes precedence over any supplied label: it never receives a fabricated prediction/probability. Normal rows are not added merely to fill the preview. The original response is not sorted or mutated.

Each selected record includes original one-based data-row number, supplied prediction/probability/reliability, actual reliability reason, up to three returned finding details, truncation notices and rejection reason. Field summaries are limited to ten per quality group. Warnings/recommendations are capped at twenty and omissions are labelled. Recommendation priority/message/reason/count are copied directly from the backend; no recommendation algorithm or blocking action is introduced. No additional result pages are requested.

## Files

Inspected Reports/NetworkDetailPages, existing network and legacy PDF utilities, active App state, structured API contract, Dashboard/Phase 13 recommendation and attention components, styles, tests and browser validation.

Modified `frontend/src/utils/downloadNetworkPdf.js`, `frontend/src/components/NetworkDetailPages.jsx` (export description), `frontend/statistics_audit.test.mjs`, and `frontend/network_browser_audit.mjs`. Created this report, `validate_pdf.py`, the generated sample PDF, expected report content, validation JSON and rendered pages under `docs/phase14`. No new production dependencies.

## Validation

49 frontend tests passed, covering section mapping, official provenance, rejection handling, selection ordering, nonmutation, huge-input bounds, actual PDF generation, empty states and prior frontend regressions. Lint and production build passed. The retained reporting bundle emits the existing large-chunk advisory (683.53 kB).

Headless Edge used the actual Reports button after a real frontend/FastAPI upload of the first 1,000 official testing rows. It downloaded `DataQualiQ-network-report.pdf`: eight pages, 49,965 bytes, 20 important records from the returned 100-row page. Actual full-file sample summaries: 183 Normal, 817 Malicious, quality 100/A, 999 High, 1 Review and zero rejected. No runtime exceptions; session summary remained 257 bytes. The first returned page had no Review malicious rows, so its important preview consists of High malicious predictions; mock tests verify higher-priority categories.

A temporary PyMuPDF installation outside project environments opened and rendered the downloaded PDF. Every expected section/value matched the active response mapping, selected positions matched exactly, and geometric checks found zero clipped or overlapping text lines. Rendered pages were visually inspected, including the header/quality page, important-record page and limitations page. This is automated real-browser export with reader validation and visual inspection, not a claimed human manual test. `pdf_validation.json` records the check. The temporary reader is not a project dependency.

## Limits and Phase 15

This is a bounded decision-support report, not an exhaustive event archive. Important-record selection covers only the returned result window, not all 82k+ records. The full backend summary may therefore report review records outside the exported window. Backend-truncated evidence cannot be reconstructed. Analysis timestamps are unavailable. Standard PDF fonts normalize common punctuation; arbitrary international filename glyphs are not guaranteed by the current font set.

Phase 15 recommendation: add expiring backend analysis IDs and bounded page/filter endpoints, then user-controlled result pagination. Keep server-side selection tied to the same analysed dataset, preserve probability/reliability distinctions and official evaluation provenance, and keep full responses out of browser storage. Add an authoritative analysis timestamp with the reusable analysis metadata so future reports can cite it without guessing.
