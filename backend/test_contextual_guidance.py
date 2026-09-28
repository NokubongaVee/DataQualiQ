import unittest
import pandas as pd
from pipeline import run_pipeline_from_dataframe


class ContextualGuidanceTests(unittest.TestCase):
    def assess(self, alternate=False, dependent=False):
        data = {'Applicant_ID': list(range(10)), 'Job_Position': ['Analyst'] * 10,
                'Email': [None] * 6 + ['a@example.com'] * 4,
                'Age': [None] * 8 + [25, 32]}
        if alternate:
            data['Phone'] = ['+27821234567'] * 10
        if dependent:
            data['Age_Group'] = ['adult'] * 10
        return run_pipeline_from_dataframe(pd.DataFrame(data))

    def finding(self, result, column):
        return next(i for i in result['translated_issues'] if i['legacy']['column'] == column and i['legacy']['issue_type'] == 'missing')

    def test_applicant_contacts_prioritised_over_optional_age(self):
        result = self.assess()
        self.assertEqual(result['dataset_context']['name'], 'recruitment')
        contact = self.finding(result, 'Email')
        self.assertEqual(contact['recommendation']['priority'], 'high')
        self.assertIn('interview invitations', contact['issue_to_review']['impact'])
        self.assertEqual(contact['issue_to_review']['evidence']['contact_coverage']['without_alternative'], 6)
        self.assertEqual(self.finding(result, 'Age')['recommendation']['priority'], 'low')

    def test_alternative_contact_changes_priority(self):
        contact = self.finding(self.assess(alternate=True), 'Email')
        self.assertEqual(contact['recommendation']['priority'], 'medium')
        self.assertEqual(contact['issue_to_review']['evidence']['contact_coverage']['without_alternative'], 0)

    def test_age_dependency_requires_review(self):
        age = self.finding(self.assess(dependent=True), 'Age')
        self.assertEqual(age['recommendation']['priority'], 'medium')
        self.assertIn('age-dependent', age['issue_to_review']['impact'])

    def test_filename_alone_does_not_establish_recruitment(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'x': [None, 2, 3], 'y': ['a', 'b', 'c']}), 'applicants.csv')
        self.assertEqual(result['dataset_context']['name'], 'unknown')
        for issue in result['translated_issues']:
            self.assertNotIn('interview', issue['issue_to_review']['impact'])
            self.assertTrue(issue['issue_to_review']['evidence']['explanation']['why'])


if __name__ == '__main__':
    unittest.main()
