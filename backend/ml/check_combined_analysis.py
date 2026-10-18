"""Functional combined analysis on an unchanged official sample; no fitting."""
import json
from pathlib import Path
from unittest.mock import patch
from csv_loading import load_csv
from .prediction import NetworkPredictionService
from .combined_analysis import CombinedAnalysisService


def main():
    root = Path(__file__).resolve().parents[2]
    metadata = json.loads((root / 'backend/models/model_metadata.json').read_text(encoding='utf-8'))
    path = root / 'data/UNSW_NB15_testing-set.csv'
    frame = load_csv(path.read_bytes()).iloc[:1000].loc[:, metadata['features']['required_features']].copy()
    predictor = NetworkPredictionService()
    with predictor._lock:
        model, preprocessor, _ = predictor._load()
    with patch.object(type(model), 'fit', side_effect=AssertionError('No retraining')), patch.object(type(preprocessor), 'fit', side_effect=AssertionError('No refitting')), patch.object(type(preprocessor), 'fit_transform', side_effect=AssertionError('No refitting')):
        result = CombinedAnalysisService(predictor).analyze(frame, 'UNSW_NB15_testing-set.csv (first 1000 predictive rows)', limit=10)
    report = {'functional_input': 'First 1000 official testing rows; predictive projection only; values unchanged',
        'summary': result['summary'], 'quality_summary': result['quality_summary'],
        'schema_audit': result['schema_audit'], 'policy': result['reliability_policy'],
        'sample_records': result['records'], 'response_bytes': len(json.dumps(result).encode()),
        'no_fit_methods_called': True}
    output = root / 'artifacts/combined_analysis_validation.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report['summary']), flush=True)
    print(json.dumps(report['schema_audit']['warnings']), flush=True)
    print('Report: ' + str(output), flush=True)


if __name__ == '__main__':
    main()
