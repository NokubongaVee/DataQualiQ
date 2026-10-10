# DataQualiQ network-analysis frontend

React/Vite interface for the completed Data Quality-Aware Network Intrusion Detection prototype. Navigation includes Upload & Analyse, Dashboard, Data Quality, Intrusion Detection, Results and Reports. The interface consumes backend recommendations and reliability labels; it does not classify records or invent a second recommendation algorithm.

## Install and run

Use Node.js 24. From `frontend`:

```powershell
npm.cmd ci
npm.cmd run dev -- --host localhost --port 5173
```

Run the backend separately on port 8000; see [backend setup](../backend/README.md). On Linux/macOS use `npm` rather than `npm.cmd`. Copy `.env.example` to `.env` only when changing `VITE_API_BASE_URL`, then restart Vite. The default API URL is `http://localhost:8000`.

## Upload and API integration

Uploads send one multipart request to `/analyze-network?offset=0&limit=100`. The browser checks file selection, CSV extension, empty files and the 50 MiB limit. The backend validates the predictive schema and returns actionable missing-feature/error details. Upload controls disable during processing, duplicate submissions are guarded and stale/aborted client requests cannot replace newer state.

Processing-stage highlights are illustrative, not backend progress telemetry. Successful analysis opens Dashboard. Full-file summaries are separate from the returned record window; no automatic additional page-fetch loop runs.

## Pages and meanings

| View | Content |
|---|---|
| Dashboard | Full-file quality, Normal/Malicious counts, probability, input reliability, official model evaluation, record preview and backend recommendations |
| Data Quality | Actual score/grade, quality groups, field counts, warnings and returned evidence |
| Intrusion Detection | Current predictions, probability and reliability, plus clearly labelled official test evaluation/confusion matrix |
| Results | Returned rows, All/Malicious/Normal/High/Review/Low filters, specific input/rejection reasons and expanded evidence |
| Reports | Combined summary and bounded PDF export from the active analysis |

Model probability is an estimate, not calibrated confidence or input reliability. High means input passed implemented integrity checks; Review means an input issue warrants investigation; Low records are rejected and have no prediction/probability. Official accuracy/precision/recall/F1 describe saved testing results, not the current upload. Analytical anomalies are not automatically confirmed attacks or invalid input.

Recommendation priority, message, reason and affected count come from the backend. Malicious + Review and rejected records receive high attention; Malicious + High is distinguishable as a security alert. The system implements no automatic blocking or firewall action.

## Memory, storage and refresh

The full structured response stays in App memory during navigation. Guarded session-storage writes persist only a bounded scalar `networkAnalysisSummary` and `currentPage`; full records, evidence, recommendations and nested responses are not stored. Storage quota failures cannot invalidate a successful backend analysis. Legacy `assessmentResult` storage is cleaned up best-effort.

Refresh loses the active full response and displays a clear no-active-analysis state. A stored historical summary is explicitly summary-only; detailed results and PDF export require another upload. Another backend result window also requires reupload/reanalysis because reusable analysis IDs are not implemented. Filters operate on the currently returned rows only.

## PDF export

The existing jsPDF report includes actual full-file summaries, official evaluation provenance, input-integrity reasons, selected returned records and backend recommendations. It previews at most twenty important records from the returned window, with bounded findings and explicit limitations. It is not an exhaustive archive of every record. Empty/refresh states do not fabricate reports. See [verified PDF work](../docs/phase14/README.md).

## Tests and build

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

GitHub Actions runs the complete `npm test` script, lint and build. Optional Windows/Edge real-browser integration:

```powershell
npm.cmd run test:browser
node phase15_system_audit.mjs
node phase15_page_checks.mjs
```

These audits require Microsoft Edge (or `EDGE_PATH`), Node 24 and `backend/venv/Scripts/python.exe`, start their own services and write evidence under the phase documentation. The main Phase 15 audit includes the full official testing CSV and may take several minutes. Browser execution may need permission outside a restricted sandbox.

Recorded Phase 15 results: 49 frontend tests, lint and build passed, with real Dashboard/detail/PDF checks and zero failed end-to-end scenarios. Responsive browser checks do not establish universal physical-device coverage. The reporting bundle remains relatively large; no production performance guarantee is claimed.

## Documentation

[Final project documentation](../docs/phase17/README.md) · [Current API contract](../docs/phase9/README.md) · [Detailed page mapping](../docs/phase12/README.md) · [Whole-system validation](../docs/phase15/README.md).

Older generic presentation utilities remain where used by regression/legacy assessment paths. Historical screenshots and phase notes should not be mistaken for the completed interface.
