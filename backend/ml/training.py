"""Train both candidates on Phase 3 training output; no evaluation or persistence."""
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
import json
import platform
import numpy as np
import sklearn
from scipy import sparse
from threadpoolctl import threadpool_limits

from .models import decision_tree, random_forest
from .prepare import prepare_official_split


@dataclass
class TrainingRun:
    decision_tree: object
    random_forest: object
    preprocessor: object
    summary: dict


def matrix_bytes(matrix):
    if sparse.issparse(matrix):
        return int(sum(getattr(matrix, key).nbytes for key in ['data', 'indices', 'indptr', 'row', 'col'] if hasattr(matrix, key)))
    return int(matrix.nbytes)


def training_matrix(X):
    """Create the CSC/float32 representation required by tree fitting, never dense.

    Dense arrays are accepted for small callers, but we do not densify sparse input.
    Reject range overflow rather than capping valid Phase 3 values.
    """
    if not sparse.issparse(X) and not isinstance(X, np.ndarray):
        raise ValueError('Training features must be a sparse matrix or numeric ndarray.')
    if len(X.shape) != 2 or not X.shape[0] or not X.shape[1]:
        raise ValueError('Training matrix must have nonzero rows and columns.')
    values = X.data if sparse.issparse(X) else X
    if values.dtype.kind not in 'biuf' or not np.isfinite(values).all():
        raise ValueError('Training features must contain finite numeric values.')
    if values.size and np.max(np.abs(values.astype(np.float64, copy=False))) > np.finfo(np.float32).max:
        raise ValueError('A feature exceeds the tree estimator float32 range; review representation without clipping.')
    if sparse.issparse(X):
        result = sparse.csc_matrix(X, dtype=np.float32, copy=True)
        result.sort_indices()
    else:
        result = np.array(X, dtype=np.float32, order='C', copy=True)
    return result


def train_models(X_train, y_train, preprocessor):
    """Return fitted estimators and metadata. There are no testing-data arguments."""
    if not getattr(preprocessor, 'fitted_', False):
        raise ValueError('An existing training-fitted Phase 3 preprocessor is required.')
    protected = preprocessor.schema.protected_fields
    if protected.intersection(preprocessor.feature_columns_):
        raise ValueError('Protected target/leakage/identifier columns cannot be predictors.')
    names = preprocessor.get_feature_names_out().tolist()
    if len(X_train.shape) != 2 or X_train.shape[1] != len(names):
        raise ValueError('Training feature width does not match the Phase 3 feature order.')
    y = np.asarray(y_train)
    if y.ndim != 1 or len(y) != X_train.shape[0]:
        raise ValueError('Training targets must be one-dimensional and aligned with rows.')
    if y.dtype.kind not in 'biuf' or not np.isfinite(y).all() or not np.isin(y, [0, 1]).all():
        raise ValueError('Training targets must contain only binary 0 and 1 values.')
    if set(np.unique(y).tolist()) != {0, 1}:
        raise ValueError('Both Normal and Malicious training classes are required.')
    y = y.astype(np.int8, copy=True)
    matrix = training_matrix(X_train)
    summaries = {}
    fitted = {}
    # Cap native numeric worker pools independently of RF's two tree workers.
    with threadpool_limits(limits=1):
        for name, factory in [('decision_tree', decision_tree), ('random_forest', random_forest)]:
            estimator = factory()
            print(f'Training {name}: {matrix.shape[0]:,} rows, {matrix.shape[1]} features', flush=True)
            start = perf_counter()
            estimator.fit(matrix, y)
            duration = perf_counter() - start
            summary = {'model_type': type(estimator).__name__, 'training_records': len(y),
                'encoded_feature_count': matrix.shape[1], 'parameters': estimator.get_params(deep=False),
                'random_state': estimator.random_state, 'training_seconds': round(duration, 4),
                'classes': estimator.classes_.tolist(), 'fit_source': 'X_train/y_train only'}
            if name == 'decision_tree':
                summary.update(tree_depth=int(estimator.get_depth()), leaves=int(estimator.get_n_leaves()))
            else:
                summary['number_of_trees'] = len(estimator.estimators_)
            summaries[name] = summary
            fitted[name] = estimator
            print(f'Completed {name} in {duration:.2f}s', flush=True)
    report = {
        'phase': 4, 'models': summaries, 'training_shape': list(matrix.shape),
        'feature_names': names, 'excluded_fields': sorted(protected),
        'class_distribution': {'normal': int((y == 0).sum()), 'malicious': int((y == 1).sum())},
        'class_weighting': None, 'resampling': False, 'parameter_tuning': False,
        'official_test_used_for_training': False, 'evaluation_performed': False,
        'selected_model': None, 'model_artifacts_saved': False,
        'resources': {'input_format': X_train.format if sparse.issparse(X_train) else 'dense ndarray',
            'input_dtype': str(X_train.dtype), 'input_matrix_bytes': matrix_bytes(X_train),
            'fit_format': matrix.format if sparse.issparse(matrix) else 'dense ndarray',
            'fit_dtype': str(matrix.dtype), 'fit_matrix_bytes': matrix_bytes(matrix),
            'dense_float64_equivalent_bytes': int(matrix.shape[0] * matrix.shape[1] * 8),
            'sparse_input_densified': False, 'forest_workers': 2, 'native_thread_limit': 1},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'sklearn': sklearn.__version__},
    }
    return TrainingRun(fitted['decision_tree'], fitted['random_forest'], preprocessor, report)


def train_prepared_split(prepared):
    # Never even access X_test/y_test here. Their presence is for Phase 5 only.
    return train_models(prepared.X_train, prepared.y_train, prepared.preprocessor)


def run_official_training(training_path, testing_path):
    prepared = prepare_official_split(training_path, testing_path)
    run = train_prepared_split(prepared)
    run.summary['preparation'] = {
        'official_split_preserved': prepared.audit['official_split_preserved'],
        'sources': [{key: item[key] for key in ['dataset', 'source_path', 'source_sha256', 'source_unchanged', 'original_rows', 'final_rows']}
                    for item in prepared.audit['datasets']],
        'preprocessing_fit_source': 'training_only',
        'test_data_transformed_only_by_phase3': True,
    }
    return run


def main():
    import argparse
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training', type=Path, default=root / 'data/UNSW_NB15_training-set.csv')
    parser.add_argument('--testing', type=Path, default=root / 'data/UNSW_NB15_testing-set.csv')
    parser.add_argument('--summary', type=Path, default=root / 'docs/phase4/training.json')
    args = parser.parse_args()
    run = run_official_training(args.training, args.testing)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(run.summary, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Training summary: {args.summary}', flush=True)
    print('Both estimators trained; no test evaluation, selection or model saving performed.', flush=True)


if __name__ == '__main__':
    main()
