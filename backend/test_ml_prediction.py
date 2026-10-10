"""Small-fixture inference/API tests, without official training."""
import asyncio
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
import numpy as np
import pandas as pd
from scipy import sparse
import main
import test_backend as backend_tests
from ml.artifacts import save_artifacts
from ml.models import random_forest
from ml.prediction import NetworkPredictionService, PredictionError
from ml.training import training_matrix
from test_ml_training import prepared_fixture


class PredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.prepared = prepared_fixture()
        cls.model = random_forest().fit(training_matrix(cls.prepared.X_train), cls.prepared.y_train)
        save_artifacts(cls.temporary.name, cls.model, cls.prepared.preprocessor, 'random_forest', 60, {})

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.service = NetworkPredictionService(self.temporary.name, batch_size=2)
        self.frame = pd.DataFrame({'elapsed': ['1', '', '17', '12', '4'], 'wire': ['tcp', 'udp', 'tcp', 'udp', 'tcp']}, index=[99, 5, 5, -1, 400])

    def test_success_without_any_protected_fields(self):
        result = self.service.predict(self.frame)
        self.assertEqual(result['summary']['records_analysed'], 5)
        self.assertEqual(result['summary']['normal_count'] + result['summary']['malicious_count'], 5)
        self.assertEqual(result['model']['encoded_feature_count'], 4)
        self.assertEqual(result['schema_audit']['missing_values']['elapsed'], 1)
        json.dumps(result, allow_nan=False)

    def test_classes_labels_and_probabilities(self):
        result = self.service.predict(self.frame)
        for record in result['records']:
            self.assertIn(record['prediction'], [0, 1])
            self.assertEqual(record['label'], ['Normal', 'Malicious'][record['prediction']])
            for field in ['probability_normal', 'probability_malicious', 'predicted_class_probability']:
                self.assertTrue(0 <= record[field] <= 1)
            self.assertAlmostEqual(record['probability_normal'] + record['probability_malicious'], 1)
            self.assertEqual(record['predicted_class_probability'], record['probability_normal' if record['prediction'] == 0 else 'probability_malicious'])
        self.assertAlmostEqual(result['summary']['average_predicted_class_probability'], np.mean([r['predicted_class_probability'] for r in result['records']]))

    def test_order_and_input_unchanged(self):
        original = self.frame.copy(deep=True)
        result = self.service.predict(self.frame)
        self.assertEqual([r['record_index'] for r in result['records']], list(range(5)))
        pd.testing.assert_frame_equal(original, self.frame)

    def test_extra_and_protected_fields_ignored(self):
        expected = self.service.predict(self.frame)['records']
        result = self.service.predict(self.frame.assign(truth='not a label', flow_id=999, attack_type='ignored', extra='also ignored'))
        self.assertEqual(result['records'], expected)
        self.assertEqual(len(result['schema_audit']['ignored_columns']), 4)

    def test_missing_fields_listed(self):
        with self.assertRaises(PredictionError) as raised:
            self.service.predict(self.frame.drop(columns='wire'))
        self.assertEqual(raised.exception.code, 'missing_features')
        self.assertEqual(raised.exception.detail()['missing_fields'], ['wire'])

    def test_invalid_numeric_and_range(self):
        for value in ['not numeric', 'inf', '-1', '1e100']:
            frame = self.frame.copy()
            frame.loc[99, 'elapsed'] = value
            with self.subTest(value=value), self.assertRaises(PredictionError) as raised:
                self.service.predict(frame)
            self.assertIn(raised.exception.code, ['invalid_features', 'numeric_range'])

    def test_unseen_category_audited_without_learning(self):
        self.service.predict(self.frame)
        preprocessor = self.service._artifacts[1]
        categories = deepcopy(preprocessor.encoder_.categories_)
        medians = dict(preprocessor.medians_)
        result = self.service.predict(self.frame.assign(wire='sctp'))
        self.assertEqual(result['schema_audit']['unseen_categories']['wire'], 5)
        self.assertTrue(result['schema_audit']['warnings'])
        self.assertEqual(preprocessor.medians_, medians)
        for first, second in zip(categories, preprocessor.encoder_.categories_):
            np.testing.assert_array_equal(first, second)

    def test_no_fit_methods_called_and_load_once(self):
        from ml.artifacts import load_artifacts
        with patch('ml.prediction.load_artifacts', wraps=load_artifacts) as loader, patch.object(type(self.prepared.preprocessor), 'fit', side_effect=AssertionError('no fit')), patch.object(type(self.prepared.preprocessor), 'fit_transform', side_effect=AssertionError('no fit_transform')), patch.object(type(self.model), 'fit', side_effect=AssertionError('no training')):
            self.service.predict(self.frame)
            self.service.predict(self.frame)
            self.assertEqual(loader.call_count, 1)

    def test_missing_artifacts_safe(self):
        with TemporaryDirectory() as directory, self.assertLogs('ml.prediction', level='ERROR'):
            with self.assertRaises(PredictionError) as raised:
                NetworkPredictionService(directory).predict(self.frame)
        self.assertEqual(raised.exception.code, 'artifacts_missing')
        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn(directory, str(raised.exception))

    def test_invalid_metadata_safe(self):
        with patch('ml.prediction.load_artifacts', side_effect=ValueError('secret internal details')), self.assertLogs('ml.prediction', level='ERROR'):
            with self.assertRaises(PredictionError) as raised:
                self.service.predict(self.frame)
        self.assertEqual(raised.exception.code, 'artifacts_invalid')
        self.assertNotIn('secret', str(raised.exception))

    def test_prediction_failure_safe(self):
        self.service.predict(self.frame)
        with patch.object(self.service._artifacts[0], 'predict', side_effect=RuntimeError('secret path')), self.assertLogs('ml.prediction', level='ERROR'):
            with self.assertRaises(PredictionError) as raised:
                self.service.predict(self.frame)
        self.assertEqual(raised.exception.code, 'prediction_failed')
        self.assertNotIn('secret', str(raised.exception))

    def test_transform_failure_safe(self):
        self.service.predict(self.frame)
        with patch.object(self.service._artifacts[1], 'transform', side_effect=RuntimeError('secret path')), self.assertLogs('ml.prediction', level='ERROR'):
            with self.assertRaises(PredictionError) as raised:
                self.service.predict(self.frame)
        self.assertEqual(raised.exception.code, 'transformation_failed')

    def test_pagination_and_summary_only(self):
        result = self.service.predict(self.frame, offset=1, limit=2)
        self.assertEqual([r['record_index'] for r in result['records']], [1, 2])
        self.assertEqual(result['pagination']['next_offset'], 3)
        self.assertEqual(result['summary']['records_analysed'], 5)
        self.assertEqual(self.service.predict(self.frame, limit=0)['records'], [])
        self.assertEqual(self.service.predict(self.frame, offset=100)['records'], [])

    def test_invalid_input_and_pagination(self):
        for frame in [None, pd.DataFrame(), pd.DataFrame([[1, 2]], columns=['x', 'x'])]:
            with self.assertRaises(PredictionError):
                self.service.predict(frame)
        for options in [{'offset': -1}, {'limit': 1001}, {'limit': -1}, {'limit': True}]:
            with self.assertRaises(PredictionError):
                self.service.predict(self.frame, **options)

    def test_large_sparse_batches_and_bounded_response(self):
        self.service.batch_size = 1024
        frame = pd.concat([self.frame] * 2000, ignore_index=True)
        self.service.predict(self.frame)
        preprocessor = self.service._artifacts[1]
        original_transform = preprocessor.transform
        sizes = []
        def checked_transform(batch):
            sizes.append(len(batch))
            return original_transform(batch)
        with patch.object(preprocessor, 'transform', side_effect=checked_transform), patch.object(sparse.csr_matrix, 'toarray', side_effect=AssertionError('no dense conversion')):
            result = self.service.predict(frame, limit=1000)
        self.assertEqual(result['summary']['records_analysed'], 10000)
        self.assertEqual(len(result['records']), 1000)
        self.assertLessEqual(max(sizes), 1024)
        self.assertLess(len(json.dumps(result)), 400000)


class PredictionRouteTests(unittest.TestCase):
    def test_upload_success_closed_and_separate_from_quality(self):
        upload = UploadFile(filename='network.csv', file=io.BytesIO(b'a\n1\n'))
        with patch('ml.prediction.predict_network_traffic', return_value={'summary': {'records_analysed': 1}}) as predict, patch('main.run_pipeline_from_dataframe', side_effect=AssertionError('quality remains separate')):
            response = asyncio.run(main.predict_network_csv(upload, offset=4, limit=5))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(predict.call_args.kwargs, {'offset': 4, 'limit': 5})
        self.assertTrue(upload.file.closed)

    def test_csv_errors_and_filename(self):
        for filename, contents in [('wrong.txt', b'a\n1\n'), ('bad.csv', b'a,b\n1\n')]:
            upload = UploadFile(filename=filename, file=io.BytesIO(contents))
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.predict_network_csv(upload))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertTrue(upload.file.closed)

    def test_schema_error_status_and_fields(self):
        error = PredictionError('missing_features', 'Missing required features: dur', fields=['dur'])
        with patch('ml.prediction.predict_network_traffic', side_effect=error):
            with self.assertRaises(HTTPException) as raised:
                main._predict_contents(b'a\n1\n', 0, 100)
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail['missing_fields'], ['dur'])

    def test_unexpected_route_failure_safe(self):
        upload = UploadFile(filename='network.csv', file=io.BytesIO(b'a\n1\n'))
        with patch('main._predict_contents', side_effect=RuntimeError('secret')), self.assertLogs('main', level='ERROR'):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.predict_network_csv(upload))
        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn('secret', str(raised.exception.detail))
        self.assertTrue(upload.file.closed)

    def test_upload_size_limit(self):
        upload = UploadFile(filename='network.csv', file=io.BytesIO(b'a\n123456\n'))
        with patch('main.MAX_SIZE', 5):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.predict_network_csv(upload))
        self.assertEqual(raised.exception.status_code, 400)


class LivePredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        backend_tests.LiveAPITests.setUpClass.__func__(cls)

    @classmethod
    def cleanup(cls):
        backend_tests.LiveAPITests.cleanup.__func__(cls)

    request = backend_tests.LiveAPITests.request

    def upload(self, contents, query=''):
        body = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="network.csv"\r\nContent-Type: text/csv\r\n\r\n' + contents + b'\r\n--boundary--\r\n'
        return self.request('/predict-network' + query, body, {'Content-Type': 'multipart/form-data; boundary=boundary', 'Origin': 'http://localhost:5173'})

    def test_real_artifacts_sparse_inference_and_pagination(self):
        metadata = json.loads((Path(__file__).parent / 'models/model_metadata.json').read_text(encoding='utf-8'))
        features = metadata['features']
        row = {name: '0' for name in features['numeric_features']}
        row.update({name: next(value for value in features['learned_categories'][name] if value != '__dataqualiq_missing__') for name in features['categorical_features']})
        frame = pd.DataFrame([row] * 4).loc[:, features['required_features']]
        status, headers, result = self.upload(frame.to_csv(index=False).encode(), '?offset=1&limit=2')
        self.assertEqual(status, 200)
        self.assertEqual(result['model']['encoded_feature_count'], 197)
        self.assertEqual(result['summary']['records_analysed'], 4)
        self.assertEqual([r['record_index'] for r in result['records']], [1, 2])
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'http://localhost:5173')

    def test_http_query_validation_and_missing_fields(self):
        for query in ['?limit=1001', '?offset=-1', '?limit=notanumber']:
            self.assertEqual(self.upload(b'a\n1\n', query)[0], 422)
        status, _, result = self.upload(b'a\n1\n')
        self.assertEqual(status, 422)
        self.assertEqual(result['detail']['code'], 'missing_features')
        self.assertEqual(len(result['detail']['missing_fields']), 42)


if __name__ == '__main__':
    unittest.main()
