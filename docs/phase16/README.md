# Phase 16: clean versus degraded network data

## Predeclared design

Original official UNSW-NB15 testing CSV, all 82,332 rows, with Normal=0 and Malicious=1 (positive class). The same saved Random Forest and saved preprocessor are used throughout. Metrics are calculated against unchanged label values, not copied from the saved official evaluation.

Master seed: **16042**. Numeric missingness seed 16042; categorical missingness 16043; representation seed 16044. Each type uses a seeded permutation of original nonmissing predictor cells, with nested 5%, 10%, 20% prefixes. Percentages refer to eligible cells in that type's declared group, not percentage of rows or all dataset cells. Exact affected-cell, per-field and unique-row counts are saved for every condition. No target or attack category participates in selection.

- Numeric missingness: dur, rate, sbytes; selected cells set to missing.
- Categorical missingness: proto, service, state; selected cells set to missing.
- Safe representation inconsistency: outer whitespace on proto/service/state; uppercase proto only. Saved normalization trims these fields and lowercases case-insensitive proto. Case-sensitive state and service spelling are preserved. No unseen category is invented.
- Baseline plus nine individual-type conditions; optional combined degradation intentionally omitted to keep mechanisms interpretable.

The three representative numeric fields were fixed before inspecting degraded performance. The experiment does not claim that this subset covers all 39 numeric features. Legitimate extreme values and duplicate policies remain unchanged; no row is removed or capped.

## Execution and safeguards

`backend/experiments/data_quality_experiment.py` calls the existing CombinedAnalysisService, including the unchanged DataQualiQ pipeline and saved inference. An experiment-only observer captures the exact class predictions used by the service, with source-position assertions, rather than training or generating a second set of predictions. Fit/fit_transform are forbidden during every condition. Label, attack_cat and all nonpredictive columns are asserted unchanged. Encoded feature definitions must stay unchanged. Original CSV, metadata, model and preprocessor hashes are checked before and after.

No degraded CSV copies are saved. Generation is reproducible from original data, declared configuration and seed. JSON records selection hashes, missing/finding summaries, quality scores, reliability, metrics, confusion matrices, baseline deltas and timing. CSV provides a flat comparison table. Checkpoint JSON has complete=false until all ten conditions and final integrity checks finish.

## Reproduction

From backend, use the existing verified virtual environment:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
.\venv\Scripts\python.exe -B -m unittest test_data_quality_experiment -v
.\venv\Scripts\python.exe -B -m experiments.data_quality_experiment
```

Plots are generated separately by `experiments/plot_quality_experiment.py` using temporary Matplotlib dependencies, keeping production requirements unchanged. Plots read completed JSON only and save PNG/SVG artifacts.

## Interpretation cautions

DataQualiQ's score is threshold-based and can plateau even while more cells are missing. It is a heuristic quality measure, not prediction accuracy. Review counts describe input integrity, not calibrated probability. All truth rows must receive safe predictions; rejected/unpredicted rows cause this safe-degradation experiment to fail rather than being silently excluded from metric denominators.

This is one controlled test set with one random realization per type. Levels are nested and not independent replications. The official test split was previously used for model selection, so baseline performance is not a fresh independent estimate. No tuning uses experiment outcomes. Missingness is random among eligible cells; real collection failures may be systematic. Conclusions apply to these fields, degradation mechanisms, fixed model and dataset.

## Validation

Eight experiment tests passed in 11.531 seconds. They check nested reproducible sampling, label-blind selection, preservation of source/truth fields, safe representation rules, known confusion-matrix metrics, predictor-only degradation, inference without fitting, source/artifact hashes, and refusal to merge incomplete or inconsistent worker reports.

The full backend regression suite passed: **282 tests in 76.722 seconds**. Existing training tests use small temporary fixtures; the experiment never trains or changes the saved production model.

To reduce elapsed time, the measured baseline was shared with isolated categorical and representation processes. The baseline/numeric process was stopped after all numeric conditions were checkpointed, before repeating the other groups. `experiments/merge_quality_experiment.py` requires exactly one measured result for each type/level, identical configurations and baseline, completed categorical/representation reports, identical before/after file hashes and current files matching those hashes. It then produces the final complete JSON/CSV. The numeric checkpoint is preserved under workers/numeric. Per-condition execution times include concurrent CPU contention and should not be treated as a production benchmark.

## Full-data measured results

All ten conditions assessed and predicted all **82,332 rows**: 37,000 Normal and 45,332 Malicious. No rows were excluded, rejected or marked Low. Metrics below are percentages; Malicious is the positive class. Baseline quality is 100 (grade A).

| Condition | Quality | Accuracy | Precision | Recall | F1 | FP | FN | Review |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 100 | 86.4111 | 80.6874 | 99.0206 | 88.9188 | 10,744 | 444 | 5 |
| Numeric missing 5% | 55 | 86.1901 | 80.4166 | 99.0360 | 88.7604 | 10,933 | 437 | 11,767 |
| Numeric missing 10% | 32.5 | 85.9605 | 80.1270 | 99.0735 | 88.5987 | 11,139 | 420 | 22,284 |
| Numeric missing 20% | 32.5 | 85.5062 | 79.5750 | 99.1176 | 88.2777 | 11,533 | 400 | 40,094 |
| Categorical missing 5% | 47.5 | 86.1475 | 80.3380 | 99.0934 | 88.7355 | 10,994 | 411 | 11,745 |
| Categorical missing 10% | 32.5 | 85.8512 | 79.9644 | 99.1441 | 88.5273 | 11,261 | 388 | 22,374 |
| Categorical missing 20% | 32.5 | 85.2937 | 79.2722 | 99.2389 | 88.1389 | 11,763 | 345 | 40,167 |
| Safe representation 5% | 100 | 86.4111 | 80.6874 | 99.0206 | 88.9188 | 10,744 | 444 | 5 |
| Safe representation 10% | 100 | 86.4111 | 80.6874 | 99.0206 | 88.9188 | 10,744 | 444 | 5 |
| Safe representation 20% | 100 | 86.4111 | 80.6874 | 99.0206 | 88.9188 | 10,744 | 444 | 5 |

### Changes from baseline

Metric changes are **percentage points**, not relative percent changes. Negative FN changes mean fewer missed attacks.

| Condition | Accuracy change | Precision change | Recall change | F1 change | FP change | FN change |
|---|---:|---:|---:|---:|---:|---:|
| Numeric missing 5% | -0.2211 | -0.2707 | +0.0154 | -0.1584 | +189 | -7 |
| Numeric missing 10% | -0.4506 | -0.5603 | +0.0529 | -0.3201 | +395 | -24 |
| Numeric missing 20% | -0.9049 | -1.1124 | +0.0971 | -0.6412 | +789 | -44 |
| Categorical missing 5% | -0.2636 | -0.3494 | +0.0728 | -0.1834 | +250 | -33 |
| Categorical missing 10% | -0.5599 | -0.7230 | +0.1235 | -0.3915 | +517 | -56 |
| Categorical missing 20% | -1.1174 | -1.4151 | +0.2184 | -0.7799 | +1,019 | -99 |
| Safe representation 5% | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0 | +0 |
| Safe representation 10% | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0 | +0 |
| Safe representation 20% | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0 | +0 |

### Confusion matrices

Each matrix is [[TN, FP], [FN, TP]], with actual rows and predicted columns ordered [Normal, Malicious].

| Condition | Confusion matrix |
|---|---|
| Baseline | `[[26256, 10744], [444, 44888]]` |
| Numeric missing 5% | `[[26067, 10933], [437, 44895]]` |
| Numeric missing 10% | `[[25861, 11139], [420, 44912]]` |
| Numeric missing 20% | `[[25467, 11533], [400, 44932]]` |
| Categorical missing 5% | `[[26006, 10994], [411, 44921]]` |
| Categorical missing 10% | `[[25739, 11261], [388, 44944]]` |
| Categorical missing 20% | `[[25237, 11763], [345, 44987]]` |
| Safe representation 5% | `[[26256, 10744], [444, 44888]]` |
| Safe representation 10% | `[[26256, 10744], [444, 44888]]` |
| Safe representation 20% | `[[26256, 10744], [444, 44888]]` |

### Quality findings, sampling and execution time

Eligible cells: 246,996 per declared group. Exact per-column counts and selection hashes are retained in JSON. Statistical anomaly occurrences can overlap across fields; these are not attack counts and were not clipped. The original baseline has zero missing/duplicate/invalid/inconsistent findings, but 248,284 statistical-anomaly occurrences across 58,543 records. Its five Review records reflect unseen state categories already present in the original data.

| Condition | Affected cells | Affected rows | Missing occurrences | Duplicate occurrences | Invalid occurrences | Inconsistency occurrences | Statistical anomaly occurrences | High | Seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 0 | 0 | 0 | 0 | 0 | 0 | 248,284 | 82,327 | 190.6 |
| Numeric missing 5% | 12,349 | 11,763 | 12,349 | 0 | 0 | 0 | 247,162 | 70,565 | 182.6 |
| Numeric missing 10% | 24,699 | 22,280 | 24,699 | 0 | 0 | 0 | 246,102 | 60,048 | 209.3 |
| Numeric missing 20% | 49,399 | 40,090 | 49,399 | 0 | 0 | 0 | 243,952 | 42,238 | 238.0 |
| Categorical missing 5% | 12,349 | 11,740 | 12,349 | 0 | 0 | 0 | 248,284 | 70,587 | 218.9 |
| Categorical missing 10% | 24,699 | 22,369 | 24,699 | 0 | 0 | 0 | 248,284 | 59,958 | 231.0 |
| Categorical missing 20% | 49,399 | 40,164 | 49,399 | 0 | 0 | 0 | 248,284 | 42,165 | 191.7 |
| Safe representation 5% | 12,349 | 11,755 | 0 | 0 | 0 | 0 | 248,284 | 82,327 | 214.5 |
| Safe representation 10% | 24,699 | 22,299 | 0 | 0 | 0 | 0 | 248,284 | 82,327 | 228.0 |
| Safe representation 20% | 49,399 | 40,189 | 0 | 0 | 0 | 0 | 248,284 | 82,327 | 192.4 |

Summed measured condition times: **2097.0 seconds**. This is a sum across partly concurrent runs, not elapsed wall time. Every reliability total equals 82,332. Missingness raises Review counts; probability is not used as input reliability.

## Evidence-based answer

For this fixed model, dataset and sampling design, missing predictive values reduced accuracy, precision and F1 at every tested level. Categorical missingness had the largest reduction at each matched level. At 20%, accuracy dropped 1.1174 percentage points, precision dropped 1.4151 points and F1 dropped 0.7799 points; false positives increased by 1,019 (10,744 to 11,763). Numeric missingness at 20% dropped accuracy by 0.9049 points and F1 by 0.6412 points, with 789 additional false positives.

The experiment **does not show worse attack recall from these missingness mechanisms**. Numeric 20% improved recall by 0.0971 points and reduced false negatives by 44 (444 to 400). Categorical 20% improved recall by 0.2184 points and reduced false negatives by 99 (444 to 345). Lower precision and more false alarms indicate a different error tradeoff; increased recall alone does not mean degraded inputs are better overall.

Safe whitespace/case changes produced exactly the same prediction SHA-256 as baseline at every level, with unchanged metrics, quality score and reliability. This supports robustness of the existing normalization to the tested representations. It does not establish robustness to arbitrary corruption or unseen categories.

Data quality therefore affects intrusion-detection performance in this controlled experiment, but the relationship is mechanism-dependent. A lower heuristic quality score is not a calibrated forecast of accuracy or recall. Scores plateau at 32.5 for both missingness types at 10% and 20%, while model metrics continue changing. No production rules, preprocessing or thresholds were changed to manufacture a monotonic result.

## Outputs and integrity

- [Measured CSV](experiment_results.csv)
- [Complete JSON, findings, deltas, configuration and hashes](experiment_results.json)
- Plots: [quality score](plots/quality_score.png), [accuracy](plots/accuracy.png), [recall](plots/recall.png), [F1](plots/f1.png), [false negatives](plots/false_negatives.png). Each also has an editable SVG beside the PNG.

Original CSV, model, saved preprocessor and metadata have identical SHA-256 hashes before and after, rechecked during merging:

| File | Unchanged SHA-256 |
|---|---|
| UNSW_NB15_testing-set.csv | `734fe6642edf758f7c94d7d9149426b49d202fe8e7bf0bef47392489c3c0a559` |
| model_metadata.json | `fe31966d283da719bc856fa389dfdab951b748de9adce121b5b38350f3436f9a` |
| intrusion_model.joblib | `a6be0a645b2c01f497c406f8daf02bfc3c85e98662ff61b90068cd1f2343067d` |
| preprocessor.joblib | `414c4ca98cfb3799096512fca901ab02dca32c7517801a4b2721aca1d0a726c9` |

## Phase 17 recommendation

Repeat this fixed-model experiment using multiple independent degradation seeds on a genuinely held-out or temporally separate labelled network dataset. Include systematic missingness and a controlled combined condition, and report uncertainty intervals for paired accuracy/precision/recall/F1 and FP/FN changes. Keep model selection/tuning separate from that evaluation. This should test whether the observed false-alarm/recall tradeoff generalizes, rather than assuming that missingness must increase missed attacks.

Remaining limitations: one random realization per mechanism; nested levels are correlated; only dur/rate/sbytes represent numeric degradation; random missingness does not model all collection failures; no combined condition or confidence intervals; official test data were used in prior model selection; full quality assessment takes several minutes per condition. These results support a bounded experiment, not a universal causal claim or production security guarantee.
