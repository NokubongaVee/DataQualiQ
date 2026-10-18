"""Official split preparation. Return matrices in memory; write only a compact audit."""
from copy import deepcopy
from dataclasses import dataclass, asdict
import gc
import hashlib
import json
from pathlib import Path

from csv_loading import load_csv
from pipeline import run_pipeline_from_dataframe
from .configs import unsw_nb15_ml_config
from .preprocessing import prepare_supervised_dataset


@dataclass
class PreparedSplit:
    X_train: object
    y_train: object
    X_test: object
    y_test: object
    preprocessor: object
    audit: dict


def compact_quality(result):
    # Assessment remains unchanged and read-only. Keep counts rather than
    # duplicating potentially millions of evidence positions in this audit.
    return {key: result[key] for key in ['filename', 'total_rows', 'total_columns', 'score', 'grade', 'finding_summary', 'issue_summary']}


def prepare_official_split(training_path, testing_path):
    schema, policy, preprocessor = unsw_nb15_ml_config()
    paths = [Path(training_path), Path(testing_path)]
    if paths[0].resolve() == paths[1].resolve():
        raise ValueError('Training and testing must be distinct official files.')
    datasets = []
    matrices = []
    labels = []
    digests = []
    for dataset, path in zip(['training', 'testing'], paths):
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        digests.append(digest)
        frame = load_csv(raw)
        del raw
        print(f'Phase 2 assessment: {dataset} ({len(frame):,} rows)', flush=True)
        quality = compact_quality(run_pipeline_from_dataframe(frame, path.name, network_schema=schema))
        gc.collect()
        print(f'Preparing {dataset} features using {"training fit" if dataset == "training" else "existing training state"}', flush=True)
        cleaned, y, audit = prepare_supervised_dataset(frame, schema, 'label', policy, dataset)
        if not len(cleaned):
            raise ValueError(f'No usable target records remain in {dataset}.')
        X = preprocessor.fit_transform(cleaned) if dataset == 'training' else preprocessor.transform(cleaned)
        audit.update(quality_assessment=quality, ml_preprocessing=deepcopy(preprocessor.last_audit_),
                     source_path=str(path), source_sha256=digest, source_unchanged=True)
        # Preserve counts and actual operations, omit huge unchanged-row lists.
        audit['retained_source_row_count'] = len(audit.pop('retained_source_rows'))
        datasets.append(audit)
        matrices.append(X)
        labels.append(y)
        del frame, cleaned
        gc.collect()
    for path, digest in zip(paths, digests):
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Source CSV changed during preprocessing: {path}')
    audit = {
        'phase': 3, 'model_training_performed': False, 'official_split_preserved': True,
        'datasets': datasets, 'schema': schema.to_dict(),
        'numeric_features': preprocessor.numeric_features_,
        'categorical_features': preprocessor.categorical_features_,
        'excluded_features': sorted(schema.protected_fields),
        'categorical_normalization_policy': {name: asdict(plan) for name, plan in policy.fields.items()},
        'duplicate_policy_reason': 'Detect only: identical network rows can be legitimate observations; no exporter provenance justifies removal.',
        'predictive_feature_count': len(preprocessor.feature_columns_),
        'encoded_feature_count': len(preprocessor.feature_names_out_),
        'feature_names_out': preprocessor.feature_names_out_,
        'training_medians': preprocessor.medians_,
        'training_category_sets': {name: categories.tolist() for name, categories in zip(preprocessor.categorical_features_, preprocessor.encoder_.categories_)},
        'matrix_shapes': {'X_train': list(matrices[0].shape), 'y_train': list(labels[0].shape),
                          'X_test': list(matrices[1].shape), 'y_test': list(labels[1].shape)},
        'matrix_format': 'scipy CSR, float64; numeric first then categorical one-hot blocks',
        'leakage_protections': ['Official files never combined or randomly split.',
            'Target, leakage and identifiers excluded before fitting.',
            'Medians and category sets fitted on usable training records only.',
            'Testing/future transform reuses the fitted imputer and encoder without fitting.',
            'No scaling, outlier removal, balancing or oversampling.'],
        'limitations': ['Unseen categories encode to all-zero blocks and are counted in the audit.',
            'Invalid numeric/schema values require review and are rejected rather than silently imputed.',
            'All-missing numeric training features require an explicit policy; no invented median.',
            'Feature matrices are produced in memory; no model or fitted object is saved.'],
    }
    return PreparedSplit(matrices[0], labels[0], matrices[1], labels[1], preprocessor, audit)


def main():
    import argparse
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training', type=Path, default=root / 'data/UNSW_NB15_training-set.csv')
    parser.add_argument('--testing', type=Path, default=root / 'data/UNSW_NB15_testing-set.csv')
    parser.add_argument('--audit', type=Path, default=root / 'artifacts/dataset_preparation.json')
    args = parser.parse_args()
    prepared = prepare_official_split(args.training, args.testing)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(prepared.audit, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(prepared.audit['matrix_shapes']), flush=True)
    print(f'Audit: {args.audit}', flush=True)


if __name__ == '__main__':
    main()
