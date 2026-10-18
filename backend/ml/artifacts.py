"""Phase 6 persistence. Load only trusted, locally produced joblib artifacts."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from time import perf_counter

import joblib
import numpy as np
import sklearn
from threadpoolctl import threadpool_limits
from sklearn.utils.validation import check_is_fitted

from csv_loading import load_csv
from .configs import unsw_nb15_ml_config
from .models import decision_tree, random_forest
from .preprocessing import prepare_supervised_dataset
from .training import training_matrix

VERSION = 1
FILES = {'model': 'intrusion_model.joblib', 'preprocessor': 'preprocessor.joblib'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def feature_information(preprocessor):
    information = {
        'required_features': list(preprocessor.feature_columns_),
        'numeric_features': list(preprocessor.numeric_features_),
        'categorical_features': list(preprocessor.categorical_features_),
        'excluded_fields': sorted(preprocessor.schema.protected_fields),
        'schema': preprocessor.schema.to_dict(),
        'encoded_feature_order': preprocessor.get_feature_names_out().tolist(),
        'training_medians': preprocessor.medians_,
        'learned_categories': {name: values.tolist() for name, values in zip(
            preprocessor.categorical_features_, preprocessor.encoder_.categories_)} if preprocessor.encoder_ is not None else {},
        'normalization_policy': asdict(preprocessor.normalization_policy),
    }
    # Canonical JSON containers: schema/policy tuples become lists on disk.
    return json.loads(json.dumps(information, allow_nan=False))


def save_artifacts(directory, model, preprocessor, selected_model, training_rows, evaluation, provenance=None):
    check_is_fitted(model)
    features = feature_information(preprocessor)
    if set(features['required_features']) & set(features['excluded_fields']):
        raise ValueError('Protected fields cannot be predictors.')
    if model.n_features_in_ != len(features['encoded_feature_order']):
        raise ValueError('Model and preprocessor feature counts differ.')
    if not np.array_equal(model.classes_, [0, 1]):
        raise ValueError('Model must use Normal=0 and Malicious=1.')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    # Metadata is the completion marker. Never leave an old marker for partial writes.
    metadata_path = directory / 'model_metadata.json'
    metadata_path.unlink(missing_ok=True)
    for key, value in [('model', model), ('preprocessor', preprocessor)]:
        temporary = directory / (FILES[key] + '.tmp')
        joblib.dump(value, temporary, compress=3)
        temporary.replace(directory / FILES[key])
    metadata = {
        'artifact_version': VERSION, 'selected_model': selected_model,
        'algorithm': type(model).__name__, 'parameters': model.get_params(deep=False),
        'random_state': model.random_state, 'training_rows': int(training_rows),
        'original_feature_count': len(features['required_features']),
        'encoded_feature_count': int(model.n_features_in_),
        'target_meaning': {'0': 'Normal', '1': 'Malicious'},
        'features': features,
        'preprocessing_method': 'Phase 3 training-only median imputation and categorical one-hot encoding; fixed Phase 2 normalization; no scaling or outlier removal',
        'phase5_evaluation': evaluation, 'provenance': provenance or {},
        'environment': {'python': platform.python_version(), 'sklearn': sklearn.__version__, 'numpy': np.__version__, 'joblib': joblib.__version__},
        'created_at': datetime.now(timezone.utc).isoformat(),
        'files': {key: {'filename': filename, 'sha256': digest(directory / filename)} for key, filename in FILES.items()},
        'official_test_used_for_fit': False,
    }
    temporary = directory / 'model_metadata.json.tmp'
    temporary.write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(metadata_path)
    return metadata


def load_artifacts(directory):
    """Validate the bundle before deserializing trusted local artifacts.

    Hashes detect accidental mismatches, not malicious replacements. Never load
    joblib files supplied by uploads or untrusted users.
    """
    directory = Path(directory)
    metadata = json.loads((directory / 'model_metadata.json').read_text(encoding='utf-8'))
    if metadata.get('artifact_version') != VERSION:
        raise ValueError('Unsupported model artifact version.')
    if metadata.get('environment', {}).get('sklearn') != sklearn.__version__:
        raise ValueError('Artifact scikit-learn version differs from this environment.')
    features = metadata.get('features', {})
    if any(key not in features or not features[key] for key in ['required_features', 'encoded_feature_order', 'schema']):
        raise ValueError('Expected feature information is missing.')
    if metadata.get('target_meaning') != {'0': 'Normal', '1': 'Malicious'}:
        raise ValueError('Unexpected target mapping.')
    for key, filename in FILES.items():
        entry = metadata.get('files', {}).get(key, {})
        if entry.get('filename') != filename:
            raise ValueError('Unexpected artifact filename.')
        if digest(directory / filename) != entry.get('sha256'):
            raise ValueError(f'{key} artifact checksum mismatch.')
    model = joblib.load(directory / FILES['model'])
    preprocessor = joblib.load(directory / FILES['preprocessor'])
    check_is_fitted(model)
    if feature_information(preprocessor) != features:
        raise ValueError('Saved preprocessing and expected feature information differ.')
    if (model.n_features_in_ != metadata['encoded_feature_count'] or
            len(features['encoded_feature_order']) != model.n_features_in_ or
            model.get_params(deep=False) != metadata['parameters'] or
            type(model).__name__ != metadata['algorithm'] or
            not np.array_equal(model.classes_, [0, 1])):
        raise ValueError('Model and metadata are incompatible.')
    return model, preprocessor, metadata


def verify_reload(directory, model, preprocessor, sample):
    before = preprocessor.transform(sample)
    # Parallel forest accumulation can vary at machine precision. A sequential
    # joblib backend gives exact verification without changing saved parameters.
    with joblib.parallel_backend('sequential'):
        predictions = model.predict(before)
        probabilities = model.predict_proba(before)
    loaded_model, loaded_preprocessor, metadata = load_artifacts(directory)
    after = loaded_preprocessor.transform(sample)
    if before.shape != after.shape or (before != after).nnz:
        raise ValueError('Reload changed preprocessing output.')
    with joblib.parallel_backend('sequential'):
        np.testing.assert_array_equal(predictions, loaded_model.predict(after))
        np.testing.assert_array_equal(probabilities, loaded_model.predict_proba(after))
    return {'rows': len(sample), 'encoded_features': before.shape[1],
            'transform_identical': True, 'predictions_identical': True,
            'probabilities_identical': True, 'feature_information_identical': True,
            'target_required': False,
            'verification_prediction_backend': 'sequential for deterministic floating-point accumulation; saved n_jobs unchanged',
            'fingerprints_before_save': prediction_fingerprints(before, predictions, probabilities)}


def prediction_fingerprints(matrix, predictions, probabilities):
    matrix = matrix.tocsr(copy=True)
    matrix.sort_indices()
    return {key: hashlib.sha256(values.tobytes()).hexdigest() for key, values in {
        'matrix_data': matrix.data, 'matrix_indices': matrix.indices,
        'matrix_indptr': matrix.indptr, 'predictions': predictions,
        'probabilities': probabilities}.items()}


def persist_selected(training_path, evaluation_path, directory):
    report = json.loads(Path(evaluation_path).read_text(encoding='utf-8'))
    winner = report['selection']['selected_model']
    factories = {'decision_tree': decision_tree, 'random_forest': random_forest}
    if winner not in factories:
        raise ValueError('Unknown Phase 5 selected model.')
    model = factories[winner]()
    if model.get_params(deep=False) != report['training_summary']['models'][winner]['parameters']:
        raise ValueError('Current model parameters differ from Phase 5.')
    source_hash = digest(training_path)
    training_audit = next(item for item in report['preparation']['datasets'] if item['dataset'] == 'training')
    if source_hash != training_audit['source_sha256']:
        raise ValueError('Official training file differs from Phase 5.')
    frame = load_csv(Path(training_path).read_bytes())
    schema, policy, preprocessor = unsw_nb15_ml_config()
    cleaned, y, audit = prepare_supervised_dataset(frame, schema, 'label', policy)
    X = preprocessor.fit_transform(cleaned)
    if (preprocessor.get_feature_names_out().tolist() != report['training_summary']['feature_names'] or
            len(y) != report['training_summary']['models'][winner]['training_records']):
        raise ValueError('Prepared training population or features differ from Phase 5.')
    print(f'Training unchanged selected {winner}: {len(y):,} rows, {X.shape[1]} features', flush=True)
    start = perf_counter()
    with threadpool_limits(limits=1):
        model.fit(training_matrix(X), np.asarray(y, dtype=np.int8))
    if digest(training_path) != source_hash:
        raise ValueError('Training source changed during persistence.')
    sample = cleaned.loc[:, preprocessor.feature_columns_].iloc[:32].copy()
    provenance = {'training_source_sha256': source_hash, 'phase5_report_sha256': digest(evaluation_path),
                  'fit_source': 'official training only', 'training_seconds': perf_counter() - start,
                  'phase5_metrics_source': 'prior unchanged candidate evaluation; no Phase 6 test fitting or retuning'}
    save_artifacts(directory, model, preprocessor, winner, len(y), report['models'][winner], provenance)
    verification = verify_reload(directory, model, preprocessor, sample)
    return verification


def main():
    import argparse
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training', type=Path, default=root / 'data/UNSW_NB15_training-set.csv')
    parser.add_argument('--evaluation', type=Path, default=root / 'backend/models/selection_reference.json')
    parser.add_argument('--output', type=Path, default=root / 'backend/models')
    args = parser.parse_args()
    verification = persist_selected(args.training, args.evaluation, args.output)
    report_path = root / 'artifacts/model_reload_verification.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(verification, indent=2), encoding='utf-8')
    print(json.dumps(verification), flush=True)


if __name__ == '__main__':
    main()
