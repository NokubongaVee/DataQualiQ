"""Format regressions using synthetic values only; no CSV fixtures."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import pandas as pd

from generic_checks import check_date_format_consistency, check_numeric_format_consistency
from pipeline import run_pipeline_from_dataframe


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

    @unittest.skipUnless(shutil.which('node'), 'Node required to verify frontend aggregation')
    def test_pipeline_overlap_is_one_displayed_cell(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'status': ['Active'] * 99 + [' Active ']}))
        findings = [i for i in result['issues'] if i['check'] == 'format' or i['check'].startswith('invalid_')]
        self.assertEqual({i['check'] for i in findings}, {'format', 'invalid_categorical'})
        self.assertEqual([i['row_indices'] for i in findings], [[99], [99]])
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
