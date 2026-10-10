"""Controlled, label-blind test degradation using unchanged saved inference."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from csv_loading import load_csv
from ml.prediction import NetworkPredictionService
from ml.preprocessing import NetworkMLPreprocessor
from ml.combined_analysis import CombinedAnalysisService
from value_utils import missing_mask

SEED = 16042
LEVELS = (0.05, 0.10, 0.20)
GROUPS = {'numeric_missing': ('dur', 'rate', 'sbytes'), 'categorical_missing': ('proto', 'service', 'state'), 'representation': ('proto', 'service', 'state')}
SEED_OFFSETS = {'numeric_missing': 0, 'categorical_missing': 1, 'representation': 2}

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def degrade(original, kind, level, *, seed=SEED, predictive_features=None):
    """Cell sampling uses predictor columns alone; nested levels share a permutation."""
    if kind not in GROUPS or not 0 <= level <= 1:
        raise ValueError('Unknown degradation type or invalid fraction')
    names = list(GROUPS[kind])
    if not set(names).issubset(predictive_features or names) or not set(names).issubset(original.columns):
        raise ValueError('Degradation fields must be present saved predictive features')
    inputs = original.loc[:, names]
    eligible = np.column_stack([~missing_mask(inputs[name]).to_numpy(dtype=bool) for name in names])
    cells = np.flatnonzero(eligible.ravel())
    permutation = np.random.default_rng(seed + SEED_OFFSETS[kind]).permutation(cells)
    selected = permutation[:int(np.floor(len(cells) * level))]
    rows, columns = np.divmod(selected, len(names))
    result = original.copy(deep=True)
    per_column = {}
    for index, name in enumerate(names):
        positions = rows[columns == index]
        per_column[name] = len(positions)
        if kind == 'representation':
            values = result.iloc[positions][name].astype(str).str.strip()
            if name == 'proto': values = values.str.upper()
            result.iloc[positions, result.columns.get_loc(name)] = '  ' + values + '  '
        else:
            result.iloc[positions, result.columns.get_loc(name)] = ''
    audit = {'kind': kind, 'level': level, 'seed': seed + SEED_OFFSETS[kind], 'eligible_values': len(cells), 'affected_values': len(selected), 'affected_rows': len(np.unique(rows)), 'affected_by_column': per_column, 'selection_sha256': hashlib.sha256(selected.astype('<i8').tobytes()).hexdigest(), 'denominator': 'original nonmissing predictive cells in the declared feature group; not percent of rows', 'selected_rows_use_labels': False}
    return result, audit

def metrics(truth, predictions):
    truth = np.asarray(truth)
    predictions = np.asarray(predictions)
    if truth.shape != predictions.shape or not np.isin(truth, [0, 1]).all() or not np.isin(predictions, [0, 1]).all():
        raise ValueError('Exactly aligned Normal=0/Malicious=1 vectors required')
    matrix = confusion_matrix(truth, predictions, labels=[0, 1]).tolist()
    return {'accuracy': float(accuracy_score(truth, predictions)), 'precision': float(precision_score(truth, predictions, pos_label=1, zero_division=0)), 'recall': float(recall_score(truth, predictions, pos_label=1, zero_division=0)), 'f1': float(f1_score(truth, predictions, pos_label=1, zero_division=0)), 'confusion_matrix': matrix, 'false_positives': matrix[0][1], 'false_negatives': matrix[1][0]}

class CapturingPredictor(NetworkPredictionService):
    """Observer only: captures the exact predictions used by unchanged service."""
    def predict(self, dataframe, **options):
        if len(dataframe) > self.batch_size:
            raise AssertionError('Capture assumes CombinedAnalysisService bounded batches')
        self.positions = dataframe.index.to_numpy(dtype=np.int64)
        return super().predict(dataframe, **options)

    def evaluate(self, frame, filename):
        self.predictions = np.full(len(frame), -1, dtype=np.int8)
        self.positions = None
        with self._lock:
            model, _, _ = self._load()
        original_predict = type(model).predict
        def capture(estimator, matrix, *args, **kwargs):
            output = original_predict(estimator, matrix, *args, **kwargs)
            if estimator is model:
                if self.positions is None or len(output) != len(self.positions): raise AssertionError('Prediction/source-position mapping mismatch')
                self.predictions[self.positions] = output
            return output
        with patch.object(type(model), 'predict', capture), patch.object(RandomForestClassifier, 'fit', side_effect=AssertionError('No model training')), patch.object(NetworkMLPreprocessor, 'fit', side_effect=AssertionError('No preprocessing fitting')), patch.object(NetworkMLPreprocessor, 'fit_transform', side_effect=AssertionError('No preprocessing refit')):
            result = CombinedAnalysisService(self).analyze(frame, filename, limit=0)
        if (self.predictions < 0).any() or result['summary']['rejected_count']:
            raise AssertionError('This safe-degradation experiment requires all source rows to be predicted')
        return result, self.predictions.copy()

def experiment(dataset, artifacts, output, only_kind=None, baseline_file=None):
    start = perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    metadata_path = artifacts / 'model_metadata.json'
    metadata = json.loads(metadata_path.read_text())
    paths = [dataset, metadata_path] + [artifacts / info['filename'] for info in metadata['files'].values()]
    before = {str(path): digest(path) for path in paths}
    frame = load_csv(dataset.read_bytes()).reset_index(drop=True)
    truth = pd.to_numeric(frame['label'], errors='raise').to_numpy(dtype=np.int8)
    if not np.isin(truth, [0, 1]).all(): raise ValueError('Invalid official test labels')
    predictor = CapturingPredictor(artifacts)
    _, preprocessor, _ = predictor._load()
    feature_state = preprocessor.get_feature_names_out().tolist()
    conditions = [('baseline', 0.0)] + [(kind, level) for kind in GROUPS for level in LEVELS]
    report = {'configuration': {'seed': SEED, 'seed_offsets': SEED_OFFSETS, 'levels': LEVELS, 'feature_groups': GROUPS, 'sampling': 'nested prefixes of independent seeded eligible-cell permutations', 'representation_rules': 'outer whitespace on proto/service/state; uppercase only case-insensitive proto; state/service case preserved', 'numeric_rule': 'selected dur/rate/sbytes cells set to missing; no numeric clipping or outlier removal', 'categorical_rule': 'selected proto/service/state cells set to missing; no invented categories', 'positive_class': 1, 'class_labels': {'0': 'Normal', '1': 'Malicious'}, 'dataset_rows': len(frame), 'dataset_sha256': before[str(dataset)], 'artifact_version': metadata['artifact_version'], 'metadata_sha256': before[str(metadata_path)], 'artifact_checksums': {info['filename']: info['sha256'] for info in metadata['files'].values()}, 'encoded_feature_count': metadata['encoded_feature_count'], 'fitting_forbidden': True, 'official_test_was_used_for_prior_model_selection': True}, 'conditions': []}
    if only_kind is not None:
        if only_kind not in GROUPS or baseline_file is None: raise ValueError('A type-specific worker requires a measured baseline')
        baseline_report = json.loads(baseline_file.read_text())
        if baseline_report['configuration'] != json.loads(json.dumps(report['configuration'])): raise ValueError('Worker/baseline configurations differ')
        report['conditions'] = [baseline_report['conditions'][0]]
        conditions = [(only_kind, level) for level in LEVELS]
    for kind, level in conditions:
        print(f'Starting {kind} {level:.0%}: {len(frame)} rows', flush=True)
        condition_start = perf_counter()
        if kind == 'baseline': degraded, audit = frame.copy(deep=True), {'kind': 'baseline', 'level': 0, 'affected_values': 0, 'affected_rows': 0}
        else: degraded, audit = degrade(frame, kind, level, predictive_features=metadata['features']['required_features'])
        for column in ['label', 'attack_cat']:
            if column in frame: pd.testing.assert_series_equal(frame[column], degraded[column])
        protected = [name for name in frame if name not in metadata['features']['required_features']]
        pd.testing.assert_frame_equal(frame[protected], degraded[protected])
        combined, predictions = predictor.evaluate(degraded, dataset.name)
        measured = metrics(truth, predictions)
        if preprocessor.get_feature_names_out().tolist() != feature_state: raise AssertionError('Encoded feature definitions changed')
        quality = combined['quality_overview']
        item = {'condition': kind, 'degradation_percent': level * 100, 'degradation': audit, 'quality_score': quality['score'], 'grade': quality['grade'], **measured, 'high_count': combined['summary']['high_count'], 'review_count': combined['summary']['review_count'], 'low_count': combined['summary']['low_count'], 'rejected_count': combined['summary']['rejected_count'], 'quality_findings': {key: quality[key] for key in ['missing_values', 'duplicates', 'invalid_values', 'inconsistencies', 'analytical_anomalies']}, 'schema_audit': combined['schema_audit'], 'seconds': perf_counter() - condition_start, 'predictions_sha256': hashlib.sha256(predictions.tobytes()).hexdigest()}
        baseline = report['conditions'][0] if report['conditions'] else item
        item['changes_from_baseline'] = {key: item[key] - baseline[key] for key in ['accuracy', 'precision', 'recall', 'f1', 'false_positives', 'false_negatives', 'quality_score']}
        report['conditions'].append(item)
        report['complete'] = False
        (output / 'experiment_results.json').write_text(json.dumps(report, indent=2, allow_nan=False))
        print(json.dumps({key: item[key] for key in ['condition', 'degradation_percent', 'quality_score', 'accuracy', 'precision', 'recall', 'f1', 'false_negatives', 'review_count', 'seconds']}), flush=True)
    after = {str(path): digest(path) for path in paths}
    if before != after: raise AssertionError('Original dataset or production artifacts changed')
    report.update(complete=True, files_unchanged=True, file_checksums_before=before, file_checksums_after=after, total_seconds=perf_counter() - start)
    (output / 'experiment_results.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    fields = ['condition', 'degradation_percent', 'quality_score', 'grade', 'accuracy', 'precision', 'recall', 'f1', 'false_positives', 'false_negatives', 'high_count', 'review_count', 'low_count', 'rejected_count', 'recall_change_pp', 'false_negative_change', 'affected_values', 'affected_rows', 'seconds']
    with (output / 'experiment_results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for item in report['conditions']:
            row = {name: item[name] for name in fields if name in item}
            row.update(recall_change_pp=100 * item['changes_from_baseline']['recall'], false_negative_change=item['changes_from_baseline']['false_negatives'], affected_values=item['degradation']['affected_values'], affected_rows=item['degradation']['affected_rows'])
            writer.writerow(row)
    print(f'Complete: {report["total_seconds"]:.1f} seconds; all source/artifact hashes unchanged', flush=True)
    return report

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=root / 'data/UNSW_NB15_testing-set.csv')
    parser.add_argument('--artifacts', type=Path, default=root / 'backend/models')
    parser.add_argument('--output', type=Path, default=root / 'docs/phase16')
    parser.add_argument('--only-kind', choices=list(GROUPS))
    parser.add_argument('--baseline-results', type=Path)
    args = parser.parse_args()
    experiment(args.dataset, args.artifacts, args.output, args.only_kind, args.baseline_results)
