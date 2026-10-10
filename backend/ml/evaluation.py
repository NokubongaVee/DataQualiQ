"""Binary classifier evaluation and an explicit cybersecurity comparison policy."""
from pathlib import Path
from time import perf_counter
import hashlib
import json
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report
from sklearn.utils.validation import check_is_fitted
from threadpoolctl import threadpool_limits
from scipy import sparse

from .prepare import prepare_official_split
from .training import train_prepared_split

SIMILARITY_TOLERANCE = 0.005


def binary_labels(values, name):
    result = np.asarray(values)
    if result.ndim != 1 or not len(result) or result.dtype.kind not in 'biuf' or not np.isfinite(result).all() or not np.isin(result, [0, 1]).all():
        raise ValueError(f'{name} must be a nonempty binary vector containing only 0 and 1.')
    return result.astype(np.int8, copy=True)


def evaluate_predictions(y_true, y_pred):
    """Stable, JSON-compatible metrics; rows=actual, columns=predicted, order=0,1."""
    truth, prediction = binary_labels(y_true, 'Targets'), binary_labels(y_pred, 'Predictions')
    if len(truth) != len(prediction):
        raise ValueError('Targets and predictions must have the same number of rows.')
    matrix = confusion_matrix(truth, prediction, labels=[0, 1])
    tn, fp, fn, tp = (int(value) for value in matrix.ravel())
    precision = float(precision_score(truth, prediction, pos_label=1, zero_division=0))
    recall = float(recall_score(truth, prediction, pos_label=1, zero_division=0))
    return {
        'records': len(truth), 'positive_class': 1, 'class_names': {'0': 'Normal', '1': 'Malicious'},
        'target_digest': hashlib.sha256(truth.tobytes()).hexdigest(),
        'metrics': {'accuracy': float(accuracy_score(truth, prediction)), 'precision': precision,
                    'recall': recall, 'f1': float(f1_score(truth, prediction, pos_label=1, zero_division=0)),
                    'f2': 5 * precision * recall / (4 * precision + recall) if precision + recall else 0.0},
        'confusion_matrix': matrix.tolist(), 'confusion_matrix_labels': [0, 1],
        'counts': {'true_negatives': tn, 'false_positives': fp, 'false_negatives': fn, 'true_positives': tp},
        'classification_report': classification_report(truth, prediction, labels=[0, 1],
            target_names=['Normal', 'Malicious'], zero_division=0, output_dict=True),
    }


def evaluate_classifier(estimator, X, y):
    """Evaluate any fitted compatible binary estimator, never fit or alter thresholds."""
    check_is_fitted(estimator)
    truth = binary_labels(y, 'Targets')
    if len(X.shape) != 2 or X.shape[0] != len(truth):
        raise ValueError('Feature rows and targets must be aligned.')
    if hasattr(estimator, 'n_features_in_') and X.shape[1] != estimator.n_features_in_:
        raise ValueError('Evaluation feature width differs from the fitted estimator.')
    if hasattr(estimator, 'classes_') and set(np.asarray(estimator.classes_).tolist()) != {0, 1}:
        raise ValueError('Estimator classes must be 0=Normal and 1=Malicious.')
    with threadpool_limits(limits=1):
        start = perf_counter()
        predicted = estimator.predict(X)
        duration = perf_counter() - start
    result = evaluate_predictions(truth, predicted)
    result.update(model_type=type(estimator).__name__, prediction_seconds=float(duration),
                  decision_rule='Estimator.predict; unchanged default class decision rule')
    return result


def compare_models(results, complexity=None):
    """Fixed before evaluation: recall-weighted F2, with a near-equivalence rule.

    F2 weights recall four times precision in its harmonic mean. This is an
    explicit selection heuristic, not a business-cost estimate or test tuning.
    """
    if len(results) < 2:
        raise ValueError('Comparison requires at least two evaluated models.')
    population = {(item['records'], item['target_digest']) for item in results.values()}
    if len(population) != 1:
        raise ValueError('Models must be evaluated on the same target population/order.')
    complexity = complexity or {}
    keys = ['accuracy', 'precision', 'recall', 'f1']
    similar = all(max(item['metrics'][key] for item in results.values()) - min(item['metrics'][key] for item in results.values()) <= SIMILARITY_TOLERANCE for key in keys)
    ranked = sorted(results, key=lambda name: (-results[name]['metrics']['f2'],
        -results[name]['metrics']['f1'], -results[name]['metrics']['recall'],
        -results[name]['metrics']['precision'], -results[name]['metrics']['accuracy'],
        complexity.get(name, float('inf')), name))
    selected = min(ranked, key=lambda name: (complexity.get(name, float('inf')), ranked.index(name))) if similar else ranked[0]
    winner = results[selected]
    reason = ('Required metrics are within 0.5 percentage points; prefer lower practical complexity.' if similar
              else 'Highest recall-weighted F2, with F1, recall, precision and accuracy as tie-breakers. F2 accounts for missed attacks and false alarms; accuracy alone is not the selection criterion.')
    return {'selected_model': selected, 'reason': reason,
        'policy': {'primary': 'malicious F2 (recall-weighted harmonic mean)', 'tie_breakers': ['F1', 'Recall', 'Precision', 'Accuracy', 'complexity'],
                   'similarity_tolerance': SIMILARITY_TOLERANCE, 'fixed_before_test_evaluation': True},
        'selected_counts': winner['counts'], 'selected_metrics': winner['metrics'],
        'observed_tradeoffs': {name: {
            'false_negatives_change': winner['counts']['false_negatives'] - item['counts']['false_negatives'],
            'false_positives_change': winner['counts']['false_positives'] - item['counts']['false_positives'],
            'metric_changes': {key: winner['metrics'][key] - item['metrics'][key] for key in keys},
        } for name, item in results.items() if name != selected},
        'comparison_table': [{'model': name, **item['metrics'], **item['counts']} for name, item in results.items()]}


def overfitting_diagnostic(training, testing):
    accuracy_gap = training['metrics']['accuracy'] - testing['metrics']['accuracy']
    f1_gap = training['metrics']['f1'] - testing['metrics']['f1']
    flagged = accuracy_gap >= 0.05 or f1_gap >= 0.05
    return {'training_accuracy': training['metrics']['accuracy'], 'test_accuracy': testing['metrics']['accuracy'],
        'training_f1': training['metrics']['f1'], 'test_f1': testing['metrics']['f1'],
        'accuracy_gap': accuracy_gap, 'f1_gap': f1_gap, 'possible_overfitting_or_distribution_shift': flagged,
        'diagnostic_gap_threshold': 0.05,
        'interpretation': 'A substantial resubstitution/test gap can indicate overfitting or distribution shift; it does not prove the cause. Training scores do not select the winner.'}


def evaluate_prepared_split(prepared, trained):
    """No fitting here. Both candidates receive the exact same reserved matrix."""
    if trained.preprocessor is not prepared.preprocessor:
        raise ValueError('Evaluation must use the same training-fitted Phase 3 preprocessor.')
    expected = prepared.preprocessor.get_feature_names_out().tolist()
    if trained.summary['feature_names'] != expected:
        raise ValueError('Training and evaluation feature order differ.')
    if not sparse.issparse(prepared.X_test):
        raise ValueError('The official workflow expects the Phase 3 sparse test matrix.')
    # Shared sparse float32 prediction representation; no preprocessing refit.
    if not np.isfinite(prepared.X_test.data).all() or (prepared.X_test.data.size and np.max(np.abs(prepared.X_test.data)) > np.finfo(np.float32).max):
        raise ValueError('Test features exceed the estimator finite float32 representation.')
    X_test = prepared.X_test.astype(np.float32).tocsr()
    results, diagnostics = {}, {}
    for name, estimator in [('decision_tree', trained.decision_tree), ('random_forest', trained.random_forest)]:
        print(f'Evaluating {name} on {X_test.shape[0]:,} reserved testing rows', flush=True)
        results[name] = evaluate_classifier(estimator, X_test, prepared.y_test)
        training = evaluate_classifier(estimator, prepared.X_train, prepared.y_train)
        diagnostics[name] = overfitting_diagnostic(training, results[name])
    selection = compare_models(results, {'decision_tree': 1, 'random_forest': 100})
    return {
        'phase': 5, 'models': results, 'selection': selection, 'overfitting_diagnostics': diagnostics,
        'training_summary': trained.summary, 'preparation': prepared.audit,
        'test_shape': list(prepared.X_test.shape), 'training_shape': list(prepared.X_train.shape),
        'official_test_used_for_fit': False, 'hyperparameters_changed': False,
        'thresholds_changed': False, 'model_artifacts_saved': False,
        'limitations': ['One official test split; no confidence intervals or future-traffic validation.',
            'F2 selection is a declared cybersecurity heuristic, not a measured business-cost function.',
            'Training/test score gaps cannot distinguish overfitting from distribution shift.',
            'Unknown categories retain the unchanged Phase 3 all-zero encoding policy.',
            'Prediction timings are single-run measurements and depend on hardware/load.',
            'Selecting on this test set is model selection, not a fresh independent estimate for the selected winner. Do not retune against it.'],
    }


def run_official_evaluation(training_path, testing_path):
    prepared = prepare_official_split(training_path, testing_path)
    trained = train_prepared_split(prepared)
    return evaluate_prepared_split(prepared, trained)


def main():
    import argparse
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training', type=Path, default=root / 'data/UNSW_NB15_training-set.csv')
    parser.add_argument('--testing', type=Path, default=root / 'data/UNSW_NB15_testing-set.csv')
    parser.add_argument('--output', type=Path, default=root / 'docs/phase5/evaluation.json')
    args = parser.parse_args()
    report = run_official_evaluation(args.training, args.testing)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print('Selected model: ' + report['selection']['selected_model'], flush=True)
    print('Evaluation report: ' + str(args.output), flush=True)


if __name__ == '__main__':
    main()
