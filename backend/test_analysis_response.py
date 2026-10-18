"""Phase 9 contract tests; metrics are read from saved evaluation, never uploads."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import pandas as pd
import main
import test_combined_analysis as combined_fixtures
from finding_categories import ANALYTICAL, ERROR, QUALITY
from ml.analysis_response import format_combined_api_response
from ml.combined_analysis import quality_overview
from ml.prediction import PredictionError


def fixture_result():
    metadata = json.loads((Path(__file__).parent / 'models/model_metadata.json').read_text())
    empty_quality = combined_fixtures.quality_fixture([])
    return {'filename': 'fixture.csv',
        'summary': {'records_analysed': 10, 'records_predicted': 9, 'rejected_count': 1,
            'normal_count': 5, 'malicious_count': 4, 'average_predicted_class_probability': .7,
            'processing_seconds': .01, 'data_quality_score': 85, 'grade': 'B', 'high_count': 6, 'review_count': 3, 'low_count': 1},
        'quality_overview': quality_overview(empty_quality, 10),
        'quality_summary': {'unlinked_findings': 0},
        'schema_audit': {'warnings': [], 'unseen_categories': {}, 'missing_values': {}},
        'prediction_by_reliability': {'High': {'normal_count': 3, 'malicious_count': 3}, 'Review': {'normal_count': 2, 'malicious_count': 1}},
        'model': {'selected_model': metadata['selected_model'], 'artifact_version': 1, 'dataset_schema': 'UNSW-NB15'},
        'saved_evaluation': metadata['phase5_evaluation'],
        'reliability_policy': {'version': 'input_integrity_v1'},
        'probability_description': 'Model probability estimate, not calibrated certainty.',
        'records': [{'record_index': 0, 'prediction': 1, 'label': 'Malicious', 'prediction_status': 'Predicted', 'reliability_reason': 'Clean input'},
                    {'record_index': 1, 'prediction': None, 'label': None, 'prediction_status': 'Rejected', 'reliability_reason': 'Invalid dur'}],
        'pagination': {'offset': 0, 'limit': 2, 'returned_records': 2, 'total_records': 10, 'next_offset': 2}}


class ResponseTests(unittest.TestCase):
    def setUp(self):
        self.raw = fixture_result()

    def test_seven_sections(self):
        result = format_combined_api_response(self.raw)
        self.assertEqual(set(result), {'filename', 'data_quality', 'intrusion_summary', 'model_performance', 'reliability_summary', 'records', 'pagination', 'recommendations'})
        json.dumps(result, allow_nan=False)

    def test_official_metrics_exact_and_explicit(self):
        result = format_combined_api_response(self.raw)['model_performance']
        for key in ['accuracy', 'precision', 'recall', 'f1']:
            self.assertEqual(result[key], self.raw['saved_evaluation']['metrics'][key])
        self.assertEqual(result['confusion_matrix'], [[26256, 10744], [444, 44888]])
        self.assertEqual(result['records_evaluated'], 82332)
        self.assertEqual(result['source'], 'official_test_evaluation')
        self.assertFalse(result['is_current_upload_metric'])

    def test_unlabeled_and_labeled_uploads_do_not_replace_metrics(self):
        for contents in [b'dur\n1\n', b'dur,label\n1,0\n', b'dur,label\n1,1\n']:
            with patch('ml.combined_analysis.analyze_network', return_value=self.raw):
                result = main._analyze_contents(contents, 'input.csv', 0, 2)
            self.assertEqual(result['model_performance']['accuracy'], self.raw['saved_evaluation']['metrics']['accuracy'])

    def test_quality_summary_occurrences_vs_distinct_rows(self):
        issues = [combined_fixtures.finding('missing', QUALITY, [0, 1], 'dur'),
            combined_fixtures.finding('missing', QUALITY, [1, 2], 'rate'), combined_fixtures.finding('duplicate', QUALITY, [3], None),
            combined_fixtures.finding('network_invalid_count', ERROR, [2], 'spkts'), combined_fixtures.finding('format', QUALITY, [4], 'proto'),
            combined_fixtures.finding('outlier', ANALYTICAL, [0, 2], 'rate'), combined_fixtures.finding('outlier', ANALYTICAL, [2], 'dur')]
        overview = quality_overview(combined_fixtures.quality_fixture(issues), 5)
        self.assertEqual(overview['missing_values']['occurrences'], 4)
        self.assertEqual(overview['missing_values']['affected_records'], 3)
        self.assertEqual(overview['duplicates']['affected_records'], 1)
        self.assertEqual(overview['invalid_values']['affected_records'], 1)
        self.assertEqual(overview['inconsistencies']['affected_records'], 1)
        self.assertEqual(overview['analytical_anomalies']['occurrences'], 3)
        self.assertEqual(overview['analytical_anomalies']['affected_records'], 2)

    def test_summaries_separate_probability_score_and_accuracy(self):
        result = format_combined_api_response(self.raw)
        self.assertEqual(result['data_quality']['score'], 100)
        self.assertNotIn('accuracy', result['data_quality'])
        self.assertNotIn('accuracy', result['intrusion_summary'])
        self.assertEqual(result['intrusion_summary']['records_predicted'], 9)
        self.assertEqual(result['intrusion_summary']['average_predicted_class_probability'], .7)
        self.assertEqual(result['reliability_summary']['low_count'], 1)

    def test_recommendation_counts_use_full_file_not_page(self):
        first = format_combined_api_response(self.raw)
        self.raw['records'] = []
        self.raw['pagination'].update(offset=999, returned_records=0, next_offset=None)
        second = format_combined_api_response(self.raw)
        self.assertEqual(first['recommendations'], second['recommendations'])
        self.assertEqual([item['affected_records'] for item in first['recommendations']], [1, 4, 1])
        self.assertTrue(all('reason' in item and 'priority' in item for item in first['recommendations']))
        self.assertFalse(any('block' in item['message'].lower() for item in first['recommendations']))

    def test_outliers_not_attacks_in_recommendations(self):
        self.raw['quality_overview']['analytical_anomalies']['affected_records'] = 8
        result = format_combined_api_response(self.raw)
        self.assertEqual(result['intrusion_summary']['malicious_count'], 4)
        anomaly = next(item for item in result['recommendations'] if 'anomalies' in item['message'])
        self.assertEqual(anomaly['affected_records'], 8)
        self.assertIn('not automatically', anomaly['reason'])

    def test_missing_invalid_duplicate_recommendations(self):
        for group in ['missing_values', 'invalid_values', 'duplicates']:
            self.raw['quality_overview'][group]['affected_records'] = 2
        result = format_combined_api_response(self.raw)
        self.assertEqual(len(result['recommendations']), 6)

    def test_no_unsupported_recommendations_for_clean_normal_file(self):
        self.raw['summary'].update(malicious_count=0, rejected_count=0)
        self.raw['prediction_by_reliability']['Review']['malicious_count'] = 0
        self.assertEqual(format_combined_api_response(self.raw)['recommendations'], [])

    def test_next_page_metadata(self):
        result = format_combined_api_response(self.raw)
        self.assertTrue(result['pagination']['has_more'])
        self.raw['pagination'].update(offset=8, returned_records=2, next_offset=None)
        self.assertFalse(format_combined_api_response(self.raw)['pagination']['has_more'])
        self.raw['pagination'].update(offset=0, limit=0, returned_records=0, next_offset=None)
        self.assertTrue(format_combined_api_response(self.raw)['pagination']['has_more'])

    def test_rejection_reason_explicit(self):
        records = format_combined_api_response(self.raw)['records']
        self.assertIsNone(records[0]['rejection_reason'])
        self.assertEqual(records[1]['rejection_reason'], 'Invalid dur')

    def test_missing_or_invalid_evaluation_never_faked(self):
        for evaluation in [None, {}, {'metrics': {'accuracy': float('nan')}}]:
            self.raw['saved_evaluation'] = evaluation
            with self.assertRaises(PredictionError) as raised:
                format_combined_api_response(self.raw)
            self.assertEqual(raised.exception.status_code, 503)

    def test_metadata_not_mutated(self):
        original = deepcopy(self.raw)
        result = format_combined_api_response(self.raw)
        result['model_performance']['confusion_matrix'][0][0] = 999
        self.assertEqual(self.raw, original)

    def test_summary_column_details_bounded(self):
        issues = [combined_fixtures.finding('missing', QUALITY, [0], 'column' + str(i)) for i in range(200)]
        result = quality_overview(combined_fixtures.quality_fixture(issues), 1)
        self.assertEqual(result['missing_values']['occurrences'], 200)
        self.assertEqual(len(result['missing_values']['by_column']), 100)
        self.assertTrue(result['missing_values']['columns_truncated'])


if __name__ == '__main__':
    unittest.main()
