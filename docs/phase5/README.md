# Phase 5: official intrusion model evaluation

Selected model: **Random Forest**, under the recall-weighted policy declared before evaluation. It misses fewer attacks, but Decision Tree has higher accuracy, precision and slightly higher F1. This is a cybersecurity trade-off, not evidence that Random Forest wins every metric or is ready for deployment.

## Data and separation

Both candidates were evaluated on exactly the same 82,332 official testing records: 37,000 Normal and 45,332 Malicious, with 197 encoded features. Training uses the separate 175,341 official training records. Labels are 0 = Normal and 1 = Malicious; all positive-class metrics below refer to Malicious.

Phase 4 saved training metadata rather than fitted estimators. The evaluation command therefore recreates both candidates using the unchanged Phase 4 training functions and Phase 3 training-fitted preprocessing. Only X_train/y_train are fitted. The evaluator itself never fits, and neither hyperparameters nor prediction thresholds were changed using test results. Both models use their default `predict` decision rule. Sparse float32 conversion is the existing estimator representation, not a preprocessing refit.

Decision Tree retains seed 42, Gini criterion, best splitter, maximum depth 16, minimum split size 10 and minimum leaf size 5. Random Forest retains seed 42, 100 trees, Gini criterion, maximum depth 20, minimum split size 10, minimum leaf size 2, sqrt feature sampling, bootstrap sampling and two workers. Neither uses class weights. All parameters, feature order, preparation audit, source hashes and software versions are recorded in [evaluation.json](evaluation.json).

## Official test comparison

| Measure | Decision Tree | Random Forest |
|---|---:|---:|
| Accuracy | 87.0221% | 86.4111% |
| Malicious precision | 82.8576% | 80.6874% |
| Malicious recall | 96.3668% | 99.0206% |
| Malicious F1 | 89.1031% | 88.9188% |
| Malicious F2 | 93.3237% | 94.7164% |
| True negatives | 27,962 | 26,256 |
| False positives | 9,038 | 10,744 |
| False negatives / missed attacks | 1,647 | 444 |
| True positives | 43,685 | 44,888 |
| Test prediction time | 0.0217063 s | 0.8225692 s |

Prediction times measure only one call to `predict` on the full test matrix, excluding preprocessing, training and scoring. They are single-run observations, not latency benchmarks. Recreated training took 7.2064 seconds for Decision Tree and 64.3416 seconds for Random Forest.

Confusion matrices use actual labels as rows and predicted labels as columns, ordered [Normal, Malicious]:

```text
Decision Tree: [[27962,  9038],
                [ 1647, 43685]]

Random Forest: [[26256, 10744],
                [  444, 44888]]
```

The upper-left cell is normal traffic correctly called Normal (TN). Upper-right is normal traffic incorrectly called Malicious (FP, a false alarm). Lower-left is malicious traffic incorrectly called Normal (FN, a missed attack). Lower-right is malicious traffic correctly called Malicious (TP).

## Classification reports

| Model | Actual class | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| Decision Tree | Normal | 94.4375% | 75.5730% | 83.9586% | 37,000 |
| Decision Tree | Malicious | 82.8576% | 96.3668% | 89.1031% | 45,332 |
| Random Forest | Normal | 98.3371% | 70.9622% | 82.4364% | 37,000 |
| Random Forest | Malicious | 80.6874% | 99.0206% | 88.9188% | 45,332 |

The JSON also contains macro and weighted averages.

## Selection and operational trade-off

The primary comparison score is malicious F2: `5 * TP / (5 * TP + 4 * FN + FP)`. This recall-weighted harmonic mean puts greater emphasis on recall while still penalizing false alarms. F1, recall, precision, accuracy and complexity break ties. If all four required metrics differ by at most 0.5 percentage points, lower practical complexity is preferred. This policy was fixed before examining test outcomes; it does not force a particular model to win. [Scikit-learn F-beta documentation](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.fbeta_score.html) explains beta's weighting.

Random Forest wins F2 (94.7164% versus 93.3237%) and recall (99.0206% versus 96.3668%). It misses **1,203 fewer attacks**, at the cost of **1,706 additional false alarms**. Decision Tree wins accuracy, precision and F1, so the selection must not be described as a Random Forest F1 improvement. The similarity rule does not apply because recall and precision differ by more than 0.5 percentage points.

Random Forest incorrectly flags 29.04% of normal test traffic, compared with 24.43% for Decision Tree. Its precision is not declared operationally acceptable without an agreed false-alarm cost or review capacity. F2 is a stated cybersecurity heuristic, not a measured business-cost function.

## Overfitting diagnostics

Training predictions are resubstitution diagnostics, separate from test results and excluded from winner selection.

| Model | Train accuracy | Test accuracy | Accuracy gap | Train F1 | Test F1 | F1 gap |
|---|---:|---:|---:|---:|---:|---:|
| Decision Tree | 96.3106% | 87.0221% | 9.2886 pp | 97.2933% | 89.1031% | 8.1903 pp |
| Random Forest | 96.9066% | 86.4111% | 10.4955 pp | 97.7550% | 88.9188% | 8.8361 pp |

Both exceed the diagnostic five-percentage-point gap threshold. These gaps indicate possible overfitting or training/test distribution shift; they cannot establish which caused the loss. No tuning was performed in response.

## Reuse and verification

From `backend`, the official command is:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\venv\Scripts\python.exe -B -m ml.evaluation
.\venv\Scripts\python.exe -B -m unittest discover -q
```

The command writes this phase's compact JSON report; fitted candidates stay in memory and are discarded when the process ends. It saves no final model artifact.

`ml.evaluation.evaluate_classifier` accepts a compatible fitted binary classifier, not only these two model types. `evaluate_predictions` scores supplied binary predictions, `compare_models` applies the fixed policy, and `evaluate_prepared_split` evaluates already-prepared and trained candidates without fitting. Population/order digests prevent comparing results from different target sequences.

`test_ml_evaluation.py` covers metric and confusion counts, malicious positivity, zero-division cases, malformed targets, generic estimator reuse, no test fitting, stable JSON, comparison rules including a lower-F1 recall winner, false-alarm trade-offs, comparable populations and separate overfitting diagnostics. All **205 backend tests passed**, including 15 evaluation tests. The full official evaluation completed successfully. Saved model parameters match the Phase 4 report, each confusion matrix totals 82,332 records, and `git diff --check` passed.

Files created: `backend/ml/evaluation.py`, `backend/test_ml_evaluation.py`, `docs/phase5/evaluation.json`, and this report. `backend/README.md` was updated with usage. Preprocessing, Phase 2 rules, training configuration and frontend were not modified for this phase.

## Limitations and next phase

This is one official split with no confidence intervals or future-traffic validation. Selecting between models on this test set means it is no longer a fresh independent estimate for the selected winner. Do not retune against these outcomes. Unknown categories retain Phase 3's all-zero encoding policy. Timings depend on hardware and load. The selected forest still misses 444 attacks and produces 10,744 false alarms.

Next phase: package the selected Random Forest together with its fitted Phase 3 preprocessor, feature order, label mapping, configuration, source hashes and dependency versions. Add save/load round-trip prediction checks before developing the prediction API. Treat the package as a development candidate pending operational validation, rather than automatically deploying it. Resolve false-alarm costs using training-only validation or a new independent dataset; any later tuning requires a fresh evaluation protocol. Keep the frontend and prediction API work in their designated phase.
