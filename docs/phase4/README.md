# Phase 4 training report

Both initial classifiers were trained successfully on the full official training matrix produced by the unchanged Phase 3 workflow. Neither model was evaluated on the official testing set. No winner was selected, no production model was saved and no prediction API or frontend change was made.

## Files inspected

`backend/ml/preprocessing.py`, `configs.py`, `prepare.py`, `README.md`; `backend/test_ml_preprocessing.py`; `docs/phase3/README.md`, `validation.json`; `backend/requirements.txt`; existing network schema/configuration. Both official files were loaded only through the existing Phase 3 preparation function.

## Files created and modified

Created: `backend/ml/models.py`, `training.py`, `TRAINING.md`; `backend/test_ml_training.py`; `docs/phase4/training.json` and this report.

Modified for Phase 4: `backend/README.md` to document the training command. Phase 2 rules and Phase 3 feature selection/preparation code remain unchanged.

## Initial configurations

Baseline Decision Tree: Gini criterion, best splitter, max_depth=16, min_samples_split=10, min_samples_leaf=5, max_features=None, class_weight=None, random_state=42. Depth and leaf-size limits constrain complexity and avoid singleton leaves while permitting all predictors.

Random Forest candidate: 100 trees, Gini criterion, max_depth=20, min_samples_split=10, min_samples_leaf=2, max_features=sqrt, bootstrap=True, oob_score=False, class_weight=None, random_state=42, n_jobs=2. This is a simple initial ensemble, with limited depth and bounded parallelism. Parameters were selected without test scores; no hyperparameter search was run.

Class weighting and class resampling were not used. Training retained 56,000 Normal and 119,341 Malicious records. Random Forest's ordinary bootstrap sampling is part of the estimator and does not change the source dataset or introduce class-balancing/oversampling.

## Full training results

| Model | Training records | Encoded features | Fit seconds | Fitted structure |
|---|---:|---:|---:|---|
| Decision Tree | 175,341 | 197 | 9.5282 | Depth 16; 1,270 leaves |
| Random Forest | 175,341 | 197 | 61.4105 | 100 trees |

X_train shape: (175341, 197). y_train shape: (175341,). Both fitted estimators have classes [0, 1]. Fit times exclude Phase 2/3 preparation and are hardware/load dependent; they are not model-quality comparisons.

## Leakage and reproducibility

Only X_train/y_train are passed to estimator.fit. `train_models` accepts no test-data argument; `train_prepared_split` never accesses X_test/y_test. Phase 3 alone reads/transforms the official testing file using its training-fitted state, as before. The official files are never combined. Protected id, attack_cat and label are absent from predictive input; fitted feature order and width are checked. Targets must be aligned finite binary values with both classes present. Imputation/encoding is not refitted by training.

Both models use random_state=42; configuration factories return fresh estimators. Unit tests verify matching tree structures for repeated fixed-seed fixture training. Source hashes match the prior Phase 3 report and both CSVs remained unchanged. The JSON records Python, NumPy and scikit-learn versions along with all parameters, feature names and source hashes.

## Resources and verification

| Representation | Measured/equivalent bytes | MiB |
|---|---:|---:|
| Original CSR float64 training matrix | 57,831,196 | 55.15 |
| Shared CSC float32 fit matrix | 38,087,344 | 36.32 |
| Dense float64 equivalent (not allocated) | 276,337,416 | 263.54 |

Sparse input was never densified. The CSC conversion is shared by both sequential fits. Forest workers are capped at two and native numeric thread pools at one. Matrix bytes do not represent whole-process peak memory or all estimator storage. No memory allocation errors occurred during these full training runs. Float32 overflow is rejected rather than clipping input; normal float32 rounding follows the tree estimator representation.

All **190 backend tests passed**, including **12 Phase 4 tests** plus the existing Phase 2/3/generic suite. Tests cover fitted estimators from Phase 3 output, reproducibility, binary targets, protected fields, train/test separation, no preprocessing refit, feature width/row alignment, sparse safety and original-input preservation, dense small fixtures, range/non-finite guards and JSON CLI output. Dependency checks and diff whitespace checks passed. No frontend build was needed for this backend-only phase.

The first full attempt completed both fits but summary writing failed because scikit-learn returned a NumPy int64 leaf count. The count/depth are now explicitly converted to native integers; JSON serialization and CLI writing are covered by regression tests. A necessary full retry with unchanged parameters produced the complete successful summary above. No test-set tuning occurred during this correction.

## Remaining limitations and Phase 5

No evaluation metrics, training accuracy, OOB score or model winner were calculated. The initial parameters are not tuned or selected as final. Models and the preprocessor are returned in memory by the training functions; the CLI exits after saving metadata, so later callers must retain the returned objects or recreate the training run. No estimator artifact was saved. Phase 3's unknown-category handling remains unchanged, including all-zero blocks for unseen testing states.

For Phase 5, keep the Phase 3 prepared split in memory and call `train_prepared_split(prepared)`. Evaluate both returned estimators on the reserved X_test/y_test with Accuracy, Precision, Recall, F1 and confusion matrices, explicitly treating 1 as Malicious. Inspect false positives/negatives and class-wise results before selecting a model. Do not tune against the official testing set. Any necessary tuning must use training-only folds with fresh fold-specific preprocessing. Save the selected model and its fitted preprocessor only after evaluation/model selection is authorized in the later persistence phase.
