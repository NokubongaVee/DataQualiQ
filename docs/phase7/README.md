# Phase 7: saved-model network prediction

The backend now has a reusable inference service and a separate network CSV prediction endpoint. It loads the verified Phase 6 Random Forest/preprocessor bundle once on first successful use per service/process. It does not train, refit, calculate upload medians, learn new categories or run the full data-quality engine. Phase 2/3 rules, saved artifacts and frontend are unchanged.

## Service and endpoint

`backend/ml/prediction.py` exposes `NetworkPredictionService` and the shared `predict_network_traffic(dataframe, offset=0, limit=100)` function. Metadata supplies the required input features and label mapping. Records use zero-based original input positions, preserving order even when a supplied DataFrame index is non-unique. Source data is not modified.

```python
from ml.prediction import predict_network_traffic

result = predict_network_traffic(network_dataframe, offset=0, limit=100)
```

The API is `POST /predict-network?offset=0&limit=100`, using a multipart `file` upload. `offset` must be nonnegative; `limit` is 0–1,000, with 0 requesting summary only. Only CSV uploads up to 50 MiB are accepted, following the existing assessment upload boundary. `/assess` remains separate.

```powershell
curl.exe -F "file=@network.csv" "http://localhost:8000/predict-network?offset=0&limit=100"
```

Every successful request predicts the entire uploaded dataset for its summary, but returns only the requested bounded window of records. Fetching another window currently requires reuploading and recomputing; there is no persistent prediction job or server-side result store yet. `next_offset` identifies the next window, not a downloadable page URL.

## Inputs and preprocessing

The saved artifact requires 42 predictive columns: 39 numeric fields plus `proto`, `service`, `state`. Exact names, schema rules, medians, categories and encoded order come from `backend/models/model_metadata.json`; the service does not duplicate that list. `id`, `attack_cat` and `label` are never requirements. Extra columns are ignored and listed in the audit.

The exact names are:

```text
dur proto service state spkts dpkts sbytes dbytes rate sttl dttl
sload dload sloss dloss sinpkt dinpkt sjit djit swin stcpb dtcpb
dwin tcprtt synack ackdat smean dmean trans_depth response_body_len
ct_srv_src ct_state_ttl ct_dst_ltm ct_src_dport_ltm ct_dst_sport_ltm
ct_dst_src_ltm is_ftp_login ct_ftp_cmd ct_flw_http_mthd ct_src_ltm
ct_srv_dst is_sm_ips_ports
```

Column order in the upload may differ; the saved feature order is used. Structurally absent features are rejected and explicitly listed. Missing cells in present columns use saved training medians/reserved missing categories under unchanged Phase 3 behaviour. Invalid numeric, non-finite, structurally invalid schema values and values exceeding the estimator's float32 range are rejected rather than guessed or clipped.

Transforms reuse the fitted median imputer and one-hot encoder and yield exactly 197 sparse features for the official model. Valid unseen categories keep the saved all-zero encoding behaviour, with per-field occurrence counts and a warning; they never extend the feature vocabulary. Existing schema-invalid categorical values still fail validation.

## Response contract

`summary` contains real `records_analysed`, `normal_count`, `malicious_count`, `average_predicted_class_probability` and `processing_seconds`. The mean uses all rows, not just the returned window. Time includes service validation, transformation, prediction and response assembly; first-use loading is included when needed, but CSV reading is outside this timer.

Each element of `records` contains:

```json
{
  "record_index": 0,
  "prediction": 1,
  "label": "Malicious",
  "probability_normal": 0.14025538816577743,
  "probability_malicious": 0.8597446118342225,
  "predicted_class_probability": 0.8597446118342225
}
```

This example is an actual record from the functional check. Labels remain 0 = Normal and 1 = Malicious. Probabilities are model estimates, not guaranteed or necessarily calibrated confidence. The response also includes bounded record pagination, artifact version and encoded width, aggregate unseen/missing counts, ignored columns and schema warnings. It contains no full row evidence arrays, quality scores or reliability classifications.

Errors are HTTP 400 for invalid CSV/upload boundaries, 422 for input/schema/pagination failures, 503 for unavailable/incompatible artifacts and 500 for unexpected transform/prediction failures. Missing feature errors return `detail.code`, `detail.message`, and `detail.missing_fields`. Internal failure messages and paths are logged server-side rather than returned as stack traces. No partial success is returned when a later batch fails.

## Large input and concurrency

The service processes at most 4,096 rows per prediction batch, keeps feature matrices sparse and uses a finite float32 estimator representation. It accumulates counts/probability sums and aggregate audits rather than retaining every prediction; at most 1,000 row dictionaries are returned. The CSV loader still parses the full upload into a DataFrame, so this is bounded inference/output rather than fully streaming CSV ingestion.

Requests within one service instance are serialized because the existing preprocessor updates its per-transform audit. Multiple backend workers load separate bundles. Sequential joblib prediction keeps probability accumulation deterministic and matches Phase 6 verification; the saved model parameters/files are unchanged. Successful artifact loading is cached; replacing artifacts requires a service restart. A failed load can be retried after artifacts are restored. Only trusted local joblib artifacts are loaded through the existing checksum/version/schema checks.

## Verification

Small fixtures cover artifacts loaded once, compatible unlabeled input, omitted protected fields, labels/probabilities, row order, unchanged source, missing/invalid numeric values, ignored columns, unseen categories without learning, schema errors, safely reported artifact/transform/prediction failures, pagination, empty inputs, forbidden fit/fit_transform calls and a 10,000-row sparse batch with dense conversion forbidden. Live HTTP checks use four synthetic compatible rows with the official saved bundle and exercise CORS, 197-feature output, pagination and query/schema errors. No official model is trained in these tests.

All **240 backend tests passed**, including 22 new prediction tests. Saved model/preprocessor checksums still match Phase 6 metadata. The scoped whitespace check passed.

Run from `backend`:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\venv\Scripts\python.exe -B -m unittest discover -q
.\venv\Scripts\python.exe -B -m ml.check_prediction
```

The functional check uses the first 1,000 official testing rows with all protected fields removed. Results: **183 Normal**, **817 Malicious**, average predicted-class probability **0.9003807236**, processing time **0.9681 seconds** with artifacts already loaded. One unseen `state` occurrence was audited and encoded safely; there were no missing cells or ignored columns. This is a functional check, not a new accuracy evaluation or tuning step. Fit methods are explicitly blocked. Service outputs on the 32 Phase 6 reference rows match the saved transformation/prediction/probability fingerprints. Details are recorded in [functional_validation.json](functional_validation.json).

Inspected files: `backend/main.py`, `backend/csv_loading.py`, `backend/ml/artifacts.py`, `backend/ml/preprocessing.py`, `backend/ml/verify_artifacts.py`, Phase 6 metadata/verification, and existing backend training/API tests. Created files: prediction service, functional-check module, prediction tests, this report and functional JSON. Modified files: `backend/main.py` (new independent route/status listing) and `backend/README.md` (usage).

## Limitations and Phase 8

Phase 5 model limitations remain: probabilities are not calibrated, false alarms/missed attacks exist, and unknown categories can reduce usefulness. Schema validation alone is not reliability scoring. Timing is a single hardware-dependent observation. There is no result/job store, true streaming ingestion, full-file export, authentication change, reliability logic, dashboard or PDF change.

Phase 8 should combine unchanged quality assessment and saved-model prediction through a new orchestration layer, preserving source row positions and separate quality findings/model probabilities. Define reliability rules explicitly with tests before assigning High/Review/Low labels; do not present probability as certainty or train new models. Add a bounded result store/pagination strategy if users need repeated detail browsing, then integrate the frontend and report views without persisting full responses in browser storage.
