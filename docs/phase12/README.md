# Phase 12: detailed network analysis pages

All four existing routes now use the active seven-section `/analyze-network` response held in App memory. No backend, model artifact, preprocessing rule, Phase 2/3 rule, API request or storage mechanism changed. Legacy generic assessment views and PDF export remain intact. Dashboard and the compact upload page are preserved.

## Pages

Data Quality displays the actual score/grade, five quality summary groups, affected-record and occurrence counts, bounded field summaries, warnings and returned row evidence. Data errors, quality issues and statistical/analytical anomalies have distinct labels. Anomalies are not automatically bad input or attacks. Evidence truncation and overlapping counts are explicit; no sub-scores are invented.

Intrusion Detection reuses the existing SVG donut for Normal/Malicious predictions, with percentages using predicted records only. It displays full-file counts, average predicted-class probability, High/Review/Low/rejected input-integrity counts, and official accuracy/precision/recall/F1. Official source metadata gates performance presentation. The confusion matrix reads the backend's actual [Normal, Malicious] row/column layout, with True Normal, False Alarm, Missed Attack and Correctly Detected Attack cells. False negatives explicitly represent missed attacks. No evaluation metrics are recomputed.

Results displays only `records` already in state, with page metadata using the actual names `offset`, `limit`, `returned_records`, `total_records`, `has_more` and `next_offset`. Prediction/reliability filters operate only on that page. Expandable row inspection shows original one-based data-row position, both class probabilities, predicted-class probability, quality findings, truncation, reliability explanation and rejection reason. Rejected records have no fabricated class or probability.

Reports identifies the filename and presents combined full-file summaries, official metrics, reliability, quality summaries/evidence and actual backend recommendations. It reuses the existing Dashboard presentation rather than duplicating its data mapping. It provides bounded PDF export.

## PDF

`downloadNetworkPdf.js` uses the existing jsPDF dependency. Export includes file/count/quality/prediction/reliability summaries, official metrics and confusion matrix, quality warnings, field details and backend recommendations. It previews at most 20 returned record rows with at most three findings per row. Per-group field detail is capped at ten and warnings/recommendations at twenty. Text is length-bounded. Page wrapping is automatic. Truncation and the current-page limitation are labelled; no extra pages are fetched. Export failures remain local to the Reports page and do not invalidate the assessment. Existing generic `downloadAssessmentPdf.js` is unchanged.

## State and empty pages

No browser storage writes or state libraries were added. Full responses remain only in App memory. Refresh presents the existing no-active-analysis state, an Upload & Analyse action and an explicitly historical summary if available. It does not reconstruct detailed findings or reports.

## Files

Inspected App routes/state, OverviewPage/NetworkDashboard, AnalysisPages, Header, API client, network result/summary and navigation utilities, quality/traffic/model/record components, existing PDF utilities, NoActiveAssessment, styles, tests, browser audit and backend response contract.

Created `frontend/src/components/NetworkDetailPages.jsx`, `frontend/src/utils/downloadNetworkPdf.js`, this documentation and browser validation artifacts. Modified `frontend/src/pages/AnalysisPages.jsx`, `frontend/src/index.css`, `frontend/statistics_audit.test.mjs` and `frontend/network_browser_audit.mjs`.

## Verification

45 frontend tests passed. Added coverage for all four detailed pages, actual quality and official matrix values, bounded rows, rejected probabilities/reasons, evidence, export control, empty states and bounded PDF preview. Existing Dashboard, storage, quota and navigation regressions remain. ESLint and production build passed. The build retains the reporting bundle's large-chunk advisory (677.29 kB main bundle).

Headless Edge exercised a real Vite/FastAPI upload with the first 1,000 official testing rows: 183 Normal, 817 Malicious, quality 100/A, 999 High and 1 Review, with no rejected rows. All four real-result routes passed content checks. The app retained 100 returned records and official evaluation provenance, persisted a 257-byte summary, and had zero runtime exceptions. Mocked schema retry, forced quota failure, duplicate prevention, route navigation and refresh passed. No human manual session was claimed; this was automated real-browser functional verification. `browser_validation.json` records the results.

## Limits and next phase

Detailed finding evidence is available only for returned rows; field summaries may be backend-truncated. Filters are page-local. There is no reusable server-side analysis ID and no fake next-page button; another result window requires reupload/reanalysis. Refresh intentionally loses full results. The PDF is a bounded summary/preview, not an exhaustive event archive.

Next phase: add expiring server-side analysis IDs and bounded result-window endpoints, then wire user-triggered page navigation and server-side filters to those IDs. Keep only needed pages in memory, avoid automatically downloading all records, and preserve the existing official-evaluation/probability/reliability distinctions and summary-only browser storage.
