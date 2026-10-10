# Phase 10: frontend upload to combined backend analysis

The main cybersecurity Upload & Analyse flow now sends the selected CSV to `POST /analyze-network?offset=0&limit=100`. The existing upload page structure, heading, supporting copy, styling, file card and navigation remain. This phase changes no backend logic, model/preprocessor artifacts, Phase 2 rules or Phase 3 preprocessing.

## API client and file boundary

`frontend/src/api/networkAnalysis.js` exposes `analyzeNetwork(file, {offset, limit, signal})`. It uses `VITE_API_BASE_URL`, defaulting to the previous backend URL `http://localhost:8000`. `.env.example` documents configuration. Multipart FormData contains `file`; the browser supplies its boundary rather than forcing a Content-Type header. The client parses and validates the structured response without flattening its sections.

The browser validates selection, `.csv` extension, empty file and 50 MiB size. It does not inspect or duplicate the 42-feature schema. Missing fields and other network compatibility failures remain the backend's decision. A selected filename is visible on the upload card/header.

The helper performs exactly one request. It neither follows `next_offset` nor accumulates pages. It supports a bounded offset/limit abstraction for future analysis IDs, but does not implement a server-side result store.

## Processing and submission safety

While the request runs, the Analyse button, Choose File button, native file input and drop interactions are disabled. An immediate ref guard prevents duplicate calls even before React commits the disabled state. The request uses an AbortController and a version guard; leaving Upload aborts the client request and prevents stale responses from publishing. Backend work may continue after client cancellation because server-side cancellation is not implemented.

The existing processing panel lists:

1. Reading dataset
2. Checking data quality
3. Preparing network features
4. Running intrusion detection
5. Preparing combined results

The highlight advances illustratively during the request and stops at the last stage. All timing is explicitly approximate, not live backend telemetry. Workflow cards await the combined response; no stage is declared complete and no percentage is fabricated. Controls return to a usable state after failure.

## Authoritative memory state and safe persistence

The existing `App` state remains the sole active-result store. Its `result` receives the exact validated response object, preserving `data_quality`, `intrusion_summary`, `model_performance`, `reliability_summary`, `records`, `pagination`, `recommendations` and other backend fields.

Official metric metadata (`source=official_test_evaluation`, `is_current_upload_metric=false`) stays intact. Probability fields and High/Review/Low reliability remain separate. Pagination preserves the actual backend names: `offset`, `limit`, `returned_records`, `total_records`, `has_more`, `next_offset`. Only the returned page is in memory; no automatic page-fetch loop runs.

`frontend/src/utils/networkAnalysis.js` persists the following explicit summary shape under `sessionStorage.networkAnalysisSummary`:

```json
{
  "filename": "network.csv",
  "data_quality": {"score": 85, "grade": "B"},
  "intrusion_summary": {"records_analysed": 1000, "normal_count": 183, "malicious_count": 817},
  "reliability_summary": {"high_count": 999, "review_count": 1, "low_count": 0, "rejected_count": 0}
}
```

The values above illustrate the summary fields, not a hard-coded analysis. Runtime values always come from the current response. Filename/grade lengths are bounded, nested arbitrary values are rejected and persisted summaries are limited to 2 KiB on read. There are no persisted records, evidence, probabilities, recommendations or official metric objects. `currentPage` is the only other analysis navigation storage value. The application does not write full responses to localStorage or sessionStorage.

All summary/navigation writes are guarded. A quota/SecurityError cannot discard the active result or produce an "Analysis failed" message after backend success. Result publication is outside the backend-request error handler. Legacy `assessmentResult` is removed best-effort; old small generic summaries are still readable but are not treated as detailed results.

## Dashboard handoff, routes and refresh

Success publishes the full result to App memory, safely persists the small summary, then navigates to the existing `overview` Dashboard route. No state library was added.

This phase deliberately does not redesign or fully map the Dashboard charts, record table or PDF to the new contract. A small result-ready panel shows the actual filename, analysed/Normal/Malicious counts, quality score/grade, reliability/rejection counts and returned page size using existing panel styling. It labels detailed dashboard/report views as unavailable rather than feeding incomplete combined evidence into legacy components or claiming no findings. Dedicated routes preserve the active result and show the same safe handoff. Existing legacy assessment render/report code remains intact for its original contract.

On refresh App starts without a full result. Saved route/summary may be restored, but the page shows "No active analysis is available. Please upload and analyse the network dataset again." The previous summary is explicitly summary-only. It never reconstructs predictions, findings or reports from storage.

## Error behaviour

Backend structured `detail.message` and missing feature names are rendered as plain React text. Network connection failures, malformed JSON/contracts, unavailable artifacts and server errors produce actionable messages. Missing-field errors explicitly list names such as dur, proto and spkts. No exception stack or error object is rendered. Failed analysis stays on Upload with retry available; aborted/unmounted requests do not overwrite newer navigation or results.

## Verification

Mocked frontend tests cover CSV boundary validation, configured API/multipart requests, one bounded request, contract/source/probability/reliability/page preservation, summary-only persistence for a large response, quota failure with normal navigation, summary-only refresh and backend/network/schema errors. Existing generic presentation and storage regression tests remain.

The headless Edge integration test exercises the actual React handlers twice in one JavaScript turn to prove the synchronous duplicate guard, disabled file/button controls, processing-stage copy, all-section memory state, navigation across result routes, refresh, schema-error retry and a large mocked finding payload with forced quota failure. It then restores native browser APIs and uploads a compatible 1,000-row real CSV through a running Vite frontend and FastAPI backend. Reports/screenshots are written under this directory.

Run from `frontend`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd run test:browser
```

The browser test requires installed Microsoft Edge (or EDGE_PATH), Node 24 and the existing backend virtual environment. The initial sandboxed Edge run could not establish automation; the check was retried with permission outside the sandbox. It runs headlessly and closes only its own services/browser. No browser automation library or new state/test dependency was installed.

## Files and remaining limits

Validation completed: all 40 frontend tests passed, ESLint passed, and the production build passed. Vite reported the retained reporting bundle's large-chunk advisory (656.26 kB, 210.81 kB gzip).

The real headless Edge run passed with zero runtime exceptions. Its 1,000-row official testing CSV retained all original columns: 183 Normal, 817 Malicious, quality 100/A, 999 High, 1 Review, and no Low/rejected records. The response retained the official evaluation source and returned 100 records with `total_records=1000`, `next_offset=100` and `has_more=true`. The persisted summary was only 257 bytes. The quality score differs from the illustrative summary above because this check retained the original identifier column. Forced quota failure also preserved navigation and the full in-memory mocked result. See `browser_validation.json` and `dashboard-handoff.png` for the recorded evidence.

Inspected: UploadPage, Dropzone, App state, session-storage/navigation helpers, Dashboard/detail pages, existing presentation components, API/configuration usage, package scripts/lint and existing browser/statistics tests. Created: network API client, network state/summary utilities and tests, `NetworkAnalysisReady`, `.env.example`, network browser audit, this documentation and validation artifacts. Modified: App, UploadPage, Dropzone, WorkflowSteps, NoActiveAssessment, OverviewPage, AnalysisPages, package scripts, frontend README and refresh text assertions in the existing statistics test.

There is no persistent server-side analysis ID or true reusable pagination yet. Another page still needs reupload/reanalysis. Detailed combined dashboard/table/PDF presentation is deferred; this phase's result-ready handoff does not pretend the legacy generic report contains all combined evidence. Full active results are intentionally lost on refresh. The existing production bundle can still emit a large-chunk advisory because of retained reporting dependencies; bundling redesign is outside this phase.

## Phase 11 recommendation

Map the preserved Phase 9 sections into the existing Dashboard/detail/report components without conflating official accuracy, current-upload quality, model probability and input reliability. Clearly show rejected rows and evidence truncation; calculate no new reliability categories in the browser. Add bounded, expiring backend analysis IDs/result pages before repeated detail navigation, then client page navigation that keeps only required pages in memory. Keep full responses out of browser storage and retain explicit no-active-result behaviour after refresh.
