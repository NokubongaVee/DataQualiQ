import unittest
import pandas as pd
from pipeline import run_pipeline_from_dataframe
from translator import translate_issue


class PlainLanguageTests(unittest.TestCase):
    def duplicate(self, context):
        return translate_issue({'check': 'duplicate', 'column': None, 'count': 167, 'pct': 16.5,
            'priority': 'high', 'evidence': {'population': 'all data records',
            'explanation': {'why': 'Repeated rows', 'consequence': 'Repeated counts', 'next_step': 'Check source'},
            'review_questions': ['Check source']}}, dataset_context=context)

    def test_duplicate_matches_requested_style(self):
        result = self.duplicate({'name': 'unknown'})
        self.assertEqual(result['issue_to_review']['title'], 'Duplicate records detected')
        self.assertEqual(result['issue_to_review']['description'], '167 records in the dataset (16.5% of all data records) repeat earlier rows.')
        self.assertIn('context uncertain', result['issue_to_review']['impact'])
        self.assertIn('legitimate repeated events before merging or deleting', result['recommendation']['action'])

    def test_supported_context_changes_consequence_without_claiming_truth(self):
        sales = self.duplicate({'name': 'sales', 'confidence': .7, 'evidence': ['order and product columns']})
        education = self.duplicate({'name': 'education', 'confidence': .7, 'evidence': ['student and course columns']})
        self.assertIn('revenue totals', sales['issue_to_review']['impact'])
        self.assertIn('assessment counts', education['issue_to_review']['impact'])
        self.assertIn('If these records', sales['issue_to_review']['impact'])
        self.assertEqual(sales['recommendation']['priority'], education['recommendation']['priority'])

    def test_unsupported_context_does_not_invent_domain_impact(self):
        for context in [{'name': 'sales', 'confidence': .9},
                        {'name': 'sales', 'confidence': .2, 'evidence': ['order']},
                        {'name': 'sales', 'confidence': .9, 'evidence': ['order'], 'conflicting': True}]:
            result = self.duplicate(context)
            self.assertNotIn('revenue', result['issue_to_review']['impact'])

    def test_applicant_results_include_extent_and_contact_consequences(self):
        frame = pd.DataFrame({'Applicant_ID': range(10), 'Job_Position': ['Analyst'] * 10,
                              'Email': [None] * 6 + ['demo@example.com'] * 4, 'Age': [None] * 8 + [25, 32]})
        result = run_pipeline_from_dataframe(frame)
        missing = {i['legacy']['column']: i for i in result['translated_issues'] if i['legacy']['issue_type'] == 'missing'}
        self.assertIn('60% of all data records', missing['Email']['issue_to_review']['description'])
        self.assertIn('interview invitations', missing['Email']['issue_to_review']['impact'])
        self.assertIn('original application forms', missing['Email']['recommendation']['action'])
        self.assertEqual(missing['Age']['recommendation']['priority'], 'low')

    def test_education_missing_marks_explain_effect_on_comparisons(self):
        frame = pd.DataFrame({'Student_ID': range(20), 'Programme': ['Science'] * 20,
                              'Semester': ['Term 1'] * 20, 'Mark': [None] * 5 + list(range(60, 75))})
        result = run_pipeline_from_dataframe(frame)
        issue = next(i for i in result['translated_issues'] if i['legacy']['column'] == 'Mark' and i['legacy']['issue_type'] == 'missing')
        self.assertIn('25% of all data records', issue['issue_to_review']['description'])
        self.assertIn('learners out of averages', issue['issue_to_review']['impact'])
        self.assertIn('pending, or not applicable', issue['recommendation']['action'])

    def test_single_missing_value_uses_singular_and_preserves_population(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'value': ['1', '2', None]}))
        issue = next(i for i in result['translated_issues'] if i['legacy']['issue_type'] == 'missing')
        self.assertEqual(issue['issue_to_review']['description'], "1 value in 'value' (33.3% of all data records) is missing.")


    def example(self, check, column, count, pct, profile=None, statistics=None):
        evidence = {'population': 'finite numeric values assessed' if check == 'outlier' else 'present values assessed',
                    'explanation': {'why': 'Finding', 'consequence': 'Old consequence', 'next_step': 'Old action'},
                    'review_questions': [], 'statistics': statistics}
        return translate_issue({'check': check, 'column': column, 'count': count, 'pct': pct,
                                'priority': 'low', 'evidence': evidence},
                               column_profile=profile or {}, dataset_context={'name': 'unknown'})

    def test_weight_explains_incomplete_measurement_averages(self):
        result = self.example('invalid_numeric', 'Weight kg', 5, .5)
        self.assertEqual(result['issue_to_review']['title'], 'Suspicious numeric values detected')
        self.assertIn("5 values in 'Weight kg' (0.5% of present values assessed)", result['issue_to_review']['description'])
        self.assertIn('measurement averages and comparisons incomplete', result['issue_to_review']['impact'])
        self.assertIn("Verify the 5 flagged values in 'Weight kg'", result['recommendation']['action'])
        self.assertIn('Correct only confirmed errors', result['recommendation']['action'])
        self.assertEqual(result['recommendation']['priority'], 'low')

    def test_longitude_outliers_are_not_claimed_to_be_invalid_coordinates(self):
        result = self.example('outlier', 'Longitude', 4, .4, statistics={'q1': 20, 'q3': 30})
        self.assertEqual(result['issue_to_review']['title'], 'Outlier values detected')
        self.assertIn('wrong location', result['issue_to_review']['impact'])
        self.assertIn('does not prove that a coordinate is wrong', result['issue_to_review']['impact'])
        self.assertIn('retain legitimate exceptions', result['recommendation']['action'])
        self.assertIn('not an allowed range', result['recommendation']['action'])

    def test_category_variants_explain_split_counts_without_forced_merging(self):
        result = self.example('invalid_categorical', 'Animal type', 1, .1)
        self.assertEqual(result['issue_to_review']['title'], 'Possible category spelling variants detected')
        self.assertIn("1 value in 'Animal type'", result['issue_to_review']['description'])
        self.assertIn('not established errors', result['issue_to_review']['description'])
        self.assertIn('split it into separate groups', result['issue_to_review']['impact'])
        self.assertIn('retain legitimate categories', result['recommendation']['action'])

    def test_contradictory_header_does_not_drive_measurement_consequence(self):
        result = self.example('outlier', 'Longitude', 4, .4, profile={'contradictions': ['values do not support coordinates']})
        self.assertNotIn('maps', result['issue_to_review']['impact'])
        self.assertNotIn('geographic', result['issue_to_review']['impact'])

    def test_date_format_explains_wrong_periods_and_checks_source(self):
        result = self.example('format', 'Order date', 2, 1, profile={'type': 'date'})
        self.assertIn('wrong period', result['issue_to_review']['impact'])
        self.assertIn("the 2 flagged values in 'Order date'", result['recommendation']['action'])
        self.assertIn('mean the same thing', result['recommendation']['action'])


if __name__ == '__main__':
    unittest.main()
