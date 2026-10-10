# Phase 3: network dataset preparation

> This document describes the training-data preparation stage. The completed application uses the saved Random Forest and fitted preprocessor without upload-time fitting. See the [current backend instructions](../README.md) and [final project documentation](../../docs/phase17/README.md) for inference, reliability and verified results.

This layer prepares features and labels without training a classifier. It does not change the frontend, API or generic Phase 2 quality rules.

## Existing architecture reused

- `csv_loading.load_csv` preserves raw CSV spellings and missing markers. Official training/testing files are loaded separately and their hashes checked after preparation.
- `generic_checks.check_missing` and the shared `value_utils.missing_mask` report missing values under the existing blank/null-marker policy. ML handling does not suppress quality findings.
- `finding_categories` classifies missingness and duplication as quality issues, and statistical extremes as analytical/security anomalies. Outliers are retained.
- `NetworkSchema` and `FieldRule` provide explicit types and protected target/leakage/identifier fields. No UNSW names occur in the reusable ML implementation.
- Phase 2 `preprocess_network` applies explicit normalization policies, protects fields, preserves raw-row duplicate semantics and produces a source-position audit. Phase 3 adds learned imputation and encoding after safe preparation; it never changes assessment input.

## Policies

Numeric features use `SimpleImputer(strategy='median')`, fitted on usable training rows only. Testing and future uploads reuse the same fitted medians. A completely missing numeric training feature fails with a clear error rather than receiving a guessed zero. Present invalid, non-finite or schema-invalid values require review and fail ML preparation; they do not silently become missing values.

Categorical missing values use the reserved `__dataqualiq_missing__` category, with its own one-hot indicator even if training has no missing values. A source category that collides with this reserved marker is rejected. Existing categories, including UNSW's service `-`, are preserved. Unseen testing/future categories encode to an all-zero block and are counted in the audit; the encoder is never fitted on testing data.

Sparse `OneHotEncoder` avoids imposing a numeric order on nominal categories and supports later Decision Tree/Random Forest workflows. Encoder categories and exact feature names/order remain in the fitted object. Numeric columns appear first, followed by one-hot blocks. Matrices are finite float64 SciPy CSR matrices. No scaling is introduced for the planned tree models. Numeric parsing uses float64; values beyond its finite range are rejected, and ordinary floating-point representation limits still apply.

The UNSW configuration trims outer whitespace from `proto`, `service` and `state`, lowercases only the explicitly case-insensitive `proto`, and preserves service/state case. Other schemas use explicitly supplied policies rather than these column names.

Duplicates default to `detect_only`: repeated network traffic can be legitimate, and deleting it would change frequencies/class balance without a provenance justification. The existing `remove_exact` policy is supported only with explicit permission and a reason, before labels and features are aligned. Exactness refers to raw full rows, not rows made equal by normalization. It is not a promise to deduplicate predictors after protected fields are excluded. The official workflow preserves all duplicate rows.

Targets must have an explicitly binary schema. Missing/invalid targets are reported and excluded, never imputed. Source row positions are retained by `prepare_supervised_dataset` so labels remain aligned; testing target exclusions are also audited. Future `transform` inputs may omit targets. `fit` expects training data already checked by supervised preparation; it deliberately never inspects target values to learn predictors.

## Reuse

From the backend directory:

```powershell
.\venv\Scripts\python.exe -B -m ml.prepare
.\venv\Scripts\python.exe -B -m unittest discover -q
```

The preparation command runs the unchanged configured Phase 2 assessment on each official file, produces all four matrices in memory and writes the compact audit to `docs/phase3/validation.json`. It saves no fitted object or matrix artifact. Dataset-specific choices live in `ml/configs.py` and reuse `domains/network/configs.py`.

For Phase 4, call:

```python
from ml.prepare import prepare_official_split

prepared = prepare_official_split(
    '../data/UNSW_NB15_training-set.csv',
    '../data/UNSW_NB15_testing-set.csv',
)
X_train, y_train = prepared.X_train, prepared.y_train
X_test, y_test = prepared.X_test, prepared.y_test
preprocessor = prepared.preprocessor
```

Alternate schemas use `NetworkMLPreprocessor(schema, normalization_policy)` with `fit`, `transform`, `fit_transform` and `get_feature_names_out`. Every predictive field needs an explicit schema type; future transforms require all fitted feature columns but ignore extra non-selected columns. Fit accepts only predictors selected by the schema and never learns from target/leakage/identifier columns. Imputation operations and unknown categories appear in `last_audit_`; `fit_audit_` retains training-fit metadata. The object contains the schema, policies, imputer, encoder and output order needed for later joint model/preprocessor persistence. Tests round-trip it in memory only.

## Phase 4 recommendation

Train Decision Tree and Random Forest using the returned `X_train` and `y_train`. Tune using folds drawn only from the official training data, fitting a fresh preprocessor inside each fold. Keep the official testing data untouched until final evaluation. Reuse the final training-fitted preprocessor for testing and future uploads; save it together with the trained model and feature/schema metadata in the later persistence phase. Do not add scaling, outlier removal, oversampling or new quality rules as an automatic part of model training.
