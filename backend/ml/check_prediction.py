"""Functional inference check on saved artifacts, with no fitting or evaluation tuning."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from csv_loading import load_csv
from .artifacts import prediction_fingerprints
from .prediction import NetworkPredictionService


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.rows <= 82332:
        parser.error('Rows must be between 1 and 82332.')
    metadata = json.loads((root / 'backend/models/model_metadata.json').read_text(encoding='utf-8'))
    features = metadata['features']['required_features']
    service = NetworkPredictionService()
    test_path = root / 'data/UNSW_NB15_testing-set.csv'
    frame = load_csv(test_path.read_bytes()).iloc[:args.rows].loc[:, features].copy()
    # Saved classes are patched after the first lazy load; no training is invoked.
    model, preprocessor, _ = service._load()
    with patch.object(type(model), 'fit', side_effect=AssertionError('No training')), patch.object(type(preprocessor), 'fit', side_effect=AssertionError('No fitting')), patch.object(type(preprocessor), 'fit_transform', side_effect=AssertionError('No fitting')):
        result = service.predict(frame, limit=10)
        if result['model']['encoded_feature_count'] != 197:
            raise ValueError('Official artifact width differs.')
        training = load_csv((root / 'data/UNSW_NB15_training-set.csv').read_bytes()).iloc[:32].loc[:, features].copy()
        roundtrip = service.predict(training, limit=32)
        reference = json.loads((root / 'docs/phase6/reload_verification.json').read_text(encoding='utf-8'))
        records = roundtrip['records']
        predictions = np.array([r['prediction'] for r in records], dtype=model.classes_.dtype)
        probabilities = np.array([[r['probability_normal'], r['probability_malicious']] for r in records])
        fingerprints = prediction_fingerprints(preprocessor.transform(training), predictions, probabilities)
        if fingerprints != reference['fingerprints_before_save']:
            raise ValueError('Inference differs from Phase 6 fingerprints.')
    report = {'functional_input': 'First official testing rows, predictive columns only; functional validation, not tuning',
        'summary': result['summary'], 'model': result['model'], 'schema_audit': result['schema_audit'],
        'sample_predictions': result['records'], 'response_bytes': len(json.dumps(result).encode()),
        'no_fit_methods_called': True, 'phase6_fingerprints_match': True,
        'model_probability_note': result['probability_description']}
    output = root / 'docs/phase7/functional_validation.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report['summary']), flush=True)
    print('Phase 6 fingerprints match; no fitting; report: ' + str(output), flush=True)


if __name__ == '__main__':
    main()
