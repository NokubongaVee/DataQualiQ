"""Saved-artifact inference only. No quality assessment, fitting or training."""
from copy import deepcopy
import logging
from pathlib import Path
from threading import Lock
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from threadpoolctl import threadpool_limits

from .artifacts import load_artifacts

logger = logging.getLogger(__name__)
MAX_RECORD_RESULTS = 1000
DEFAULT_BATCH_SIZE = 4096


class PredictionError(Exception):
    def __init__(self, code, message, status_code=422, fields=None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.fields = fields

    def detail(self):
        detail = {'code': self.code, 'message': str(self)}
        if self.fields is not None:
            detail['missing_fields'] = self.fields
        return detail


class NetworkPredictionService:
    def __init__(self, artifact_directory=None, batch_size=DEFAULT_BATCH_SIZE):
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or not 1 <= batch_size <= DEFAULT_BATCH_SIZE:
            raise ValueError('Batch size must be between 1 and 4096.')
        self.artifact_directory = Path(artifact_directory) if artifact_directory is not None else Path(__file__).resolve().parents[1] / 'models'
        self.batch_size = batch_size
        self._artifacts = None
        # The saved preprocessor updates last_audit_ during transform. Serialize
        # requests so each summary receives only its own audit; also bound memory.
        self._lock = Lock()

    def _load(self):
        if self._artifacts is None:
            try:
                model, preprocessor, metadata = load_artifacts(self.artifact_directory)
                if metadata['selected_model'] != 'random_forest' or metadata['algorithm'] != 'RandomForestClassifier':
                    raise ValueError('Expected the Phase 6 selected Random Forest.')
                self._artifacts = model, preprocessor, metadata
            except FileNotFoundError as exc:
                logger.exception('Prediction artifact missing')
                raise PredictionError('artifacts_missing', 'Prediction artifacts are unavailable. Restore the saved model, preprocessor and metadata.', 503) from exc
            except Exception as exc:
                logger.exception('Prediction artifacts could not be loaded')
                raise PredictionError('artifacts_invalid', 'Prediction artifacts are invalid or incompatible with this backend environment.', 503) from exc
        return self._artifacts

    def predict(self, dataframe, *, offset=0, limit=100):
        if not isinstance(dataframe, pd.DataFrame):
            raise PredictionError('invalid_input', 'Network traffic must be supplied as a DataFrame.')
        if dataframe.empty:
            raise PredictionError('empty_input', 'No network records are available for prediction.')
        if not dataframe.columns.is_unique:
            raise PredictionError('duplicate_columns', 'Network feature names must be unique.')
        if (not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or
                not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= MAX_RECORD_RESULTS):
            raise PredictionError('invalid_pagination', 'Offset must be nonnegative; limit must be between 0 and 1000.')
        start = perf_counter()
        with self._lock:
            model, preprocessor, metadata = self._load()
            features = metadata['features']
            missing = [name for name in features['required_features'] if name not in dataframe.columns]
            if missing:
                raise PredictionError('missing_features', 'Missing required network features: ' + ', '.join(missing), fields=missing)
            ignored = [str(name) for name in dataframe.columns if name not in features['required_features']]
            normal = malicious = 0
            probability_sum = 0.0
            records = []
            unseen = {name: 0 for name in features['categorical_features']}
            missing_values = {name: 0 for name in features['required_features']}
            for batch_start in range(0, len(dataframe), self.batch_size):
                batch = dataframe.iloc[batch_start:batch_start + self.batch_size].loc[:, features['required_features']]
                try:
                    matrix = preprocessor.transform(batch)
                    audit = deepcopy(preprocessor.last_audit_)
                except ValueError as exc:
                    raise PredictionError('invalid_features', str(exc)) from exc
                except Exception as exc:
                    logger.exception('Prediction transformation failed')
                    raise PredictionError('transformation_failed', 'Could not transform network features with the saved preprocessing.', 500) from exc
                if not sparse.issparse(matrix) or matrix.shape != (len(batch), metadata['encoded_feature_count']):
                    raise PredictionError('feature_mismatch', 'Saved preprocessing output is incompatible with the model.', 503)
                if not np.isfinite(matrix.data).all() or (matrix.data.size and np.max(np.abs(matrix.data)) > np.finfo(np.float32).max):
                    raise PredictionError('numeric_range', 'Network features exceed the finite numeric range supported by the saved model.')
                matrix = matrix.astype(np.float32).tocsr()
                try:
                    # Deterministic tree accumulation; saved parameters unchanged.
                    with threadpool_limits(limits=1), joblib.parallel_backend('sequential'):
                        predictions = np.asarray(model.predict(matrix))
                        probabilities = np.asarray(model.predict_proba(matrix))
                    if (predictions.shape != (len(batch),) or not np.isin(predictions, [0, 1]).all() or
                            probabilities.shape != (len(batch), 2) or not np.isfinite(probabilities).all() or
                            (probabilities < 0).any() or (probabilities > 1).any() or
                            not np.allclose(probabilities.sum(axis=1), 1, atol=1e-10, rtol=0)):
                        raise ValueError('Invalid classifier output')
                except Exception as exc:
                    logger.exception('Saved model prediction failed')
                    raise PredictionError('prediction_failed', 'Could not generate predictions with the saved model.', 500) from exc
                predicted_probabilities = probabilities[np.arange(len(batch)), predictions.astype(int)]
                normal += int((predictions == 0).sum())
                malicious += int((predictions == 1).sum())
                probability_sum += float(predicted_probabilities.sum())
                for name, count in audit['unseen_categories'].items():
                    unseen[name] += count
                for name, count in audit['missing_detected'].items():
                    missing_values[name] += count
                first = max(offset, batch_start)
                last = min(offset + limit, batch_start + len(batch))
                for position in range(first, last):
                    local = position - batch_start
                    prediction = int(predictions[local])
                    records.append({'record_index': position, 'prediction': prediction,
                        'label': metadata['target_meaning'][str(prediction)],
                        'probability_normal': float(probabilities[local, 0]),
                        'probability_malicious': float(probabilities[local, 1]),
                        'predicted_class_probability': float(predicted_probabilities[local])})
            warnings = []
            if any(unseen.values()):
                warnings.append('Unseen categorical values were encoded with the saved all-zero category behaviour; no new categories were learned.')
            if ignored:
                warnings.append('Non-predictive columns were ignored.')
            return {
                'summary': {'records_analysed': len(dataframe), 'normal_count': normal, 'malicious_count': malicious,
                    'average_predicted_class_probability': probability_sum / len(dataframe),
                    'processing_seconds': perf_counter() - start},
                'records': records,
                'pagination': {'offset': offset, 'limit': limit, 'returned_records': len(records),
                    'total_records': len(dataframe), 'next_offset': offset + len(records) if limit and offset + len(records) < len(dataframe) else None},
                'model': {'selected_model': metadata['selected_model'], 'artifact_version': metadata['artifact_version'],
                    'encoded_feature_count': metadata['encoded_feature_count'], 'target_meaning': dict(metadata['target_meaning'])},
                'schema_audit': {'ignored_columns': ignored, 'unseen_categories': unseen, 'missing_values': missing_values, 'warnings': warnings},
                'probability_description': 'Model probability estimate; not necessarily calibrated or a guarantee.',
                'record_index_description': 'Zero-based position in the original supplied DataFrame/CSV data rows; header excluded.',
            }


service = NetworkPredictionService()


def predict_network_traffic(dataframe, *, offset=0, limit=100):
    return service.predict(dataframe, offset=offset, limit=limit)
