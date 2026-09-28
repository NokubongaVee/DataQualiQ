"""Behavioural tests: anonymous headers, changed evidence, diverse CSV exports."""
import json
import unittest
import pandas as pd
from csv_loading import load_csv
from pipeline import run_pipeline_from_dataframe
from type_inference import infer_column_profile


def datasets():
    n = 60
    return {
        'sales': pd.DataFrame({'order_id': [f'O{i:03}' for i in range(n)],
            'price': [str(10 + i % 9) for i in range(n-1)] + ['9000'],
            'region': ['North'] * 30 + ['South'] * 30,
            'channel': [f'p{i}@example.org' for i in range(n-1)] + ['broken']}),
        'hr': pd.DataFrame({'worker_code': [f'W{i:03}' for i in range(n)],
            'division': ['A'] * 30 + ['B'] * 30,
            'compensation': [''] * 21 + [str(30000 + i * 17) for i in range(n-21)],
            'joined': ['2025-01-10'] * (n-1) + ['not-a-date']}),
        'education': pd.DataFrame({'learner_no': [f'L{i:03}' for i in range(n)],
            'programme': ['Science'] * 30 + ['Arts'] * 29 + [' arts '],
            'mark': [str(40 + i % 40) for i in range(n-1)] + ['bad'],
            'term': ['T1'] * 30 + ['T2'] * 30}),
        'spectrometry': pd.DataFrame({'zeta': [f'Q{i:03}' for i in range(n-1)] + ['Q000'],
            'omega': [str(1.1 + i % 7 / 10) for i in range(n-1)] + ['999'],
            'lambda': ['green'] * 30 + ['violet'] * 29 + ['Violet'],
            'nu': ['The instrument acquired a distinct observation ' + str(i) for i in range(n)]}),
    }


def find(result, check, column=None):
    return next(i for i in result['issues'] if i['check'] == check and (column is None or i['column'] == column))


def action(result, check, column=None):
    return next(i['recommendation']['action'] for i in result['translated_issues']
                if i['legacy']['issue_type'] == check and (column is None or i['legacy']['column'] == column))


class GeneralisationTests(unittest.TestCase):
    def test_diverse_csv_datasets(self):
        expected = {'sales': {'outlier', 'invalid_email'}, 'hr': {'missing', 'invalid_date'},
                    'education': {'format', 'invalid_numeric'},
                    'spectrometry': {'outlier', 'format', 'repeated_identifier'}}
        for name, frame in datasets().items():
            with self.subTest(dataset=name):
                result = run_pipeline_from_dataframe(load_csv(frame.to_csv(index=False).encode()), name + '.csv')
                self.assertTrue(expected[name] <= {i['check'] for i in result['issues']})
                for col, profile in result['column_profiles'].items():
                    self.assertEqual(profile['measurements']['full']['row_count'], len(frame))
                    self.assertTrue(all('reason' in c for c in profile['checks'].values()))
                json.dumps(result, allow_nan=False)

    def test_rename_preserves_value_based_findings(self):
        for name, frame in datasets().items():
            mapping = {c: f'x{n}' for n, c in enumerate(frame.columns)}
            before = run_pipeline_from_dataframe(frame)
            after = run_pipeline_from_dataframe(frame.rename(columns=mapping))
            checks = {'missing', 'format', 'invalid_numeric', 'invalid_email', 'invalid_date', 'outlier'}
            def signatures(result, rename):
                return {(i['check'], rename.get(i['column'], i['column']), tuple(i['row_indices']))
                        for i in result['issues'] if i['check'] in checks}
            with self.subTest(dataset=name):
                self.assertEqual(signatures(before, mapping), signatures(after, {}))

    def test_filename_invariance(self):
        df = datasets()['spectrometry']
        a, b = [run_pipeline_from_dataframe(df, name) for name in ['sales.csv', 'never-seen.csv']]
        a.pop('filename'); b.pop('filename')
        self.assertEqual(a, b)

    def test_misleading_header_conflict(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'email': ['10', '20', '30', '40', '50']}))
        self.assertEqual(result['column_types']['email'], 'numeric')
        self.assertNotIn('invalid_email', [i['check'] for i in result['issues']])
        self.assertTrue(find(result, 'header_conflict')['evidence']['semantic']['contradictions'])

    def test_unique_prose_is_not_identifier(self):
        result = run_pipeline_from_dataframe(datasets()['spectrometry'])
        self.assertEqual(result['column_profiles']['nu']['role'], 'free_text')
        self.assertFalse(result['column_profiles']['nu']['checks']['repeated_identifier']['selected'])

    def test_generic_value_is_not_money(self):
        p = infer_column_profile(pd.Series(range(20), name='value'), 'value')
        self.assertEqual(p['role'], 'unknown')

    def test_numeric_identifier_skips_outliers(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'record_id': list(range(19)) + [999999]}))
        self.assertFalse(result['column_profiles']['record_id']['checks']['outlier']['selected'])

    def test_anonymous_zero_padded_codes(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'x': [f'{i:05}' for i in range(30)]}))
        self.assertEqual(result['column_profiles']['x']['role'], 'identifier')

    def test_repeated_keys_with_conflicts(self):
        frame = pd.DataFrame({'record_id': ['001', '001', '002'], 'amount': ['500', '750', '800']})
        result = run_pipeline_from_dataframe(frame)
        issue = find(result, 'repeated_identifier')
        self.assertEqual(issue['row_indices'], [0, 1])
        self.assertEqual(issue['relationship']['conflicting_columns'], ['amount'])
        self.assertNotIn('duplicate', [i['check'] for i in result['issues']])
        self.assertIn('multiple events', action(result, 'repeated_identifier'))

    def test_identical_associations_change_recommendation(self):
        a = pd.DataFrame({'record_id': ['001', '001', '002'], 'reading': ['500', '500', '800']})
        b = a.copy(); b.loc[1, 'reading'] = '750'
        ra, rb = run_pipeline_from_dataframe(a), run_pipeline_from_dataframe(b)
        self.assertNotEqual(action(ra, 'repeated_identifier'), action(rb, 'repeated_identifier'))
        self.assertIn('matching associated fields', action(ra, 'repeated_identifier'))

    def test_legitimate_events_not_called_duplicate_rows(self):
        frame = pd.DataFrame({'entity_id': ['A01'] * 10, 'observed': [f'2025-01-{i+1:02}' for i in range(10)]})
        result = run_pipeline_from_dataframe(frame)
        self.assertNotIn('duplicate', [i['check'] for i in result['issues']])
        self.assertTrue(find(result, 'repeated_identifier')['evidence']['candidate'])

    def test_missing_concentration_changes_advice(self):
        a = pd.DataFrame({'x': ['8'] * 100, 'group': ['A'] * 50 + ['B'] * 50})
        a.loc[[3, 70], 'x'] = ''
        b = a.copy(); b['x'] = [''] * 35 + ['8'] * 65
        ra, rb = run_pipeline_from_dataframe(a), run_pipeline_from_dataframe(b)
        self.assertNotIn('collection coverage', action(ra, 'missing', 'x'))
        self.assertIn('collection coverage for group=A', action(rb, 'missing', 'x'))
        self.assertGreater(find(rb, 'missing')['priority_score'], find(ra, 'missing')['priority_score'])

    def test_comissingness_is_observation_not_cause(self):
        frame = pd.DataFrame({'a': [''] * 8 + ['left'] * 12, 'b': [''] * 8 + ['right'] * 12})
        result = run_pipeline_from_dataframe(frame)
        relations = result['relationships']['observations']
        self.assertEqual(next(r for r in relations if r['kind'] == 'co_missingness')['overlap_count'], 8)
        self.assertIn('optional section', action(result, 'missing'))

    def test_categorical_dependency_requires_repetition(self):
        frame = pd.DataFrame({'a': ['A'] * 30 + ['B'] * 30, 'b': ['x'] * 29 + ['y'] + ['y'] * 30})
        result = run_pipeline_from_dataframe(frame)
        issue = find(result, 'relationship_deviation')
        self.assertEqual(issue['row_indices'], [29])
        self.assertTrue(issue['evidence']['candidate'])

    def test_unique_columns_do_not_make_dependencies(self):
        frame = pd.DataFrame({'a': [f'word{i}' for i in range(60)], 'b': ['x', 'y'] * 30})
        result = run_pipeline_from_dataframe(frame)
        self.assertNotIn('categorical_dependency', [r['kind'] for r in result['relationships']['observations']])

    def test_unknown_domain_useful(self):
        result = run_pipeline_from_dataframe(datasets()['spectrometry'])
        self.assertEqual(result['dataset_context']['name'], 'unknown')
        self.assertTrue(result['recommendations'])
        self.assertIn('middle half', action(result, 'outlier'))

    def test_outlier_distribution_changes_advice(self):
        a = pd.DataFrame({'x': list(range(20)) + [999]})
        b = a * 100
        self.assertNotEqual(action(run_pipeline_from_dataframe(a), 'outlier'),
                            action(run_pipeline_from_dataframe(b), 'outlier'))

    def test_sparse_and_all_missing_columns(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'a': [''] * 30, 'b': [''] * 29 + ['note']}))
        self.assertEqual(result['column_profiles']['a']['type'], 'unknown')
        self.assertIn('no observed values', action(result, 'missing', 'a'))
        self.assertIn('verify a value', action(result, 'missing', 'b'))

    def test_ambiguous_dates_are_review_only(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'x': ['01/02/2025', '03/04/2025', '05/06/2025']}))
        issue = find(result, 'ambiguous_date')
        self.assertEqual(issue['count'], 3)
        self.assertTrue(issue['review_only'])
        self.assertEqual(result['score'], 100)

    def test_percentage_syntax_without_invented_bounds(self):
        frame = pd.DataFrame({'x': ['120%'] * 19 + ['oops']})
        result = run_pipeline_from_dataframe(frame)
        self.assertEqual(find(result, 'invalid_percentage')['row_indices'], [19])

    def test_negative_values_not_invalid_from_name(self):
        for name in ['amount', 'age', 'height', 'x']:
            result = run_pipeline_from_dataframe(pd.DataFrame({name: [-1, -2, -3]}))
            self.assertNotIn('invalid_numeric', [i['check'] for i in result['issues']])

    def test_sample_coverage_explicit(self):
        p = infer_column_profile(pd.Series(range(1200)), 'x')
        self.assertEqual(p['measurements']['full']['present_count'], 1200)
        self.assertEqual(p['measurements']['sample']['size'], 1000)

    def test_date_values_override_phone_header(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'phone': ['2025-01-01', '2025-02-01', '2025-03-01']}))
        self.assertEqual(result['column_types']['phone'], 'date')
        self.assertTrue(find(result, 'header_conflict'))

    def test_scientific_notation_is_not_an_identifier(self):
        frame = pd.DataFrame({'x': [f'{i}e1' for i in range(1, 21)] + ['9e8']})
        result = run_pipeline_from_dataframe(frame)
        self.assertNotEqual(result['column_profiles']['x']['role'], 'identifier')
        self.assertEqual(find(result, 'outlier')['row_indices'], [20])

    def test_equal_missing_count_different_distribution_changes_review(self):
        a = pd.DataFrame({'x': [''] * 30 + ['8'] * 70, 'cohort': ['A'] * 50 + ['B'] * 50})
        b = a.copy(); b['x'] = ['' if i % 10 < 3 else '8' for i in range(100)]
        ra, rb = run_pipeline_from_dataframe(a), run_pipeline_from_dataframe(b)
        self.assertEqual(find(ra, 'missing')['count'], find(rb, 'missing')['count'])
        self.assertIn('coverage for cohort=A', action(ra, 'missing'))
        self.assertNotIn('coverage for cohort=A', action(rb, 'missing'))

    def test_equal_format_count_different_variants_changes_review(self):
        a = pd.DataFrame({'x': ['Alpha'] * 29 + ['alpha']})
        b = pd.DataFrame({'x': ['Beta'] * 29 + [' Beta ']})
        self.assertNotEqual(action(run_pipeline_from_dataframe(a), 'format'),
                            action(run_pipeline_from_dataframe(b), 'format'))

    def test_relationship_coverage_limits_are_explicit(self):
        from unittest.mock import patch
        frame = pd.DataFrame({'a': ['x'] * 20, 'b': ['y'] * 20, 'c': ['z'] * 20})
        with patch('relationships.MAX_ROWS', 10), patch('relationships.MAX_COLUMNS', 2):
            result = run_pipeline_from_dataframe(frame)
        coverage = result['relationships']['coverage']
        self.assertTrue(coverage['sampled'])
        self.assertTrue(coverage['columns_truncated'])
        self.assertEqual(coverage['rows_examined_for_pairs'], 10)

    def test_internal_looking_headers_do_not_collide(self):
        frame = pd.DataFrame({'record_id': ['001', '001'], '_candidate_key_': ['x', 'y']})
        result = run_pipeline_from_dataframe(frame)
        self.assertEqual(find(result, 'repeated_identifier')['relationship']['conflicting_columns'], ['_candidate_key_'])

    def test_extreme_numeric_magnitudes_remain_json_safe(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'x': [-1e308, 1e308, 1.1e308, 1.2e308, 1.5e308, 1.6e308, 1.7e308, 1.75e308]}))
        json.dumps(result, allow_nan=False)
        self.assertFalse(result['column_profiles']['x']['checks']['outlier']['selected'])
        self.assertTrue(result['column_profiles']['x']['measurements']['full']['numeric']['arithmetic_limited'])

    def test_evidence_counts_and_sorting(self):
        result = run_pipeline_from_dataframe(datasets()['hr'])
        ranks = [i['issue_to_review']['evidence']['priority_score'] for i in result['translated_issues']]
        self.assertEqual(ranks, sorted(ranks, reverse=True))
        for i in result['issues']:
            self.assertEqual(i['count'], len(i['row_indices']))
            self.assertEqual(i['pct'], round(100 * i['count'] / i['denominator'], 1))
            self.assertTrue(i['evidence']['observations'])
            self.assertTrue(i['evidence']['review_questions'])
            self.assertIn('interpretation_confidence', i['evidence'])

    def test_delimiters_encodings(self):
        frame = pd.DataFrame({'x': ['André', 'André', ' André '], 'y': ['1', '', '3']})
        baseline = None
        for delimiter in [',', ';', '\t', '|']:
            for encoding in ['utf-8-sig', 'cp1252', 'utf-16']:
                result = run_pipeline_from_dataframe(load_csv(frame.to_csv(index=False, sep=delimiter).encode(encoding)))
                signature = [(i['check'], i['column'], i['row_indices']) for i in result['issues']]
                baseline = baseline if baseline is not None else signature
                self.assertEqual(signature, baseline)


if __name__ == '__main__':
    unittest.main()
