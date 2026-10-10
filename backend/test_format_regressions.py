"""Format regressions using synthetic values only; no CSV fixtures."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import pandas as pd

from generic_checks import check_date_format_consistency, check_numeric_format_consistency
from pipeline import run_pipeline_from_dataframe
from validity_checks import check_categorical_consistency, check_currency_validity


class FormatRegressionTests(unittest.TestCase):
    def test_date_component_widths_are_equivalent(self):
        for values in [
            ['4/2/2021', '12/7/2021', '04/02/2021', '12/17/2021'],
            ['2021-4-2', '2021-12-7', '2021-04-02'],
        ]:
            with self.subTest(values=values):
                issue = check_date_format_consistency(pd.DataFrame({'date': values}), 'date')
                self.assertEqual(issue['count'], 0)
                self.assertEqual(issue['pct'], 0)

    def test_date_separator_and_year_position_differences_remain(self):
        df = pd.DataFrame({'date': ['2021-1-2', '2021-11-2', '2021-03-04', '2021/4/5', '6-7-2021']})
        issue = check_date_format_consistency(df, 'date')
        self.assertEqual(issue['row_indices'], [3, 4])
        self.assertEqual(issue['pct'], 40.0)

    def test_date_denominator_only_includes_compared_styles(self):
        df = pd.DataFrame({'date': ['2021-1-2', '2021-11-2', '2021/4/5', 'January 6, 2021', 'bad', '', 'N/A']})
        issue = check_date_format_consistency(df, 'date')
        self.assertEqual(issue['row_indices'], [2])
        self.assertEqual(issue['count'], 1)
        self.assertEqual(issue['pct'], 33.3)

    def test_no_comparable_dates(self):
        issue = check_date_format_consistency(pd.DataFrame({'date': ['January 6, 2021', '', 'bad']}), 'date')
        self.assertEqual((issue['count'], issue['pct'], issue['row_indices']), (0, 0, []))

    def test_valid_thousands_grouping_is_equivalent(self):
        for values in [
            ['100', '1000', '1,000', '1000000.50', '1,000,000.50', '-1,000'],
            ['$100', '$1000', '$1,000', '$1,000,000.50'],
        ]:
            with self.subTest(values=values):
                self.assertEqual(check_numeric_format_consistency(pd.DataFrame({'v': values}), 'v')['count'], 0)

    def test_numeric_symbol_and_whitespace_differences_remain(self):
        issue = check_numeric_format_consistency(pd.DataFrame({'v': ['1000', '1,000', '2000', '$1,000', ' 1000 ']}), 'v')
        self.assertEqual(issue['row_indices'], [3, 4])
        self.assertEqual(issue['pct'], 40.0)

    def test_malformed_grouping_not_normalised(self):
        issue = check_numeric_format_consistency(pd.DataFrame({'v': ['1000', '1,000', '2000', '12,,34']}), 'v')
        self.assertEqual(issue['row_indices'], [3])

    def test_case_and_whitespace_are_not_spelling_variants(self):
        for common, variant in [('Active', 'ACTIVE'), ('Active', ' Active '), (' Active ', 'ACTIVE')]:
            with self.subTest(common=common, variant=variant):
                issue = check_categorical_consistency(pd.DataFrame({'status': [common] * 99 + [variant]}), 'status')
                self.assertEqual((issue['count'], issue['pct'], issue['row_indices']), (0, 0, []))

    def test_nonnumeric_text_is_only_a_validity_failure(self):
        df = pd.DataFrame({'amount': ['R100.00', 'R250.00', 'R75.00', 'oops']})
        issue = check_numeric_format_consistency(df, 'amount')
        self.assertEqual((issue['count'], issue['pct'], issue['row_indices']), (0, 0, []))
        self.assertEqual(issue['denominator'], 4)
        self.assertEqual(issue['pattern_support'], 3)
        invalid = check_currency_validity(df, 'amount')
        self.assertEqual((invalid['count'], invalid['pct'], invalid['row_indices']), (1, 25.0, [3]))

    def test_numeric_formats_survive_filtering_with_original_denominator(self):
        df = pd.DataFrame({'amount': ['R100.00', 'R250.00', 'R75.00', ' R50.00 ', '100.00', 'oops', 'NA']})
        issue = check_numeric_format_consistency(df, 'amount')
        self.assertEqual(issue['row_indices'], [3, 4])
        self.assertEqual((issue['count'], issue['pct'], issue['denominator']), (2, 33.3, 6))
        # Enough valid currency examples to exercise the existing pipeline routing.
        pipeline_df = pd.concat([df, pd.DataFrame({'amount': ['R125.00'] * 14})], ignore_index=True)
        result = run_pipeline_from_dataframe(pipeline_df)
        finding = next(i for i in result['issues'] if i['check'] == 'format')
        self.assertEqual((finding['row_indices'], finding['count'], finding['pct'], finding['denominator']), ([3, 4], 2, 10.0, 20))
        review = next(i for i in result['translated_issues'] if i['legacy']['issue_type'] == 'format')
        self.assertEqual((review['legacy']['count'], review['legacy']['pct']), (2, 10.0))

    @unittest.skipUnless(shutil.which('node'), 'Node required to verify frontend aggregation')
    def test_pipeline_format_is_preserved_without_false_spelling_finding(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'status': ['Active'] * 99 + [' Active ']}))
        findings = [i for i in result['issues'] if i['check'] == 'format' or i['check'].startswith('invalid_')]
        self.assertEqual({i['check'] for i in findings}, {'format'})
        self.assertEqual([i['row_indices'] for i in findings], [[99]])
        self.assertEqual((findings[0]['count'], findings[0]['pct'], findings[0]['denominator']), (1, 1.0, 100))
        review = next(i for i in result['translated_issues'] if i['legacy']['issue_type'] == 'format')
        self.assertEqual((review['legacy']['column'], review['legacy']['count'], review['legacy']['pct']), ('status', 1, 1.0))
        self.assertEqual(review['issue_to_review']['evidence']['row_indices'], [99])
        helper = Path(__file__).resolve().parent.parent / 'frontend/src/utils/affectedValues.js'
        script = f"""
            import {{ countInvalidFormatValues }} from {json.dumps(helper.as_uri())};
            let input = '';
            for await (const chunk of process.stdin) input += chunk;
            console.log(countInvalidFormatValues(JSON.parse(input)));
        """
        completed = subprocess.run(['node', '--input-type=module', '-e', script], input=json.dumps(result['issues']), text=True, capture_output=True, check=True)
        self.assertEqual(completed.stdout.strip(), '1')


if __name__ == '__main__':
    unittest.main()
