"""Synthetic tests for contextual advice and unchanged assessment contracts."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import pandas as pd

from pipeline import run_pipeline_from_dataframe
from recommendation_policy import build_recommendation
from translator import translate_all_issues, translate_issue


class RecommendationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.context = {'name': 'human_resources', 'confidence': .9}
        self.profile = {'role': 'phone', 'semantic_tags': ['phone', 'contact'], 'confidence': .9}
        self.issue = {'check': 'missing', 'column': 'channel', 'count': 24, 'pct': 4,
                      'row_indices': list(range(24))}

    def test_equivalent_semantics_ignore_column_spelling(self):
        first = translate_issue(self.issue, dataset_context=self.context, column_profile=self.profile)
        renamed = {**self.issue, 'column': 'arbitrary_label'}
        second = translate_issue(renamed, dataset_context=self.context, column_profile=self.profile)
        self.assertEqual(first['recommendation']['priority'], second['recommendation']['priority'])
        self.assertEqual(first['issue_to_review']['impact'], second['issue_to_review']['impact'])
        self.assertEqual(first['recommendation']['action'].replace("'channel'", "'arbitrary_label'"), second['recommendation']['action'])

    def test_domain_is_not_an_action_source(self):
        outputs = [build_recommendation(self.issue, self.profile, {'name': d, 'confidence': .9})
                   for d in ['human_resources', 'education', 'sales', 'inventory', 'healthcare', 'finance', 'unknown']]
        self.assertTrue(all(item == outputs[0] for item in outputs))

    def test_evidence_priority_is_preserved(self):
        for priority in ['low', 'medium', 'high']:
            result = build_recommendation({**self.issue, 'priority': priority}, self.profile, self.context)
            self.assertEqual(result['severity'], priority)

    def test_evidence_changes_action_without_domain_templates(self):
        evidence = {'review_questions': ['Compare coverage between the observed groups.'],
                    'potential_impact': ['Group summaries have different coverage.']}
        result = build_recommendation({**self.issue, 'evidence': evidence}, self.profile, self.context)
        self.assertIn(evidence['review_questions'][0], result['recommendation']['action'])
        self.assertIn(evidence['potential_impact'][0], result['impact'])
        self.assertNotIn('employee communication', result['impact'])

    def test_unknown_domain_does_not_suppress_evidence(self):
        issue = {**self.issue, 'priority': 'high', 'evidence': {'review_questions': ['Check the observed coverage difference.']}}
        for context in [{'name': 'unknown'}, {'name': 'healthcare', 'confidence': .2}, {'conflicting': True}]:
            result = build_recommendation(issue, self.profile, context)
            self.assertEqual(result['severity'], 'high')
            self.assertIn('observed coverage difference', result['recommendation']['action'])
            self.assertNotIn('patient', result['impact'])

    def test_uncertain_or_conflicting_column_meaning_is_qualified(self):
        for profile in [{'role': 'phone', 'confidence': .1},
                        {**self.profile, 'contradictions': ['Conflicting value patterns']}, {}]:
            result = build_recommendation(self.issue, profile, self.context)
            self.assertIn('field purpose is uncertain', result['impact'])
            self.assertNotIn('employee communication', result['impact'])

    def test_review_candidates_not_claimed_as_errors(self):
        for check in ['outlier', 'invalid_categorical']:
            result = build_recommendation({**self.issue, 'check': check}, self.profile, self.context)
            self.assertIn('not established errors', result['description'])
            self.assertNotIn('Delete', result['recommendation']['action'])

    def test_risk_and_legacy_consistent_for_every_issue_type(self):
        for check in ['missing', 'duplicate', 'format', 'outlier', 'invalid_email',
                      'invalid_phone', 'invalid_date', 'invalid_currency', 'invalid_numeric',
                      'invalid_text', 'invalid_categorical', 'unknown']:
            with self.subTest(check=check):
                result = translate_issue({**self.issue, 'check': check}, dataset_context=self.context, column_profile=self.profile)
                self.assertEqual(result['issue_to_review']['severity'], result['recommendation']['priority'])
                self.assertEqual(result['legacy']['severity'], result['recommendation']['priority'])
                self.assertEqual(result['legacy']['suggestion'], result['recommendation']['action'])
                self.assertIn('separate from the numerical quality-score penalty', result['recommendation']['reason'])

    def test_evidence_population_and_no_distinct_person_claim(self):
        issue = {**self.issue, 'evidence': {'population': 'all data records'}}
        result = translate_issue(issue, dataset_context=self.context, column_profile=self.profile)
        self.assertIn('24 affected records', result['issue_to_review']['description'])
        self.assertIn('4% of all data records', result['issue_to_review']['description'])
        self.assertNotIn('24 employees', str(result))

    def test_inputs_not_mutated_and_legacy_callers_supported(self):
        before = deepcopy((self.issue, self.profile, self.context))
        translate_all_issues([self.issue], ['channel'], self.context, {'channel': self.profile})
        self.assertEqual(before, (self.issue, self.profile, self.context))
        result = translate_all_issues([self.issue])
        self.assertTrue(result[0]['recommendation']['action'])
        self.assertIn('uncertain', result[0]['issue_to_review']['impact'])

    def test_translated_response_keys_unchanged(self):
        result = translate_issue(self.issue, dataset_context=self.context, column_profile=self.profile)
        self.assertEqual(set(result), {'issue_to_review', 'recommendation', 'legacy'})
        self.assertEqual(set(result['issue_to_review']), {'title', 'description', 'impact', 'severity', 'evidence'})
        self.assertEqual(set(result['recommendation']), {'title', 'action', 'reason', 'priority'})
        self.assertEqual(set(result['legacy']), {'title', 'description', 'suggestion', 'severity', 'issue_type', 'column', 'count', 'pct'})
        self.assertEqual(set(result['issue_to_review']['evidence']), {'issue_type', 'column', 'affected_records', 'affected_percentage', 'dataset_context', 'examples'})

    def test_pipeline_forwards_profiles_without_changing_assessment(self):
        df = pd.DataFrame({'email': ['person@example.com', '', 'bad'], 'quantity': [1, 2, 3]})
        baseline = run_pipeline_from_dataframe(df)
        def alternate(issue, profile, context):
            result = build_recommendation(issue, profile, context)
            result['severity'] = 'high'
            result['recommendation']['priority'] = 'high'
            result['description'] = 'Alternative remediation policy'
            return result
        with patch('translator.build_recommendation', side_effect=alternate) as policy:
            changed = run_pipeline_from_dataframe(df)
        self.assertEqual(policy.call_args_list[0].args[1], changed['column_profiles']['email'])
        self.assertEqual(policy.call_args_list[0].args[2], changed['dataset_context'])
        translated_fields = {'translated_issues', 'issues_to_review', 'recommendations'}
        self.assertNotEqual(baseline['translated_issues'], changed['translated_issues'])
        self.assertEqual({k: v for k, v in baseline.items() if k not in translated_fields},
                         {k: v for k, v in changed.items() if k not in translated_fields})
        self.assertEqual(set(changed), {'filename', 'total_rows', 'total_columns', 'column_profiles', 'column_types', 'dataset_context', 'issues', 'translated_issues', 'issues_to_review', 'recommendations', 'issue_summary', 'score', 'grade', 'label', 'total_penalty', 'issue_details', 'relationships', 'score_policy', 'finding_summary', 'domain_validation'})


if __name__ == '__main__':
    unittest.main()
