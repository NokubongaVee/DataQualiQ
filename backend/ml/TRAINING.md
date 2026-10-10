# Phase 4: initial model training

`models.py` defines two initial candidates; `training.py` accepts the existing Phase 3 output and returns fitted estimators plus training metadata. It does not change preprocessing, quality rules, API or frontend.

## Initial settings

Both classifiers use Gini splits, `random_state=42` and `class_weight=None`. Training retains the official approximately 32% Normal / 68% Malicious distribution. There is no SMOTE, resampling or balancing. No parameter search or validation/test metric was used to choose these initial settings.

- Baseline Decision Tree: `max_depth=16`, `min_samples_split=10`, `min_samples_leaf=5`, `splitter='best'`, `max_features=None`. Depth/leaf limits constrain initial complexity and avoid leaves based on individual observations, while retaining all available predictors.
- Main Random Forest candidate: `n_estimators=100`, `max_depth=20`, `min_samples_split=10`, `min_samples_leaf=2`, `max_features='sqrt'`, `bootstrap=True`, `oob_score=False`, `n_jobs=2`. A 100-tree ensemble is a simple initial academic baseline; feature subsampling/bootstrap diversify its trees. Depth/leaf limits constrain resource use. These settings do not establish that the forest is better.

Two forest workers are used instead of all logical CPUs because this development environment has previously experienced memory allocation failures. Native numeric worker pools are limited to one during fitting. Both models are trained sequentially on a single shared CSC float32 conversion of the Phase 3 CSR float64 matrix. Sparse input is never converted to dense. The original matrix/labels are not mutated. Range overflow is rejected rather than clipping Phase 3 extremes. Ordinary float32 precision rounding follows the tree estimator representation.

The sparse fitting representation follows the documented [Decision Tree fit contract](https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeClassifier.html#sklearn.tree.DecisionTreeClassifier.fit) and [Random Forest fit contract](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html#sklearn.ensemble.RandomForestClassifier.fit).

## Reuse and command

From the backend directory:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\venv\Scripts\python.exe -B -m unittest discover -q
.\venv\Scripts\python.exe -B -m ml.training
```

The command uses `prepare_official_split()` with the official files, runs their unchanged Phase 3 preparation and trains each classifier exactly once on `X_train/y_train`. Phase 3 reads/transforms testing data using the existing training-fitted preprocessor; model training never accesses `X_test/y_test`. The two source CSVs are never modified.

Only `docs/phase4/training.json` metadata is written. No estimator, production artifact or prediction endpoint is saved. The CLI's estimators leave memory when the process ends; retain the return value of `run_official_training()` in a Python session to keep both candidates and the fitted preprocessor for later evaluation.

```python
from ml.training import run_official_training, train_prepared_split

# If the Phase 3 output is already held in memory:
trained = train_prepared_split(prepared)

# Otherwise prepare the official split through the existing Phase 3 workflow:
trained = run_official_training(
    '../data/UNSW_NB15_training-set.csv',
    '../data/UNSW_NB15_testing-set.csv',
)
```

`train_models()` has no testing-data arguments. It requires a fitted Phase 3 preprocessor, matching feature width/order, excluded protected predictors, finite inputs and aligned binary targets with both classes. Training summaries record all estimator parameters, seed, training rows/features, duration, classes, tree depth/leaves or forest tree count, library versions and measured sparse matrix bytes. Matrix bytes are not a measurement of whole-process peak memory. No accuracy, precision, recall, F1, confusion matrix, OOB score or winner is calculated in this phase.

## Verification and Phase 5

Small fixtures verify both estimators are fitted, fixed seeds reproduce tree structures, only training matrices are accessed, preprocessing is never refitted, protected fields/invalid labels are rejected, sparse data is not densified, input matrices remain unchanged and small dense callers are handled safely. Full official training is a separate one-time run, not part of unit tests.

Phase 5 should prepare and train both candidates with these unchanged settings, retain the same fitted preprocessor and evaluate both against the reserved official test matrices. Report Accuracy, Precision, Recall, F1 and confusion matrices for `1 = Malicious`, together with class-wise false positives/negatives. Compare those results before selecting a model; do not revise settings against the test set. If tuning becomes necessary, tune only on training folds with fresh fold-specific preprocessing and keep final test evaluation separate. Model selection and production persistence follow evaluation.
