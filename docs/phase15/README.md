# Phase 15: whole-system end-to-end validation

Result: **28 scenarios passed, 0 failed**. Existing regression suites: **274 backend tests and 49 frontend tests passed**. Both virtual-environment dependency checks, ESLint and production build passed. No application defect was found and no application fix was made.

`system_validation.json` records each scenario's name, input, expected result, actual result, pass/fail and notes. Detailed browser cases, suite logs, PDF evidence and filter results accompany it. Results are from actual executions, not inferred success.

## Scope and approach

Two isolated headless Microsoft Edge sessions used real React/Vite uploads and FastAPI. The main session exercised small altered inputs and the **entire** official testing CSV. A second 1,000-row session checked every existing Results filter and expanded record details. Mocking was limited to deliberate unavailable-backend and storage-quota boundary tests and existing UI guard tests; CSV success/failure cases and PDFs used the actual backend.

The main API process forbade RandomForestClassifier.fit, NetworkMLPreprocessor.fit and fit_transform. Existing inference uses loaded saved artifacts, transform, predict and predict_proba; uploads completed with those fitting methods forbidden. Model/preprocessor hashes matched metadata before and after every upload. No saved model was trained or modified. The pre-existing regression suite fits only its isolated scratch fixtures, not the saved selected model.

Fixtures derive from the first twenty official testing rows with label/attack_cat omitted because prediction uploads do not require targets. Each alteration is explicit. Original data files, ML preprocessing, quality rules and frontend design were not changed. Test files are generated in an isolated temporary folder.

## Input scenarios

| Case | Actual result | Status |
| --- | --- | --- |
| Good compatible CSV | 20 analysed/predicted; 4 Normal, 16 Malicious; quality 100; mean predicted-class probability 0.8414665484963063 | Pass |
| Malformed CSV | Unclosed quote rejected: `Could not parse CSV near line 2: unexpected end of data`; active result null, retry enabled | Pass |
| Missing required features | `dur, proto, spkts` listed clearly; active result null, no guesses or predictions | Pass |
| Missing numeric/categorical values | Missing dur/service detected in two rows; saved median/missing-category handling recorded; Review and valid predictions retained; quality 70 | Pass |
| Invalid numeric value | Negative dur detected; one rejected row, null class/probability, specific reason; 19 predictions; quality 92 | Pass |
| Unseen category | Structurally valid new proto audited and encoded using saved behaviour; Review; no fit/refit | Pass |
| Analytical outlier | Extreme but valid duration produces an analytical finding; affected row remains High and predicted; no rejection; quality 100 | Pass |
| Duplicate | Exact repeated row detected once; 21 rows retained/predicted; repeated row remains High; quality 90 | Pass |
| Backend unavailable | Mocked connection rejection gives clear error, clears active result and reenables Analyse | Pass |
| Full official testing CSV | 82,332 rows analysed/predicted; 100 returned rows; bounded response/storage/PDF | Pass |

Altered-input record explanations and group counts are retained in `browser_cases.json`. Selecting a new CSV explicitly clears the previous active result, including before malformed or missing-feature failures.

## Large-file actual values

- File: UNSW_NB15_testing-set.csv, all 82,332 rows.
- Normal: 26,700; Malicious: 55,632; no rejected rows.
- Quality: 100/A. Analytical anomalies remain distinct from errors.
- Mean predicted-class probability: 0.9079187748526718.
- Reliability: 82,327 High, 5 Review, 0 Low, 0 Rejected. Review cross-counts: 2 Normal, 3 Malicious.
- Backend analysis time: 239.47992339998018 seconds. Concurrent regression work was active; no throughput SLA is claimed.
- Current page: offset 0, limit 100, returned_records 100, total_records 82,332, next_offset 100, has_more true.
- Serialized response: 149,930 bytes. Persisted scalar summary: 266 bytes.
- Sampled browser JS heap: 27,371,448 bytes used, approximately 26.1 MiB. This is a sample, not peak browser/backend RSS.
- No runtime exceptions or browser crash.

No additional record pages were requested. Full-file counts are not calculated from the 100-row preview. Probability is not used to invent reliability categories.

## Pages, filters, refresh and quota

Dashboard and all four detailed routes rendered the real response. Official metrics remained `official_test_evaluation` with `is_current_upload_metric=false`; confusion matrix and missed-attack explanations were present. Quality findings distinguish errors, quality issues and anomalies. Reports uses backend recommendations and the active analysis.

All Results filters were exercised on a real 100-row sample page: All 100, Malicious 43, Normal 57, High 100, Review 0 and Low 0. Expanded record details showed original position, class probabilities and reliability explanation. Nonempty Review/Low/rejected rows were verified in altered-input responses and frontend rendering regression tests.

Refresh cleared full App memory, displayed summary-only state and directed back to Upload & Analyse. Empty states on every route are covered by frontend tests. Forced Storage.setItem quota failure preserved a large mocked in-memory result, successful navigation and backend-success status. Two synchronous submissions made only one request; native file input and Analyse button were disabled while processing.

Responsive upload checks retained no document overflow at phone, tablet and laptop sizes. These checks and Edge automation do not imply that every browser and physical device was tested.

## PDF validation

The real Reports button exported `DataQualiQ-network-report.pdf` from the **full** analysis: eight pages, 50,707 bytes, at most twenty important records from the returned page. Expected sections/content were captured from active App memory and compared with reader-extracted text. Every expected value and selected record position matched. Official metrics are labelled as reserved-test results, separate from the current upload. Recommendations are backend text.

Temporary PyMuPDF opened and rendered the PDF; geometric checks found zero clipped or overlapping text lines. Rendered summary/model/reliability pages were visually inspected. The reader is installed only in a temporary directory, not in project requirements. This is automated real-browser export plus PDF-reader and visual inspection, not a claimed human manual session.

## Regression results

- Backend: 274 tests passed in 66.526 seconds, including existing assess/predict/combine regressions.
- Frontend: 49 tests passed, including current state mapping, recommendation labels, PDF bounds, empty states and storage safety.
- `pip check`: clean in backend/venv and the user's root .venv.
- ESLint: passed, including new audit scripts.
- Production build: passed. Existing reporting bundle large-chunk advisory remains.
- Saved artifact checksums: unchanged and match metadata.

See individual `.log` files and `regression_results.json` for exit statuses. No failing checks were ignored.

## Files and reproduction

Created only audit scripts and evidence: `frontend/phase15_system_audit.mjs`, `frontend/phase15_page_checks.mjs`, and the scripts/logs/JSON/PDF/rendered images in this directory. No application source, requirements, trained artifacts or design was modified for Phase 15.

Run browser audits from frontend with `node phase15_system_audit.mjs` and `node phase15_page_checks.mjs`. Run regressions from the project root with `backend/venv/Scripts/python.exe -B docs/phase15/run_regressions.py`. Run the PDF validator after installing the temporary reader at the path stated in `validate_pdf.py`; sandbox permissions may be needed to access that temporary package. Finally run `assemble_validation.py` to combine the successful audit evidence. Reader success and existing browser reports must exist before assembly.

## Limits and readiness

The prototype is ready to proceed to Phase 16 within its tested scope. It remains an uploaded-record decision-support application, not production live-packet protection. Result pages are bounded but lack reusable analysis IDs; another window needs reanalysis. Refresh loses full results by design. Important PDF selection is page-local and evidence can be truncated. Large-file analysis is comparatively slow; peak process memory and concurrent multiuser throughput were not profiled. Existing build size and PDF font limitations remain.

No unrelated enhancements or backend pagination changes were introduced during this validation phase.
