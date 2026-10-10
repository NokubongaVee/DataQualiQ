# Phase 8: combined network analysis and input reliability

The Phase 8 reusable service and integrity policy below remain. Phase 9 finalizes
the HTTP response sections; see [the current API contract](../phase9/README.md).

`backend/ml/combined_analysis.py` coordinates the existing Phase 2 quality pipeline and Phase 7 saved-model prediction service. It adds no training, model changes, new quality detectors or preprocessing rules. The frontend is unchanged. The separate `/assess` and `/predict-network` routes remain available.

## Endpoint and service

`POST /analyze-network?offset=0&limit=100` accepts one multipart CSV `file`, with the existing 50 MiB upload limit. Offset is nonnegative; limit is 0–1,000. Limit 0 requests a full-file summary without records.

```powershell
curl.exe -F "file=@network.csv" "http://localhost:8000/analyze-network?offset=0&limit=100"
```

```python
from ml.combined_analysis import analyze_network

result = analyze_network(dataframe, 'network.csv', offset=0, limit=100)
```

`CombinedAnalysisService` can receive a `NetworkPredictionService` instance and an explicit `duplicate_review` policy (default False). Exact required features, types, categorical mappings and normalization configuration come from the saved artifact. No target, identifier or attack category is required. Missing predictive columns reject the request with HTTP 422 and an explicit `missing_fields` list. Invalid individual required values reject their rows while retaining other rows for prediction.

## Exact row linking

All findings and combined records use zero-based positions in the original supplied DataFrame/CSV data rows, excluding the header. The quality pipeline already resets its local index; the orchestrator uses the same reset positions. Original DataFrame index labels, including duplicates, are not used as join keys, and input data is not modified.

Within each batch, an explicit array of original positions identifies rows accepted for prediction. Phase 7 predicts that subset; each subset-relative `record_index` is mapped back through that array. Rejected rows remain in the original page with null prediction/probability fields. Neither rejection nor pagination shifts neighboring findings onto another prediction. Finding positions outside the source population fail explicitly; findings without row evidence are counted as unlinked, not assigned arbitrarily to every record.

## Defendable policy: input_integrity_v1

Reliability describes predictive-input integrity under known checks, not model accuracy, calibrated certainty or the overall dataset score. The policy uses no model-probability thresholds.

| Status | Rule | Meaning |
|---|---|---|
| High | Prediction succeeded, with no unresolved predictive-field quality/error flag, missing predictive cell or unseen category | Input passed the known integrity checks; this does not guarantee a correct class |
| Review | Prediction succeeded, but a relevant noncritical quality/error flag, handled missing cell or unseen category exists; optionally a duplicate under configured policy | The model produced an estimate, but the documented input issue warrants human review |
| Low | Prediction rejected because a required value violates the saved structural rules, finite model representation or reserved-category contract | No trustworthy prediction was produced; class and probabilities are null |

Critical predictive errors take precedence over Review. Low does not mean a fabricated prediction with a low probability. The service never silently replaces structurally invalid values. Ordinary missing cells use the existing saved training median or missing-category indicator and receive Review, not an invented "significant missingness" threshold. Rejected rows do not claim that missing values were imputed, because they never reached prediction.

Unseen categories receive Review because the saved encoder represents them with an all-zero block: there is no learned training category information for that value. This is an input coverage concern independent of model probability. Encoder vocabulary and encoded width remain unchanged.

The existing categories are preserved exactly: `data_error`, `quality_issue`, `analytical_security_anomaly`. Findings affecting required predictive columns (or explicitly related predictive columns) inform reliability. Errors in optional/nonpredictive fields remain visible but do not establish corruption of the model's projected input. Relevant representation/candidate quality flags conservatively remain Review rather than being treated as proof of incorrect data.

### Findings that do not automatically lower reliability

- IQR outliers, relationship deviations and other `analytical_security_anomaly` findings: unusual traffic can be attack evidence. An anomaly is not automatically bad input.
- Exact duplicates under the default preserve/detect-only policy: identical network observations can be legitimate repeated events. Findings remain attached, but duplication alone does not corrupt the row's feature values. `duplicate_review=True` explicitly changes duplicate rows to Review, never automatically Low.
- Findings solely about excluded/nonpredictive fields: they are shown separately from predictive input integrity.
- Model probability and overall quality score: neither selects the reliability status.

No thresholds were tuned or inferred from the official test results. This is a transparent first integrity policy requiring future domain validation; High means only that implemented checks found no qualifying integrity issue.

## Output and bounded evidence

Each page record includes the existing Phase 7 fields (`record_index`, numeric `prediction`, readable `label`, `probability_normal`, `probability_malicious`, `predicted_class_probability`) plus:

- `prediction_status`: Predicted or Rejected.
- `quality_status`: Issue detected or No issue detected. High rows can still have analytical/duplicate findings.
- `quality_findings`: compact original finding references/categories/reasons for that row.
- `quality_finding_count`, complete distinct `quality_finding_categories`, and `quality_findings_truncated`.
- `missing_predictive_fields` and `preprocessing_handled_missing` with saved handling methods for predicted rows.
- `reliability` and a concrete `reliability_reason`.

For rejected rows the prediction, label and all probabilities are null. Their Low reason identifies the invalid feature/error rather than inventing an attack classification. Model probabilities remain explicitly described as estimates, not necessarily calibrated confidence.

The full-file summary contains `records_analysed`, `records_predicted`, `normal_count`, `malicious_count`, `average_predicted_class_probability`, `data_quality_score`, `grade`, `high_count`, `review_count`, `low_count`, `rejected_count` and `processing_seconds`. The probability average covers successful predictions only and is null if every row was rejected. High + Review + Low = all records; rejected count is the Low subset, not an additional reliability category. Normal + Malicious + rejected = all records. Outlier occurrence totals remain in the separate quality summary.

Other sections expose aggregate existing quality categories/check counts/score policy, missing/unseen counts, warnings, artifact identification and policy version. Full quality evidence arrays and translated/recommendation trees are not returned by this endpoint. `/assess` retains its original response contract.

At most 1,000 original-position records are returned. Finding details are capped at 10 per row and 1,000 across the entire page; reasons/column labels are compact. Full per-row finding counts and distinct categories remain available even when detail is truncated, and reliability is computed from all findings rather than the truncated display. This prevents repeating the prior huge combined/browser response problem. A 10,000-row synthetic test checks response size and summary coverage.

## Functional validation

The unchanged first 1,000 official testing records were used as a functional input with predictive columns only, not for training or tuning. All fit/fit_transform methods were blocked. See [functional_validation.json](functional_validation.json) for the actual timed run and sample records.

| Measure | Result |
|---|---:|
| Analysed / predicted | 1,000 / 1,000 |
| Normal / Malicious | 183 / 817 |
| Average predicted-class probability | 90.0381% |
| Data quality score / grade | 85 / B |
| High / Review / Low | 999 / 1 / 0 |
| Rejected | 0 |
| Processing time | 4.9802 seconds |

The single Review is an unseen `state` occurrence. Thirty analytical outlier findings (2,973 occurrences across fields, not distinct rows or malicious counts) remain visible without reducing reliability. A duplicate finding covers 256 repeated row occurrences; rows were preserved without reliability penalties under the default policy. The existing dataset score nevertheless penalizes duplication. This demonstrates why the dataset score and row input reliability are separate. No data was changed to force Low results.

Run from `backend`:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\venv\Scripts\python.exe -B -m unittest discover -q
.\venv\Scripts\python.exe -B -m ml.check_combined_analysis
```

Tests cover exact identity with nonunique indexes and rejected rows, clean High, missing/imputed Review, invalid predictive values and all-rejected output, outlier exclusion, configured duplicates, unseen categories, probability/score independence, ancillary errors, full-file counts, pagination and bounded detail under 10,000 rows, no fitting and a live combined HTTP upload. Existing assessment and prediction tests remain included.

All **259 backend tests passed**, including 19 new combined-analysis tests. Saved model/preprocessor checksums remain unchanged, and the scoped whitespace check passed.

## Files and practical limitations

Inspected: quality pipeline, finding categories/evidence, network schema/validators, missing-value semantics, saved artifacts, Phase 7 predictor and existing API/test helpers. Created: `backend/ml/combined_analysis.py`, `backend/ml/check_combined_analysis.py`, `backend/test_combined_analysis.py`, this policy/report and functional validation JSON. Modified: `backend/main.py` and `backend/README.md` to expose/document the separate route.

The quality engine still materializes its full assessment/evidence internally; this phase bounds the response rather than rewriting Phase 2. CSV parsing still loads the full file. Prediction uses sparse batches. Fetching another page currently requires reuploading and recomputing the analysis; no reusable job/result store exists. Timings are single-run hardware-dependent measurements. Valid categories are not necessarily familiar to the model; High does not prove semantic correctness or prediction accuracy. Existing model false-alarm/generalization limitations remain.

## Phase 9 recommendation

Integrate this combined contract into the existing frontend without redesigning its layout. Show probability estimates and input reliability separately, expose concrete reasons and rejected-row states, and keep anomaly/duplicate context visible. Before repeated detail browsing, add a bounded, expiring server-side analysis/result store with reusable pagination to avoid reuploading/recomputing. Keep complete analysis out of browser storage, preserve original positions through views/exports and add frontend integration tests for missing active sessions, large responses and rejection states. Do not retrain or claim calibrated confidence.
