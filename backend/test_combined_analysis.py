"""Row linking and integrity policy regression tests on small fixtures."""
import asyncio
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from fastapi import UploadFile, HTTPException
import main
import test_backend as backend_tests
from finding_categories import ERROR, QUALITY, ANALYTICAL
from ml.artifacts import save_artifacts
from ml.models import random_forest
from ml.prediction import NetworkPredictionService, PredictionError
from ml.combined_analysis import CombinedAnalysisService
from ml.training import training_matrix
from test_ml_training import prepared_fixture


def quality_fixture(issues):
    return {'issues': issues, 'score': 100, 'grade': 'A', 'finding_summary': {}, 'issue_summary': {}, 'score_policy': {}}


def finding(check, category, rows, column='elapsed'):
    return {'check': check, 'category': category, 'row_indices': rows, 'column': column, 'count': len(rows), 'id': check}


class CombinedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        prepared = prepared_fixture()
        cls.preprocessor = prepared.preprocessor
        cls.model = random_forest().fit(training_matrix(prepared.X_train), prepared.y_train)
        save_artifacts(cls.temp.name, cls.model, cls.preprocessor, 'random_forest', 60, {})

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.predictor = NetworkPredictionService(self.temp.name, batch_size=2)
        self.service = CombinedAnalysisService(self.predictor)
        self.frame = pd.DataFrame({'elapsed': ['1', '2', '17', '14', '4'], 'wire': ['tcp', 'udp', 'tcp', 'udp', 'tcp']}, index=[99, 8, 8, -4, 100])

    def controlled(self, issues, frame=None, **options):
        with patch('ml.combined_analysis.run_pipeline_from_dataframe', return_value=quality_fixture(issues)):
            return self.service.analyze(self.frame if frame is None else frame, **options)

    def test_clean_high_and_input_unchanged(self):
        original = self.frame.copy(deep=True)
        result = self.controlled([])
        self.assertEqual(result['summary']['high_count'], 5)
        self.assertEqual([r['record_index'] for r in result['records']], list(range(5)))
        pd.testing.assert_frame_equal(original, self.frame)

    def test_exact_row_link_with_duplicate_indexes(self):
        result = self.controlled([finding('format', QUALITY, [3])])
        self.assertEqual([r['reliability'] for r in result['records']], ['High', 'High', 'High', 'Review', 'High'])
        self.assertEqual(result['records'][3]['quality_findings'][0]['check'], 'format')
        self.assertEqual(result['records'][2]['quality_findings'], [])

    def test_missing_numeric_and_category_review(self):
        frame = self.frame.copy()
        frame.iloc[1, 0] = ''
        frame.iloc[3, 1] = ''
        result = self.controlled([], frame)
        self.assertEqual(result['summary']['review_count'], 2)
        for index in [1, 3]:
            record = result['records'][index]
            self.assertIsNotNone(record['prediction'])
            self.assertTrue(record['preprocessing_handled_missing'])
            self.assertIn('Missing', record['reliability_reason'])

    def test_real_invalid_row_rejected_without_displacing_neighbors(self):
        frame = self.frame.copy()
        frame.iloc[1, 0] = '-1'
        result = self.service.analyze(frame)
        self.assertEqual(result['summary']['rejected_count'], 1)
        record = result['records'][1]
        self.assertEqual(record['reliability'], 'Low')
        self.assertEqual(record['prediction_status'], 'Rejected')
        self.assertIsNone(record['prediction'])
        self.assertIsNone(record['probability_malicious'])
        self.assertTrue(record['quality_findings'])
        expected = self.predictor.predict(frame.iloc[[0, 2, 3, 4]])['records']
        for position, prediction in zip([0, 2, 3, 4], expected):
            self.assertEqual(result['records'][position]['prediction'], prediction['prediction'])

    def test_outlier_alone_not_penalized(self):
        result = self.controlled([finding('outlier', ANALYTICAL, [1, 4])])
        self.assertEqual(result['summary']['high_count'], 5)
        self.assertEqual(result['records'][1]['quality_findings'][0]['category'], ANALYTICAL)

    def test_duplicate_default_and_configured_review(self):
        issues = [finding('duplicate', QUALITY, [2], None)]
        self.assertEqual(self.controlled(issues)['records'][2]['reliability'], 'High')
        self.service.duplicate_review = True
        result = self.controlled(issues)
        self.assertEqual(result['records'][2]['reliability'], 'Review')
        self.assertEqual(result['summary']['low_count'], 0)

    def test_probability_and_score_do_not_select_reliability(self):
        clean = self.controlled([])
        flagged = self.controlled([finding('format', QUALITY, [0])])
        self.assertEqual(flagged['summary']['data_quality_score'], 100)
        self.assertEqual(flagged['records'][0]['reliability'], 'Review')
        self.assertEqual(clean['records'][0]['predicted_class_probability'], flagged['records'][0]['predicted_class_probability'])

    def test_full_file_class_reliability_counts_without_page(self):
        issues = [finding('format', QUALITY, [2, 3])]
        complete = self.controlled(issues)
        summary_only = self.controlled(issues, limit=0)
        for reliability in ['High', 'Review']:
            selected = [r for r in complete['records'] if r['reliability'] == reliability]
            for prediction, field in [(0, 'normal_count'), (1, 'malicious_count')]:
                expected = sum(r['prediction'] == prediction for r in selected)
                self.assertEqual(summary_only['prediction_by_reliability'][reliability][field], expected)

    def test_nonpredictive_errors_do_not_penalize_input(self):
        result = self.controlled([finding('invalid_numeric', ERROR, [2], 'truth')])
        self.assertEqual(result['records'][2]['reliability'], 'High')
        self.assertTrue(result['records'][2]['quality_findings'])

    def test_unseen_category_review_without_refit(self):
        result = self.controlled([], self.frame.assign(wire='sctp'))
        self.assertEqual(result['summary']['review_count'], 5)
        self.assertEqual(result['schema_audit']['unseen_categories']['wire'], 5)
        self.assertIn('Unseen wire', result['records'][0]['reliability_reason'])

    def test_pagination_original_positions_with_rejection(self):
        frame = self.frame.copy()
        frame.iloc[2, 0] = '1e100'
        result = self.controlled([], frame, offset=1, limit=3)
        self.assertEqual([r['record_index'] for r in result['records']], [1, 2, 3])
        self.assertIsNone(result['records'][1]['prediction'])
        self.assertEqual(result['summary']['records_predicted'], 4)
        self.assertEqual(result['pagination']['next_offset'], 4)
        self.assertEqual(self.controlled([], offset=999)['records'], [])
        self.assertEqual(self.controlled([], limit=0)['records'], [])

    def test_all_rejected_null_average_and_summary_counts(self):
        frame = self.frame.assign(elapsed='1e100')
        result = self.controlled([], frame)
        self.assertEqual(result['summary']['records_predicted'], 0)
        self.assertEqual(result['summary']['low_count'], 5)
        self.assertIsNone(result['summary']['average_predicted_class_probability'])
        json.dumps(result, allow_nan=False)

    def test_rejected_row_does_not_claim_missing_was_imputed(self):
        frame = self.frame.copy()
        frame.iloc[0, 0] = '1e100'
        frame.iloc[0, 1] = ''
        result = self.controlled([], frame)
        self.assertEqual(result['records'][0]['missing_predictive_fields'], ['wire'])
        self.assertEqual(result['records'][0]['preprocessing_handled_missing'], [])

    def test_missing_structural_columns_rejected(self):
        with self.assertRaises(PredictionError) as raised:
            self.service.analyze(self.frame.drop(columns='wire'))
        self.assertEqual(raised.exception.fields, ['wire'])

    def test_large_response_and_evidence_bounded(self):
        frame = pd.concat([self.frame] * 2000, ignore_index=True)
        self.predictor.batch_size = 1024
        issues = [finding('outlier', ANALYTICAL, list(range(len(frame)))) for _ in range(25)]
        result = self.controlled(issues, frame, limit=1000)
        self.assertEqual(result['summary']['records_analysed'], 10000)
        self.assertEqual(len(result['records']), 1000)
        self.assertLessEqual(sum(len(r['quality_findings']) for r in result['records']), 1000)
        self.assertTrue(any(r['quality_findings_truncated'] for r in result['records']))
        self.assertTrue(all(r['quality_finding_categories'] == [ANALYTICAL] for r in result['records']))
        self.assertLess(len(json.dumps(result)), 1500000)

    def test_no_fitting_and_real_quality(self):
        with patch.object(type(self.preprocessor), 'fit', side_effect=AssertionError('no fit')), patch.object(type(self.preprocessor), 'fit_transform', side_effect=AssertionError('no fit_transform')), patch.object(type(self.model), 'fit', side_effect=AssertionError('no training')):
            result = self.service.analyze(self.frame)
        self.assertEqual(result['summary']['records_predicted'], 5)
        self.assertEqual(sum(result['summary'][key] for key in ['high_count', 'review_count', 'low_count']), 5)

    def test_invalid_evidence_mapping_fails(self):
        with self.assertRaises(PredictionError):
            self.controlled([finding('missing', QUALITY, [999])])


class CombinedRouteTests(unittest.TestCase):
    def test_upload_and_closed(self):
        upload = UploadFile(filename='network.csv', file=io.BytesIO(b'a\n1\n'))
        with patch('ml.combined_analysis.analyze_network', return_value={'summary': {'records_analysed': 1}}) as analyze, patch('ml.analysis_response.format_combined_api_response', side_effect=lambda result: result):
            response = asyncio.run(main.analyze_network_csv(upload, offset=3, limit=4))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(analyze.call_args.kwargs, {'offset': 3, 'limit': 4})
        self.assertTrue(upload.file.closed)

    def test_bad_upload(self):
        upload = UploadFile(filename='network.csv', file=io.BytesIO(b'a,b\n1\n'))
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main.analyze_network_csv(upload))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertTrue(upload.file.closed)


class LiveCombinedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        backend_tests.LiveAPITests.setUpClass.__func__(cls)

    @classmethod
    def cleanup(cls):
        backend_tests.LiveAPITests.cleanup.__func__(cls)

    request = backend_tests.LiveAPITests.request

    def test_combined_http_real_saved_bundle(self):
        metadata = json.loads((Path(__file__).parent / 'models/model_metadata.json').read_text())
        features = metadata['features']
        row = {name: '0' for name in features['numeric_features']}
        row.update({name: next(v for v in features['learned_categories'][name] if v != '__dataqualiq_missing__') for name in features['categorical_features']})
        frame = pd.DataFrame([row] * 4)
        frame.loc[1, 'dur'] = '-1'
        contents = frame.to_csv(index=False).encode()
        body = b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="network.csv"\r\nContent-Type: text/csv\r\n\r\n' + contents + b'\r\n--boundary--\r\n'
        status, _, result = self.request('/analyze-network?offset=1&limit=2', body, {'Content-Type': 'multipart/form-data; boundary=boundary'})
        self.assertEqual(status, 200)
        self.assertEqual(result['intrusion_summary']['rejected_count'], 1)
        self.assertEqual([r['record_index'] for r in result['records']], [1, 2])
        self.assertIsNone(result['records'][0]['prediction'])


if __name__ == '__main__':
    unittest.main()
