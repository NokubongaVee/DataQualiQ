"""Synthetic phone-structure regressions; no CSV files or dataset fixtures."""
import unittest

import pandas as pd

from pipeline import run_pipeline_from_dataframe
from validity_checks import check_phone_validity


class PhoneValidationTests(unittest.TestCase):
    def check_values(self, values):
        return check_phone_validity(pd.DataFrame({'Phone': values}), 'Phone')

    def test_accepts_common_structure(self):
        values = [
            '2345678', '23456789', '234567890', '2345678901',
            '+123456789012345', '234-567-8901', '234.567.8901',
            '234 567 8901', '(234) 567-8901', '(234)567-8901',
            '+1 (234) 567-8901', '+44(20)12345678', '+44 20 1234 5678',
        ]
        self.assertEqual(self.check_values(values)['count'], 0)

    def test_digit_limits_ignore_punctuation(self):
        for digits in range(1, 18):
            with self.subTest(digits=digits):
                value = '+1-' + '2' * (digits - 1) if digits > 1 else '1'
                issue = self.check_values([value])
                self.assertEqual(issue['count'], 0 if 7 <= digits <= 15 else 1)

    def test_rejects_misplaced_and_repeated_separators(self):
        values = [
            '-2345678901', '.2345678901', '2345678901-', '2345678901.',
            '234--5678901', '234..5678901', '234-.5678901',
            '234- 5678901', '234  5678901', '234 -5678901',
            '+-2345678901', '+.2345678901',
        ]
        self.assertEqual(self.check_values(values)['row_indices'], list(range(len(values))))

    def test_rejects_misplaced_plus(self):
        values = ['++12345678901', '123+45678901', '12345678901+', '+1+2345678901']
        self.assertEqual(self.check_values(values)['count'], len(values))

    def test_rejects_malformed_parentheses(self):
        values = [
            '(2345678901', '2345678901)', ')234(5678901',
            '((234))5678901', '()2345678901', '(23-4)5678901',
            '(23 4)5678901', '(+234)5678901', '(234)-.5678901',
        ]
        self.assertEqual(self.check_values(values)['count'], len(values))

    def test_nonseparator_characters_and_outer_whitespace_rejected(self):
        values = ['234a5678901', '234/5678901', '234\t5678901',
                  '234\n5678901', ' 2345678901', '2345678901 ', '2345678901\n']
        self.assertEqual(self.check_values(values)['count'], len(values))

    def test_missing_exclusion_denominator_indexes_and_examples(self):
        df = pd.DataFrame({'Phone': [None, '', '   ', ' N/A ', 'NA', 'null', 'NaN', 'none',
                                     '2345678', '-2345678', '++2345678', '23456789']},
                          index=range(10, 22))
        issue = check_phone_validity(df, 'Phone')
        self.assertEqual(issue, {
            'check': 'invalid_phone', 'column': 'Phone', 'count': 2,
            'pct': 50.0, 'row_indices': [19, 20],
            'examples': ['-2345678', '++2345678'],
        })

    def test_empty_and_all_missing(self):
        for values in [[], [None, '', 'N/A', ' ']]:
            with self.subTest(values=values):
                issue = self.check_values(values)
                self.assertEqual((issue['count'], issue['pct'], issue['row_indices'], issue['examples']),
                                 (0, 0, [], []))

    def test_multiple_failures_count_once_per_occurrence(self):
        issue = self.check_values(['--12', '--12', '2345678'])
        self.assertEqual(issue['count'], 2)
        self.assertEqual(issue['row_indices'], [0, 1])
        self.assertEqual(issue['pct'], 66.7)

    def test_pipeline_retains_phone_finding_contract(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'Phone': ['2345678', '-2345678', 'N/A']}))
        finding = next(i for i in result['issues'] if i['check'] == 'invalid_phone')
        self.assertEqual((finding['count'], finding['pct'], finding['row_indices']), (1, 50.0, [1]))
        translated = next(i for i in result['translated_issues'] if i['legacy']['issue_type'] == 'invalid_phone')
        self.assertEqual(translated['legacy']['count'], 1)
        self.assertTrue(translated['recommendation']['action'])


if __name__ == '__main__':
    unittest.main()
