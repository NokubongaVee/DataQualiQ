# DataQualiQ quality and network intrusion-analysis backend

The FastAPI backend serves the saved Random Forest and preprocessor through `/predict-network` and combines quality assessment, predictions, input reliability and recommendations through `/analyze-network`. The independent `/assess` quality endpoint remains available. Uploads reuse saved artifacts without training or fitting.

The repository includes the verified model bundle and official CSVs. Use Python 3.13 and the pinned requirements; do not run artifact/training commands merely to start the application. Later sections document the historical phase workflows and intentionally distinguish preparation, training, evaluation and serving.

See [final architecture and results](../docs/phase17/README.md) and [the combined API contract](../docs/phase9/README.md). Responses contain full-file summaries with bounded record pages; rejected required inputs have no class or probability. Another window requires reanalysis because reusable analysis IDs are not implemented.

See the [main project README](../README.md) for installation, examples, product screenshots, project progress, and limitations. See [Architecture](../docs/ARCHITECTURE.md) for module responsibilities.

```powershell
py -3.13 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run regression tests with `.\venv\Scripts\python.exe -m unittest discover -v`.

Public `sample_data` files are demonstrations, not independently labelled accuracy benchmarks. The original input is never automatically cleaned or overwritten.

## Phase 2: quality, optional domain validation, separate preprocessing

See [Phase 2 audit and validation](../docs/PHASE2_VALIDATION.md) for the rule audit,
full UNSW-NB15 results, file inventory and limitations. IQR and other analytical
candidates no longer reduce the quality score. Existing counts and response fields
remain available; category summaries and domain configuration are additive.

```python
from csv_loading import load_csv
from pipeline import run_pipeline_from_dataframe
from domains.network import NetworkSchema, FieldRule
from preprocessing import FieldPolicy, PreprocessingPolicy, preprocess_network

schema = NetworkSchema(
    fields={"protocol": FieldRule("protocol", case_sensitive=False),
            "duration_seconds": FieldRule("nonnegative"),
            "packets_sent": FieldRule("count"),
            "destination_port": FieldRule("port")},
    target_fields=("truth",), identifier_fields=("flow_id",),
)
df = load_csv(open("flows.csv", "rb").read())
assessment = run_pipeline_from_dataframe(df, network_schema=schema)
policy = PreprocessingPolicy(fields={
    "protocol": FieldPolicy(trim=True, case="lower",
        reason="Exporter declares protocol spelling case-insensitive."),
})
processed, audit = preprocess_network(df, schema, policy, assessment["issues"])
```

Without `network_schema`, assessment remains generic. `/assess` optionally accepts
a JSON `network_schema` multipart form field; existing file-only uploads work as
before. `NetworkSchema.from_dict()` / `to_dict()` support JSON configuration.
UNSW-NB15 names live only in `domains/network/configs.py`, selected explicitly.

Preprocessing returns a copy and an audit, and is **never invoked by assessment**.
The default changes nothing and detects exact duplicates without removing them.
Explicit policies can trim/case-normalize verified representations, convert finite
numbers losslessly, mark independently invalid features as unknown, use approved
constant missing-value policies or reject required invalid/missing rows. Any row
removal requires an explicit policy; exact-duplicate removal additionally requires
permission and a provenance reason. Labels, leakage fields and identifiers are
protected. Reports use zero-based source row positions even with repeated indexes.
Examples are opt-in (`include_examples=True`); reports can still contain source
evidence and should remain development artifacts.

Pass the assessment findings to preprocessing for a full finding-status audit.
When omitted, the audit explicitly records that no assessment findings were
supplied. Learned median/mode imputation, encoding and scaling are deferred to
Phase 3 and must be fitted on training data only. This phase trains no model.

```powershell
.\venv\Scripts\python.exe -B -m unittest discover -q
.\venv\Scripts\python.exe -B phase2_validate.py --unsw ../data/UNSW_NB15_training-set.csv --unsw ../data/UNSW_NB15_testing-set.csv
```

Phase 3 now adds a separate reusable ML preparation layer. See [ml/README.md](ml/README.md)
for training-only imputation/encoding, official split preparation, audits and reuse.
Run `.\venv\Scripts\python.exe -B -m ml.prepare` to produce matrices in memory and
the compact `docs/phase3/validation.json` report. No classifier is trained.

Phase 4 training is separate: see [ml/TRAINING.md](ml/TRAINING.md).
Run `.\venv\Scripts\python.exe -B -m ml.training` to train both initial candidates
on the official training matrices and record `docs/phase4/training.json` metadata.
This does not evaluate the official test set, select a winner or save model artifacts.

Phase 5 evaluation is separate: run `.\venv\Scripts\python.exe -B -m ml.evaluation`
to recreate the unchanged training candidates, evaluate both on the reserved
official test matrices and record `docs/phase5/evaluation.json`. The evaluator
uses Malicious=1 as positive, records confusion counts/classification reports,
and applies a declared recall-weighted comparison policy without test-set fitting
or parameter/threshold tuning. No deployed model artifact is saved.

Phase 6 persistence: run `.\venv\Scripts\python.exe -B -m ml.artifacts` to
recreate only the Phase 5 winner with unchanged parameters on official training
data, save the fitted model/preprocessor and metadata in `backend/models`, and
verify reload consistency. See [Phase 6](../docs/phase6/README.md). Future consumers
can call `ml.artifacts.load_artifacts`; this phase adds no prediction endpoint.

Phase 7 adds saved-model inference in `ml/prediction.py` and the independent
`POST /predict-network?offset=0&limit=100` multipart CSV route. It returns a
full-file summary with at most 1,000 row predictions, using sparse batches and
cached artifacts without fitting. `/assess` stays separate. See
[Phase 7](../docs/phase7/README.md) for schema, probability, errors and pagination
limits; run `.\venv\Scripts\python.exe -B -m ml.check_prediction` for the functional check.

Phase 8 adds `POST /analyze-network?offset=0&limit=100` and the separate
`ml/combined_analysis.py` orchestration layer. It links quality evidence to
original prediction positions, returns explainable High/Review/Low input
reliability, and rejects invalid rows without invented predictions. Responses
contain full-file counts and bounded record/evidence details. `/assess` and
`/predict-network` stay independent. See [Phase 8 policy](../docs/phase8/README.md);
run `.\venv\Scripts\python.exe -B -m ml.check_combined_analysis` for functional validation.

Phase 9 finalizes the `/analyze-network` wire response into `data_quality`,
`intrusion_summary`, `model_performance`, `reliability_summary`, `records`,
`pagination` and `recommendations`. Official Phase 5 metrics are copied from saved
metadata and explicitly marked as not current-upload metrics. Human review
recommendations use full-file evidence and exact class/reliability cross-counts.
See [the final API contract](../docs/phase9/README.md), including a response example;
run `.\venv\Scripts\python.exe -B -m ml.check_analysis_api` for a real HTTP check.
