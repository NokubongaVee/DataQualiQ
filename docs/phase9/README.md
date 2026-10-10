# Phase 9: final combined backend response contract

`POST /analyze-network` now exposes seven distinct result sections, plus the uploaded filename. The existing Phase 8 service still computes the combined analysis and preserves its reusable service output; `backend/ml/analysis_response.py` projects that output into the final wire contract. The endpoint no longer exposes the old mixed top-level `summary`, internal saved-evaluation object or internal audit trees. Existing `/assess` and `/predict-network` contracts remain unchanged. No frontend, Phase 2 rules, Phase 3 preprocessing or saved artifacts were modified.

## Request and section meanings

Upload a CSV as multipart `file`, with query parameters `offset` (default 0, minimum 0) and `limit` (default 100, range 0–1,000). The existing 50 MiB upload limit and required predictive feature checks remain. No labels, identifiers or attack category are required.

```powershell
curl.exe -F "file=@network.csv" "http://localhost:8000/analyze-network?offset=0&limit=100"
```

| Section | Meaning and fields |
|---|---|
| `data_quality` | Current-upload `score`, `grade`, `label`, missing/duplicate/invalid/inconsistency/analytical summaries, existing finding category totals, score policy, warnings, compact schema audit and unlinked finding count |
| `intrusion_summary` | Current-upload `records_analysed`, `records_predicted`, `rejected_count`, `normal_count`, `malicious_count`, `average_predicted_class_probability`, `processing_seconds` and probability description |
| `model_performance` | Saved official-test `accuracy`, `precision`, `recall`, `f1`, confusion matrix and orientation/labels, evaluation source/dataset/phase, evaluated record count, positive class and artifact identification |
| `reliability_summary` | Current-upload High, Review, Low and rejected counts; full-file Normal/Malicious cross-counts by High/Review; Phase 8 integrity policy and interpretation |
| `records` | Bounded original-position records with predictions, probabilities, quality findings/categories, missing handling, reliability/reason and explicit `rejection_reason` |
| `pagination` | Offset, requested limit, returned count, total count, `has_more` and optional `next_offset` |
| `recommendations` | Bounded, evidence-based human decision support: priority, message, reason and affected record count |

### Quality counts

Each of `missing_values`, `duplicates`, `invalid_values`, `inconsistencies`, and `analytical_anomalies` contains `finding_count`, `occurrences`, `affected_records`, bounded `by_column` and `columns_truncated`.

Occurrences count detector observations across fields; affected records count the union of explicit source-row positions within that group. Neither is an attack count. Group record counts can overlap. Existing `data_error` findings populate invalid values; non-missing/non-duplicate `quality_issue` findings populate inconsistencies, including uncertain category/representation candidates rather than asserting those are confirmed invalid values. `analytical_security_anomaly` findings remain in the separate analytical group. Duplicate counts exclude the first occurrence and preserve source rows under the existing detector/policy. Finding groups with no row evidence do not invent affected positions; unlinked findings are reported separately.

The score and grade come directly from the unchanged quality engine. For example, its duplicate penalty can lower the dataset score even though individual duplicate predictions retain High reliability under the default Phase 8 policy.

### Official metrics versus this upload

`model_performance.source` is `official_test_evaluation`, `evaluation_phase` is 5, and `is_current_upload_metric` is always false. The dataset is explicitly the saved schema's reserved official testing split. The selected Random Forest was evaluated on 82,332 official testing rows. Metrics are copied from `model_metadata.json`'s `phase5_evaluation`, not computed from uploaded rows or labels.

Metric values are fractions in [0, 1]; display percentages by multiplying by 100. Precision, recall and F1 refer to Malicious = 1. The confusion matrix uses actual classes as rows and predicted classes as columns in [Normal=0, Malicious=1] order. Saved evaluation consistency is validated. Missing/invalid evaluation metadata produces a structured 503 error rather than fake/default model metrics.

Providing a `label` column does not turn this endpoint into a model-evaluation feature. The existing quality engine may assess that column, but predictions use only saved predictive features and official metrics remain unchanged. Model selection used the official test split, so the displayed metrics are not a fresh independent estimate of the selected winner.

### Probability and reliability

`average_predicted_class_probability` is the mean over successful predictions only, not over just the displayed page; it is null if all rows are rejected. Individual probabilities are model estimates and are not guaranteed or necessarily calibrated confidence. They do not determine integrity reliability.

Phase 8 rules remain: High for successful predictions without qualifying input issues; Review for handled missing/unseen predictive values or relevant noncritical quality concerns; Low for rejected invalid predictive inputs. Rejected rows retain original positions, null classes/probabilities and an explicit rejection reason. High + Review + Low equals all records; rejected count is the Low subset. Normal + Malicious + rejected equals all records.

### Pagination and bounds

Summaries and recommendations always cover the full file. At most 1,000 record results are returned; limit 0 returns summaries with no records. `has_more` means rows exist beyond `offset + returned_records`; a summary-only request at offset 0 can therefore have `has_more=true` without a `next_offset`. Choose a positive limit to retrieve rows. Offsets beyond the file yield an empty page with `has_more=false`.

The existing evidence limits remain: 10 finding details per row and 1,000 across the page, with complete distinct categories/counts and truncation indicators. Column breakdowns are capped at 100 per summary group, and column labels/reasons are compact. No full row evidence arrays, full translated assessment trees or all prediction records appear in the wire response.

There is still no persistent result/job store. Each page currently requires reuploading and reanalysis; `next_offset` is a window index rather than a stored-result URL. Internally the quality engine still materializes its full evidence, and CSV parsing still uses a full DataFrame.

## Recommendation rules

Recommendations are emitted only when measured counts support them:

- Prioritise malicious predictions with Review reliability, using exact whole-file cross-counts.
- Investigate all model-predicted malicious records with independent security evidence.
- Inspect rejected rows and correct required inputs before reanalysis.
- Review missing source values or explicit invalid-value findings.
- Preserve analytical anomalies for contextual investigation, without calling them attacks or bad input.
- Check duplicate event provenance before changing record totals.

No recommendation orders automatic traffic blocking or declares an attack confirmed. Counts refer to distinct affected records or explicit predicted/rejected counts, not summed IQR occurrences. Recommendations may overlap and their counts should not be added together. With no supported condition, an empty recommendation list is legitimate.

To obtain malicious-with-Review counts without storing every prediction, Phase 8 now partitions accepted batch positions by its already-decided integrity status and predicts each row exactly once. Original positions are mapped back identically, and full-file counts remain available even with limit 0. The saved estimator, preprocessing and reliability policy are unchanged.

## Response example

Below is a selected-field example from the real HTTP validation; the complete seven-section response, including all returned row fields and four recommendations, is stored under `response` in [functional_validation.json](functional_validation.json).

```json
{
  "filename": "network_sample.csv",
  "data_quality": {
    "score": 85.0,
    "grade": "B",
    "duplicates": {"occurrences": 256, "affected_records": 256},
    "analytical_anomalies": {"occurrences": 2973, "affected_records": 706}
  },
  "intrusion_summary": {
    "records_analysed": 1000,
    "records_predicted": 1000,
    "rejected_count": 0,
    "normal_count": 183,
    "malicious_count": 817,
    "average_predicted_class_probability": 0.9003807236044477
  },
  "model_performance": {
    "source": "official_test_evaluation",
    "dataset": "UNSW-NB15 reserved official testing split",
    "is_current_upload_metric": false,
    "records_evaluated": 82332,
    "accuracy": 0.8641111596948938,
    "precision": 0.8068737417313776,
    "recall": 0.9902055942821848,
    "f1": 0.889188225506121,
    "confusion_matrix": [[26256, 10744], [444, 44888]]
  },
  "reliability_summary": {
    "high_count": 999,
    "review_count": 1,
    "low_count": 0,
    "rejected_count": 0
  },
  "records": [
    {
      "record_index": 0,
      "prediction": 1,
      "label": "Malicious",
      "probability_normal": 0.14025538816577743,
      "probability_malicious": 0.8597446118342225,
      "predicted_class_probability": 0.8597446118342225,
      "reliability": "High",
      "rejection_reason": null
    }
  ],
  "pagination": {
    "offset": 0,
    "limit": 10,
    "returned_records": 10,
    "total_records": 1000,
    "has_more": true,
    "next_offset": 10
  },
  "recommendations": [
    {
      "priority": "high",
      "message": "Investigate model-predicted malicious records using independent security evidence.",
      "reason": "817 records were predicted Malicious. A probability estimate does not establish a confirmed attack.",
      "affected_records": 817
    }
  ]
}
```

## Errors

Upload/schema/artifact/analysis failures use FastAPI's `detail` envelope with a stable `code` and safe `message`; missing-feature failures also list `missing_fields`. Statuses remain 400 for CSV/type/size problems, 422 for input/schema errors, 503 for unavailable/incompatible artifacts or official evaluation metadata, and 500 for unexpected analysis failures. FastAPI query/multipart validation uses its standard structured 422 details. No internal stack traces are returned. Row rejection is a successful analysis with explicit per-row null prediction/reason, rather than a fabricated class or whole-file error.

## Validation and files

The actual `/analyze-network?offset=0&limit=10` endpoint was run in a temporary API process against 1,000 unchanged official testing rows, projected to predictive features only. Fitting methods were forbidden in that API process. Results: 183 Normal, 817 Malicious, mean predicted probability 90.0381%, quality score 85/B, High 999, Review 1, Low/rejected 0, ten returned rows and four recommendations. The one Review malicious record was counted despite not depending on the requested page. All official metrics matched saved metadata. Exact timing and response size are recorded in the functional report.

Tests cover the seven sections, measured quality group unions/occurrences and bounded column detail, official metric attribution and equality, unlabeled/labeled-upload separation, separate quality/probability/accuracy meanings, full-file reliability cross-counts without page records, evidence-based recommendations, explicit rejection reasons, missing evaluation errors and pagination. Existing Phase 8 row/policy/bounds tests and `/assess` and `/predict-network` tests remain.

All **274 backend tests passed**. The final HTTP run took **5.4392 seconds** for the core combined analysis and returned **17,091 bytes** with ten row records. Saved model/preprocessor checksums remained unchanged, API metrics matched the Phase 5 Random Forest report, and the scoped whitespace check passed.

Inspected: Phase 8 combined service/route/tests/documentation, Phase 5 evaluation report, Phase 6 metadata, quality scoring/category semantics and current prediction pagination. Created: `backend/ml/analysis_response.py`, `backend/ml/check_analysis_api.py`, `backend/test_analysis_response.py`, this contract and functional validation JSON. Modified: `backend/ml/combined_analysis.py`, `backend/main.py`, `backend/test_combined_analysis.py`, `backend/README.md` and a Phase 8 documentation pointer. Phase 8 endpoint tests now assert the final wire sections; its reusable service still returns its existing internal summary.

## Phase 10 recommendation

Integrate the finalized contract into the existing frontend: display current-upload quality and intrusion summaries, official metrics with source labels, separate probability and reliability, concrete rejection reasons and human decision-support recommendations. Use only bounded pages and keep full analysis out of browser storage. Add frontend contract/session/pagination tests. Before repeated large-file browsing, implement a bounded, expiring backend result store so pagination can reuse completed analysis rather than repeat uploads. Do not retrain or redesign the frontend without an explicit subsequent requirement.
