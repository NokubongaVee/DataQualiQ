# Phase 3 validation report

The complete official files were assessed using the unchanged configured Phase 2 pipeline, prepared independently and converted to aligned sparse ML matrices. Source SHA-256 hashes were verified after processing. No frontend/API changes, classifier training, balancing, scaling or outlier removal occurred in Phase 3.

## Files inspected

- `backend/preprocessing/generic_preprocessor.py`, `network_preprocessor.py`, `__init__.py`
- `backend/domains/network/schema.py`, `configs.py`, `validators.py`
- `backend/csv_loading.py`, `value_utils.py`, `generic_checks.py`, `finding_categories.py`
- `backend/pipeline.py`, `check_selection.py`, `finding_evidence.py`, `translator.py`
- `backend/phase2_validate.py`, `test_phase2.py`, `requirements.txt`, `README.md`
- `docs/phase2/validation.json`
- The complete official `data/UNSW_NB15_training-set.csv` and `data/UNSW_NB15_testing-set.csv`

Phase 2 detects missing values independently of ML preparation, classifies duplicates as quality issues and preserves analytical outliers. Schemas map feature types and protect targets, leakage and identifiers. Its conservative preprocessor returns DataFrame copies plus source-position audits; Phase 2 validation stores compact JSON reports. CSV loading preserves raw spellings/missing markers and loads the two files separately.

## Files created and modified

Created: `backend/ml/__init__.py`, `preprocessing.py`, `configs.py`, `prepare.py`, `README.md`; `backend/test_ml_preprocessing.py`; `docs/phase3/validation.json` and this report.

Modified for Phase 3: `backend/requirements.txt` (scikit-learn and SciPy) and `backend/README.md` (usage link). Existing unrelated changes remain outside this phase's scope.

## Data preparation

Numeric features use training-only medians. Missing categories use a reserved explicit indicator, never an existing class. Missing/invalid targets are excluded and audited rather than guessed. The official files contain zero missing values and zero invalid/missing targets, so no imputation or target exclusion was actually needed. Fitted medians still exist for future uploads.

Duplicates use the existing `detect_only` policy because repeated traffic can be legitimate. Both files have zero exact raw duplicates, and zero rows were removed. Explicit `remove_exact` is supported with permission/reason in a preparation policy; it does not mutate CSVs.

Configured normalization trims `proto`, `service` and `state`, lowercases only case-insensitive `proto`, and preserves service/state case and the service `-` category. Actual normalization changes in these files: zero.

Sparse one-hot encoding preserves nominal category distinctions without inventing an ordinal ranking. It is fitted on training features only. Training vocabularies contain 133 protocols, 13 services and 9 states. Three additional reserved missing indicators keep future missing categories distinct, giving 197 encoded columns. Five testing rows use unseen states (`ACC` or `CLO`); they receive all-zero state blocks and are audited. Testing data is never used to expand vocabulary.

## Features and target

Predictive input: **42 features**, comprising **39 numeric** and **3 categorical**.

Numeric features: `dur`, `spkts`, `dpkts`, `sbytes`, `dbytes`, `rate`, `sttl`, `dttl`, `sload`, `dload`, `sloss`, `dloss`, `sinpkt`, `dinpkt`, `sjit`, `djit`, `swin`, `stcpb`, `dtcpb`, `dwin`, `tcprtt`, `synack`, `ackdat`, `smean`, `dmean`, `trans_depth`, `response_body_len`, `ct_srv_src`, `ct_state_ttl`, `ct_dst_ltm`, `ct_src_dport_ltm`, `ct_dst_sport_ltm`, `ct_dst_src_ltm`, `is_ftp_login`, `ct_ftp_cmd`, `ct_flw_http_mthd`, `ct_src_ltm`, `ct_srv_dst`, `is_sm_ips_ports`

Categorical features: `proto`, `service`, `state`.

Excluded: `id` (identifier), `attack_cat` (target leakage) and `label` (target). Target: `label`, with `0 = Normal`, `1 = Malicious / Attack`. Both complete files contain only valid targets; no target was imputed or excluded. Valid extremes remain in the numeric matrices.

## Class balance

| Dataset | Original rows | Final rows | Normal | Normal % | Malicious | Malicious % |
|---|---:|---:|---:|---:|---:|---:|
| Training | 175,341 | 175,341 | 56,000 | 31.9378% | 119,341 | 68.0622% |
| Testing | 82,332 | 82,332 | 37,000 | 44.9400% | 45,332 | 55.0600% |

No resampling or balancing was applied.

## Matrices

| Matrix | Shape |
|---|---|
| X_train | (175341, 197) |
| y_train | (175341,) |
| X_test | (82332, 197) |
| y_test | (82332,) |

X matrices are finite float64 SciPy CSR matrices. Labels are aligned int8 Series. Matrices and fitted preprocessing were produced in memory; only this audit/report is saved. Feature names/order, learned medians, encoder categories, schema and normalization policy remain available on the reusable fitted object for later joint persistence.

## Leakage protections and verification

The official split is never combined/randomly split. Protected columns are projected out before fitting. Targets are used only to validate/select usable labelled rows and prepare y. Medians and category vocabularies are fitted on training rows only; testing/future data uses transform without refitting. No scaler is introduced for the planned tree models. For later cross-validation, fit a fresh preprocessor inside each training fold.

Verification: **178 backend tests pass**, including 16 Phase 3 tests and the existing generic/Phase 2 regression suite. `pip check` reports no broken requirements. Full official-file preparation passed, with unchanged source hashes, expected class balance, aligned matrices and finite sparse values. Tests cover missing numeric/category/target values, invalid targets, unseen categories, duplicate policy, protected fields, leakage, feature exclusion, extremes including median overflow, alternate names, consistent order, generic assessment and in-memory serialization. No frontend build was needed for this backend-only phase.

## Limitations and Phase 4

Unseen categories have all-zero blocks and audit counts; the five unseen testing states were not added to training vocabulary. Present invalid numeric/schema values and all-missing numeric training features require review/explicit policy rather than invented replacements. Dense conversion or high-cardinality categorical features can increase memory use. Numeric features use float64 with its ordinary representation limits; no finite extreme is capped or winsorized. Matrices/preprocessor must be recreated or retained by the Phase 4 caller because they are not saved to disk here.

Phase 4: call `ml.prepare.prepare_official_split`, train Decision Tree and Random Forest on X_train/y_train, tune only within official training folds with fold-specific fitted preprocessing, and evaluate on the official testing data only after tuning. Reuse the final training-fitted preprocessor for testing/future uploads and save it with the model in the later persistence phase. Do not automatically add scaling, outlier removal or oversampling.
