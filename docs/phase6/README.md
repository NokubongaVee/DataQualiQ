# Phase 6: selected model persistence

Phase 5 selected Random Forest using its declared recall-weighted comparison. Phase 6 recreates only that selected candidate using the existing Phase 3 configuration and Phase 4 model factory, unchanged. The explicit training step recreates the fitted estimator because Phase 5 saved evaluation metadata rather than fitted objects. It does not tune, change the winner, or use the official testing file for fitting; the persistence command never reads that file.

## Artifacts and usage

Artifacts are separate, compressed joblib files:

- `backend/models/intrusion_model.joblib`: fitted Random Forest.
- `backend/models/preprocessor.joblib`: complete fitted `NetworkMLPreprocessor`.
- `backend/models/model_metadata.json`: versioned configuration, feature information, dependencies, timestamps, source/report hashes, artifact checksums and prior Phase 5 evaluation.

From `backend`:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\venv\Scripts\python.exe -B -m ml.artifacts
.\venv\Scripts\python.exe -B -m ml.verify_artifacts
```

The command checks the Phase 5 winner, parameters, training-file hash, feature order and training population before saving. It writes `docs/phase6/reload_verification.json`. No test evaluation or prediction API is added.

```python
from ml.artifacts import load_artifacts

model, preprocessor, metadata = load_artifacts('models')
X = preprocessor.transform(compatible_dataframe)
predictions = model.predict(X)
probabilities = model.predict_proba(X)
```

Future transforms reuse saved medians and category mappings without fitting. Metadata describes exact input names and schema rules; there is no new alias mapping or inferred schema. Missing required columns and invalid numeric/schema values are rejected by the existing Phase 3 transformer. Unknown categories retain the existing all-zero encoding and audit behaviour.

Load only trusted locally produced bundles. Joblib deserialization executes Python objects; checksums catch corruption or accidental mixing, not malicious replacements. The loader checks artifact version, scikit-learn version, file presence/hashes, target mapping, expected feature information, model parameters and model/preprocessor width/order consistency. Metadata is written last as the completion marker; a failed replacement leaves no old valid marker. Concurrent loading while replacing a bundle is not supported.

## Configuration and predictive inputs

Training population: 175,341 official training rows. Raw CSV has 45 columns; 42 are predictive features, excluding `id`, `attack_cat` and `label`. These three fields are not required for prediction. There are 39 numeric features and three categorical features (`proto`, `service`, `state`), yielding 197 encoded features in the saved order.

Required predictive columns:

```text
dur proto service state spkts dpkts sbytes dbytes rate sttl dttl
sload dload sloss dloss sinpkt dinpkt sjit djit swin stcpb dtcpb
dwin tcprtt synack ackdat smean dmean trans_depth response_body_len
ct_srv_src ct_state_ttl ct_dst_ltm ct_src_dport_ltm ct_dst_sport_ltm
ct_dst_src_ltm is_ftp_login ct_ftp_cmd ct_flw_http_mthd ct_src_ltm
ct_srv_dst is_sm_ips_ports
```

Random Forest parameters: 100 trees, Gini criterion, maximum depth 20, minimum split size 10, minimum leaf size 2, sqrt feature sampling, bootstrap enabled, OOB disabled, no class weights, random seed 42 and two workers. Full parameters are in metadata. No balancing, scaling, outlier removal or hyperparameter tuning was introduced.

Saved preprocessing includes the fitted numeric median imputer, all training medians, fitted one-hot encoder with learned categories and reserved missing indicators, original and encoded feature order, network schema and fixed categorical normalization policy. Target meaning remains 0 = Normal, 1 = Malicious. No dataset or row-level findings are embedded in metadata.

## Verification and limitations

The small-fixture regression suite covers file creation, reload without fitting, identical transforms/predictions/probabilities, medians, categories, feature order, optional protected columns, missing predictive columns, missing files, wrong versions and checksum mismatches. It also verifies exact forest probabilities under the sequential verification backend while preserving the saved two-worker configuration.

All **218 backend tests passed**, including 13 new artifact tests. Dependency checks and the scoped `git diff --check` passed.

The official save compares pre-save and reloaded outputs on 32 compatible training rows with no target, identifier or attack category columns. A separate process verifies the recorded fingerprints after the training process exits. The detailed verification result is in `reload_verification.json`.

The first full run saved both artifacts and verified transformations and class predictions. Exact probability comparison initially failed by at most 2.22e-16 because parallel forest accumulation changes floating-point addition order. Verification now uses a sequential joblib backend; saved parameters remain unchanged. The existing fitted artifacts were reloaded and resaved without further training, then all transformation/prediction/probability comparisons passed exactly, including the independent process with fitting methods blocked. Model size is 7,028,935 bytes, preprocessor size 4,144 bytes and metadata size 22,083 bytes.

Phase 5 metrics are provenance from the unchanged evaluated candidate, not a new Phase 6 test evaluation. The selected model still has the Phase 5 false-alarm and missed-attack limitations, possible overfitting/distribution shift and no new independent validation. Use the recorded Python/scientific dependency versions; scikit-learn version mismatches are rejected and cross-version portability is not promised. This bundle also depends on the project modules containing the custom preprocessor/schema classes.

## Phase 7 recommendation

Implement a prediction service that loads this verified bundle once, validates compatible predictive inputs, performs Phase 2 quality assessment separately, and calls only saved-preprocessor `transform` plus model `predict`/`predict_proba`. Add endpoint tests proving there is no fitting. Keep original row provenance, use bounded/paginated record responses for large uploads, and treat probabilities as model scores rather than calibrated certainty. Define reliability mapping and frontend integration explicitly in that phase. Do not retune against the already-used official test set; any tuning requires training-only validation and a fresh evaluation protocol.
