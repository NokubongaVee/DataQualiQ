"""Fresh-process Phase 6 reload check; no fitting or training calls."""
import json
import joblib
from pathlib import Path
from unittest.mock import patch

from csv_loading import load_csv
from .artifacts import load_artifacts, prediction_fingerprints


def main():
    root = Path(__file__).resolve().parents[2]
    verification_path = root / 'docs/phase6/reload_verification.json'
    verification = json.loads(verification_path.read_text(encoding='utf-8'))
    model, preprocessor, metadata = load_artifacts(root / 'backend/models')
    frame = load_csv((root / 'data/UNSW_NB15_training-set.csv').read_bytes())
    sample = frame.loc[:, metadata['features']['required_features']].iloc[:verification['rows']].copy()
    del frame
    with patch.object(type(preprocessor), 'fit', side_effect=AssertionError('No refitting allowed')), patch.object(type(model), 'fit', side_effect=AssertionError('No retraining allowed')):
        matrix = preprocessor.transform(sample)
        with joblib.parallel_backend('sequential'):
            fingerprints = prediction_fingerprints(matrix, model.predict(matrix), model.predict_proba(matrix))
    if fingerprints != verification['fingerprints_before_save']:
        raise ValueError('Fresh-process reload differs from pre-save outputs.')
    verification['fresh_process_reload_identical'] = True
    verification['fresh_process_fit_calls_forbidden'] = True
    verification_path.write_text(json.dumps(verification, indent=2), encoding='utf-8')
    print('Fresh-process transform, prediction and probability fingerprints match; no fitting.', flush=True)


if __name__ == '__main__':
    main()
