"""Regression and real HTTP tests; run with python -m unittest discover -v."""
import asyncio
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pandas as pd
from fastapi import HTTPException, UploadFile

import main
from anomaly_detection import check_numeric_outliers, run_anomaly_detection
from csv_loading import load_csv
from generic_checks import check_missing, check_duplicate_rows, check_categorical_format
from pipeline import run_pipeline_from_dataframe
from scoring import calculate_quality_score
from translator import translate_issue
from type_inference import infer_column_type, infer_column_profile
from validity_checks import (check_numeric_bounds, check_text_quality,
                             check_categorical_consistency, check_currency_validity)

ROOT = Path(__file__).resolve().parent


class CSVTests(unittest.TestCase):
    def test_preserves_values(self):
        df = load_csv(b'id,phone,note\n001,0123456789, NA \n002,0123456790,hello\n')
        self.assertEqual(df.iloc[0].tolist(), ['001', '0123456789', ' NA '])

    def test_single_column_and_delimiters(self):
        for delimiter in [',', ';', '\t', '|']:
            with self.subTest(delimiter=delimiter):
                df = load_csv(f'a{delimiter}b\n1{delimiter}2\n'.encode())
                self.assertEqual(df.shape, (1, 2))
        self.assertEqual(load_csv(b'name\nAlice\nBob\n').shape, (2, 1))

    def test_encodings(self):
        for encoding in ['utf-8-sig', 'cp1252', 'utf-16']:
            with self.subTest(encoding=encoding):
                self.assertEqual(load_csv('name\nAndré\n'.encode(encoding)).iloc[0, 0], 'André')

    def test_quoted_fields(self):
        df = load_csv(b'a,b\n"hello, world","two\nlines"\n')
        self.assertEqual(df.iloc[0].tolist(), ['hello, world', 'two\nlines'])

    def test_long_text_field_within_upload_limit(self):
        self.assertEqual(len(load_csv(b'note\n' + b'x' * 150000).iloc[0, 0]), 150000)

    def test_rejects_structural_errors(self):
        for content in [b'', b'a,b\n', b'a,b\n1,2,3\n', b'a,b\n1\n',
                        b'a,a\n1,2\n', b'a,\n1,2\n', b'a\n"unfinished', b'a\n\x00\n']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                load_csv(content)


class QualityTests(unittest.TestCase):
    def test_missing_is_not_invalid(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'email': ['a@b.com', '', ' N/A ', None]}))
        self.assertEqual([(i['check'], i['count']) for i in result['issues']], [('missing', 3)])

    def test_numeric_inference_ignores_missing(self):
        self.assertEqual(infer_column_type(pd.Series(['1', '', '2', 'NA', None], name='metric')), 'numeric')

    def test_malformed_numeric_and_nonfinite(self):
        df = pd.DataFrame({'metric': ['1'] * 18 + ['bad', 'inf']})
        result = run_pipeline_from_dataframe(df)
        invalid = next(i for i in result['issues'] if i['check'] == 'invalid_numeric')
        self.assertEqual(invalid['row_indices'], [18, 19])
        json.dumps(result, allow_nan=False)

    def test_known_phone_and_date_with_invalid_majority(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'phone': ['bad', '123'], 'start_date': ['bad', '2024-02-30']}))
        self.assertNotEqual(result['column_types']['phone'], 'phone')
        self.assertNotEqual(result['column_types']['start_date'], 'date')
        self.assertEqual({i['check'] for i in result['issues']}, {'header_conflict'})

    def test_mixed_date_formats_and_invalid_dates_are_separate(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'date': ['2024-01-01', '2024-01-02', '2024/01/03', 'bad']}))
        issues = {i['check']: i for i in result['issues']}
        self.assertEqual(issues['format']['row_indices'], [2])
        self.assertEqual(issues['invalid_date']['row_indices'], [3])

    def test_mixed_timezone_dates_do_not_crash(self):
        result = run_pipeline_from_dataframe(pd.DataFrame({'timestamp': ['2024-01-01T12:00:00+02:00', '2024-01-02T12:00:00Z']}))
        self.assertEqual(result['issues'], [])

    def test_bounds_small_and_all_negative(self):
        for column, expected in [('temperature', 0), ('balance', 0), ('Age', 0)]:
            self.assertEqual(check_numeric_bounds(pd.DataFrame({column: [-1, -2]}), column)['count'], expected)

    def test_text_without_schema(self):
        df = pd.DataFrame({'note': ['M', '李明', 'éàü', 'x' * 200, 'Hello!!!', 'bad\x01text']})
        self.assertEqual(check_text_quality(df, 'note')['row_indices'], [5])

    def test_category_false_positives_and_typos(self):
        self.assertEqual(check_categorical_format(pd.DataFrame({'v': ['C++', 'C', '李', '王']}), 'v')['count'], 0)
        self.assertEqual(check_categorical_format(pd.DataFrame({'v': ['Open', 'Open', ' open ']}), 'v')['row_indices'], [2])
        for value, count in [('Rare', 0), ('Actve', 1)]:
            df = pd.DataFrame({'v': ['Active'] * 99 + [value]})
            self.assertEqual(check_categorical_consistency(df, 'v')['count'], count)

    def test_currency_grouping_and_sign(self):
        df = pd.DataFrame({'price': ['-R10.50', '$1,000.00', '12,,34', '1,2']})
        self.assertEqual(check_currency_validity(df, 'price')['row_indices'], [2, 3])

    def test_duplicates_are_excess_rows(self):
        self.assertEqual(check_duplicate_rows(pd.DataFrame({'v': ['a', 'a', 'a', 'b']}))['row_indices'], [1, 2])

    def test_iqr_constant_majority_and_identifiers(self):
        df = pd.DataFrame({'v': [10] * 19 + [1000]})
        self.assertEqual(check_numeric_outliers(df, 'v')['row_indices'], [19])
        self.assertEqual(run_anomaly_detection(df, {'v': {'type': 'numeric', 'role': 'identifier'}}), [])
        self.assertEqual(check_numeric_outliers(df.iloc[:19], 'v')['count'], 0)

    def test_no_false_currency_evidence(self):
        profile = infer_column_profile(pd.Series(['Alice', 'Bob'], name='name'), 'name')
        self.assertNotIn('currency', profile['semantic_tags'])

    def test_inference_uses_more_than_first_rows(self):
        values = ['a@b.com'] * 50 + ['ordinary text'] * 950
        self.assertNotEqual(infer_column_type(pd.Series(values)), 'email')

    def test_pipeline_reindexes_and_does_not_mutate(self):
        df = pd.DataFrame({'email': ['bad', 'good@example.com']}, index=['a', 'b'])
        result = run_pipeline_from_dataframe(df)
        self.assertEqual(result['issues'][0]['row_indices'], [0])
        self.assertEqual(df.index.tolist(), ['a', 'b'])

    def test_empty_and_duplicate_columns_rejected(self):
        for df in [pd.DataFrame(), pd.DataFrame([[1, 2]], columns=['a', 'a'])]:
            with self.assertRaises(ValueError):
                run_pipeline_from_dataframe(df)

    def test_score_zero_counts_and_duplicate_scale(self):
        df = pd.DataFrame({'a': range(100)})
        self.assertEqual(calculate_quality_score([{'check': 'missing', 'count': 0}], df)['score'], 100)
        for count in [10, 1000]:
            issue = {'check': 'duplicate', 'count': count, 'pct': 10}
            self.assertEqual(calculate_quality_score([issue], df)['score'], 85)
            self.assertEqual(translate_issue(issue)['legacy']['severity'], 'high')

    def test_grades_and_score_clamp(self):
        df = pd.DataFrame({'a': [1]})
        for count, score, grade in [(0, 100, 'A'), (4, 90, 'A'), (10, 75, 'B'), (16, 60, 'C'), (24, 40, 'D'), (25, 37.5, 'F'), (50, 0, 'F')]:
            issues = [{'check': 'format', 'column': str(i), 'count': 1, 'pct': 1} for i in range(count)]
            result = calculate_quality_score(issues, df)
            self.assertEqual((result['score'], result['grade']), (score, grade))


class BoundaryTests(unittest.TestCase):
    def test_size_limit_and_close(self):
        file = UploadFile(filename='test.csv', file=io.BytesIO(b'a\n12345'))
        with patch.object(main, 'MAX_SIZE', 4), self.assertRaises(HTTPException) as error:
            asyncio.run(main.assess_csv(file))
        self.assertEqual(error.exception.status_code, 400)
        self.assertTrue(file.file.closed)

    def test_internal_errors_are_not_exposed(self):
        file = UploadFile(filename='test.csv', file=io.BytesIO(b'a\n1'))
        with patch.object(main, '_assess_contents', side_effect=RuntimeError('private detail')), self.assertLogs('main', level='ERROR'), self.assertRaises(HTTPException) as error:
            asyncio.run(main.assess_csv(file))
        self.assertEqual(error.exception.status_code, 500)
        self.assertNotIn('private', error.exception.detail)


class LiveAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            cls.port = sock.getsockname()[1]
        cls.log = tempfile.TemporaryFile()
        cls.process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'main:app', '--app-dir', str(ROOT), '--host', '127.0.0.1', '--port', str(cls.port)],
            cwd=tempfile.gettempdir(), stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.cleanup)
        for _ in range(100):
            try:
                with urlopen(f'http://127.0.0.1:{cls.port}/health', timeout=1):
                    return
            except OSError:
                if cls.process.poll() is not None:
                    break
                time.sleep(0.1)
        cls.log.seek(0)
        raise RuntimeError(cls.log.read().decode(errors='replace'))

    @classmethod
    def cleanup(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.log.close()

    def request(self, path, data=None, headers=None, method=None):
        req = Request(f'http://127.0.0.1:{self.port}{path}', data=data, headers=headers or {}, method=method)
        try:
            response = urlopen(req, timeout=30)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, response.headers, json.loads(body) if body and body.startswith(b'{') else body

    def upload(self, contents, filename='data.csv'):
        body = (f'--boundary\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: text/csv\r\n\r\n'.encode() + contents + b'\r\n--boundary--\r\n')
        return self.request('/assess', body, {'Content-Type': 'multipart/form-data; boundary=boundary', 'Origin': 'http://localhost:5173'})

    def test_status_and_sample_from_other_working_directory(self):
        for path, method in [('/', 'GET'), ('/health', 'GET'), ('/assess-with-sample', 'POST')]:
            with self.subTest(path=path):
                status, _, data = self.request(path, method=method)
                self.assertEqual(status, 200)
                if path == '/assess-with-sample':
                    self.assertEqual(data['total_rows'], 10)

    def test_upload_frontend_contract_and_cors(self):
        status, headers, data = self.upload(b'id,email\n001,good@example.com\n002,bad\n003,\n', 'DATA.CSV')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'http://localhost:5173')
        self.assertEqual(data['filename'], 'DATA.CSV')
        self.assertEqual((data['total_rows'], data['total_columns']), (3, 2))
        self.assertIsInstance(data['score'], (int, float))
        for issue in data['translated_issues']:
            for key in ['title', 'description', 'severity']:
                self.assertTrue(issue['issue_to_review'][key])
            self.assertTrue(issue['recommendation']['action'])
        self.assertEqual(len(data['issues']), len(data['translated_issues']))
        json.dumps(data, allow_nan=False)

    def test_upload_errors(self):
        for content, filename in [(b'', 'empty.csv'), (b'a,b\n1,2,3', 'broken.csv'), (b'a\n1', 'data.txt')]:
            with self.subTest(filename=filename):
                status, _, data = self.upload(content, filename)
                self.assertEqual(status, 400)
                self.assertIsInstance(data['detail'], str)
        self.assertEqual(self.request('/assess', b'')[0], 422)

    def test_cors_preflight(self):
        for origin in ['http://localhost:5173', 'http://localhost:5174', 'http://127.0.0.1:5173', 'http://127.0.0.1:5174']:
            status, headers, _ = self.request('/assess', headers={'Origin': origin, 'Access-Control-Request-Method': 'POST'}, method='OPTIONS')
            self.assertEqual(status, 200)
            self.assertEqual(headers['Access-Control-Allow-Origin'], origin)


if __name__ == '__main__':
    unittest.main()
