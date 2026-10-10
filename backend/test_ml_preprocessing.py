"""Phase 3 invariants; no classifiers are instantiated or trained."""
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import numpy as np
import pandas as pd
from scipy import sparse
from domains.network import NetworkSchema, FieldRule
from preprocessing import FieldPolicy, PreprocessingPolicy
from pipeline import run_pipeline_from_dataframe
from ml.preprocessing import NetworkMLPreprocessor, prepare_supervised_dataset, MISSING_CATEGORY
from ml.configs import unsw_nb15_ml_config
from ml.prepare import prepare_official_split


def alternate_schema():
    return NetworkSchema(name='alternate', fields={
        'elapsed': FieldRule('nonnegative'), 'octets': FieldRule('count'),
        'wire': FieldRule('protocol', case_sensitive=False), 'mode': FieldRule('category'),
        'truth': FieldRule('binary')}, target_fields=('truth',), leakage_fields=('attack_kind',), identifier_fields=('flow_id',))


def policy():
    return PreprocessingPolicy(fields={'wire': FieldPolicy(trim=True, case='lower', reason='Explicit case-insensitive protocol.'),
                                      'mode': FieldPolicy(trim=True, reason='Explicit exporter whitespace convention.')})


def training():
    return pd.DataFrame({'elapsed': ['1', '', '5', '999999'], 'octets': ['10', '20', '30', '40'],
        'wire': [' TCP ', 'tcp', 'udp', 'tcp'], 'mode': ['A', '', 'a', 'A'],
        'truth': ['0', '1', '0', '1'], 'attack_kind': ['Normal', 'Attack', 'Normal', 'Attack'],
        'flow_id': ['1', '2', '3', '4']})


class MLPreprocessingTests(unittest.TestCase):
    def preprocessor(self):
        return NetworkMLPreprocessor(alternate_schema(), policy())

    def test_training_median_missing_categories_and_extremes(self):
        frame = training()
        original = frame.copy(deep=True)
        processor = self.preprocessor()
        X = processor.fit_transform(frame)
        self.assertTrue(sparse.isspmatrix_csr(X))
        self.assertEqual(processor.medians_['elapsed'], 5)
        self.assertEqual(X[1, 0], 5)
        self.assertEqual(X[3, 0], 999999)
        self.assertEqual(processor.last_audit_['missing_handled']['elapsed'], 1)
        self.assertEqual(processor.last_audit_['missing_handled']['mode'], 1)
        missing_index = processor.feature_names_out_.index('mode_' + MISSING_CATEGORY)
        self.assertEqual(X[1, missing_index], 1)
        pd.testing.assert_frame_equal(frame, original)

    def test_test_data_never_changes_training_state(self):
        processor = self.preprocessor().fit(training())
        medians = dict(processor.medians_)
        categories = [v.copy() for v in processor.encoder_.categories_]
        test = training().iloc[:2].copy()
        test['elapsed'] = ['', '1000000000']
        test['wire'] = ['newproto', 'tcp']
        X = processor.transform(test)
        self.assertEqual(X[0, 0], 5)
        self.assertEqual(processor.medians_, medians)
        for before, after in zip(categories, processor.encoder_.categories_):
            np.testing.assert_array_equal(before, after)
        self.assertEqual(processor.last_audit_['unseen_categories']['wire'], 1)
        self.assertNotIn('wire_newproto', processor.feature_names_out_)
        self.assertEqual(X.shape[1], len(processor.feature_names_out_))

    def test_protected_values_cannot_influence_predictors(self):
        frame = training()
        changed = frame.copy()
        changed['truth'] = ['100', '', '-1', 'bad']
        changed['attack_kind'] = ['secret'] * 4
        changed['flow_id'] = ['999'] * 4
        p1, p2 = self.preprocessor(), self.preprocessor()
        np.testing.assert_array_equal(p1.fit_transform(frame).toarray(), p2.fit_transform(changed).toarray())
        self.assertEqual(p1.feature_columns_, ['elapsed', 'octets', 'wire', 'mode'])
        self.assertEqual(p1.medians_, p2.medians_)

    def test_unlabelled_future_upload_and_reordered_columns(self):
        processor = self.preprocessor().fit(training())
        future = training()[['mode', 'wire', 'octets', 'elapsed']]
        np.testing.assert_array_equal(processor.transform(future).toarray(), processor.transform(training()).toarray())
        with self.assertRaisesRegex(ValueError, 'absent'):
            processor.transform(future.drop(columns='elapsed'))

    def test_target_missing_invalid_exclusions_and_no_imputation(self):
        frame = training()
        frame['truth'] = ['0', '', '2', '1']
        original = frame.copy()
        cleaned, labels, audit = prepare_supervised_dataset(frame, alternate_schema(), 'truth', policy(), 'training')
        self.assertEqual(labels.tolist(), [0, 1])
        self.assertEqual(audit['target_validation']['missing'], 1)
        self.assertEqual(audit['target_validation']['invalid'], 1)
        self.assertEqual(audit['target_validation']['imputed'], 0)
        self.assertEqual(audit['retained_source_rows'], [0, 3])
        self.assertEqual(cleaned['flow_id'].tolist(), ['1', '4'])
        pd.testing.assert_frame_equal(frame, original)
        # Excluded target rows do not contribute to training median/category sets.
        processor = self.preprocessor().fit(cleaned)
        self.assertEqual(processor.medians_['octets'], 25)
        self.assertNotIn('udp', processor.encoder_.categories_[0])

    def test_duplicate_detection_and_explicit_raw_exact_removal(self):
        frame = pd.concat([training(), training().iloc[[0]]], ignore_index=True)
        cleaned, _, audit = prepare_supervised_dataset(frame, alternate_schema(), 'truth', policy())
        self.assertEqual(len(cleaned), 5)
        self.assertEqual(audit['duplicates_detected'], 1)
        self.assertEqual(audit['duplicates_removed'], 0)
        remove = PreprocessingPolicy(duplicate_policy='remove_exact', allow_duplicate_removal=True, duplicate_reason='Test explicit exporter duplicate decision.')
        cleaned, _, audit = prepare_supervised_dataset(frame, alternate_schema(), 'truth', remove, 'testing')
        self.assertEqual(len(cleaned), 4)
        self.assertEqual(audit['dataset'], 'testing')
        self.assertEqual(audit['duplicates_removed'], 1)
        with self.assertRaises(ValueError):
            PreprocessingPolicy(duplicate_policy='remove_exact')
        with self.assertRaises(ValueError):
            NetworkMLPreprocessor(alternate_schema(), remove)

    def test_case_sensitive_categories_are_preserved(self):
        processor = self.preprocessor().fit(training())
        self.assertTrue({'A', 'a'} <= set(processor.encoder_.categories_[1]))
        self.assertEqual(set(processor.encoder_.categories_[0]), {'tcp', 'udp', MISSING_CATEGORY})
        with self.assertRaisesRegex(ValueError, 'Case carries meaning'):
            NetworkMLPreprocessor(alternate_schema(), PreprocessingPolicy(fields={'mode': FieldPolicy(case='lower', reason='Unsafe case change.')})).fit(training())

    def test_protected_normalization_rejected(self):
        with self.assertRaisesRegex(ValueError, 'protected'):
            NetworkMLPreprocessor(alternate_schema(), PreprocessingPolicy(fields={'truth': FieldPolicy(trim=True, reason='Unsafe target change.')}))

    def test_all_missing_training_numeric_is_not_guessed(self):
        frame = training()
        frame['elapsed'] = ''
        with self.assertRaisesRegex(ValueError, 'all-missing'):
            self.preprocessor().fit(frame)

    def test_invalid_numeric_or_nonfinite_not_imputed(self):
        for value in ['bad', 'Infinity', '-1']:
            frame = training()
            frame.loc[0, 'elapsed'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.preprocessor().fit(frame)

    def test_finite_extreme_median_is_preserved_without_overflow(self):
        frame = training().iloc[:3].copy()
        frame['elapsed'] = ['1e308', '1e308', '']
        with np.errstate(over='ignore'):
            processor = self.preprocessor()
            X = processor.fit_transform(frame)
        self.assertEqual(processor.medians_['elapsed'], 1e308)
        np.testing.assert_array_equal(X[:, 0].toarray().ravel(), [1e308, 1e308, 1e308])

    def test_missing_sentinel_collision_rejected(self):
        frame = training()
        frame.loc[0, 'mode'] = MISSING_CATEGORY
        with self.assertRaisesRegex(ValueError, 'collides'):
            self.preprocessor().fit(frame)

    def test_schema_is_explicit_and_fitted_object_reusable_in_memory(self):
        frame = training()
        frame['unmapped'] = 'x'
        with self.assertRaisesRegex(ValueError, 'explicit schema'):
            self.preprocessor().fit(frame)
        processor = self.preprocessor()
        with self.assertRaisesRegex(ValueError, 'Fit'):
            processor.transform(training())
        processor.fit(training())
        restored = pickle.loads(pickle.dumps(processor))  # Round trip only in memory.
        np.testing.assert_array_equal(processor.transform(training()).toarray(), restored.transform(training()).toarray())

    def test_generic_quality_engine_still_reports_missing_outliers(self):
        frame = pd.DataFrame({'measurement': ['1'] * 20 + ['999999', '']})
        quality = run_pipeline_from_dataframe(frame)
        self.assertFalse(quality['domain_validation']['enabled'])
        self.assertTrue({'missing', 'outlier'} <= {i['check'] for i in quality['issues']})
        self.assertEqual(frame.iloc[20, 0], '999999')

    def test_unsw_configuration_is_separate(self):
        schema, _, processor = unsw_nb15_ml_config()
        self.assertEqual(schema.protected_fields, {'id', 'label', 'attack_cat'})
        self.assertFalse(processor.fitted_)

    def test_official_split_workflow_preserves_files_and_aligns_labels(self):
        train = pd.DataFrame({'id': ['1', '2', '3'], 'dur': ['1', '', '5'],
            'proto': ['tcp', 'udp', 'tcp'], 'service': ['-', 'http', '-'],
            'state': ['FIN', 'CON', 'FIN'], 'label': ['0', '1', ''],
            'attack_cat': ['Normal', 'Attack', 'Unknown']})
        test = train.iloc[[0]].copy()
        test['dur'] = ''
        test['proto'] = 'newproto'
        with TemporaryDirectory() as directory:
            training_path, testing_path = Path(directory) / 'training.csv', Path(directory) / 'testing.csv'
            train.to_csv(training_path, index=False)
            test.to_csv(testing_path, index=False)
            originals = [training_path.read_bytes(), testing_path.read_bytes()]
            prepared = prepare_official_split(training_path, testing_path)
            self.assertEqual(prepared.X_train.shape[0], 2)
            self.assertEqual(prepared.y_train.tolist(), [0, 1])
            self.assertEqual(prepared.y_test.tolist(), [0])
            self.assertEqual(prepared.X_test[0, 0], 1)
            self.assertEqual(prepared.X_test.shape[1], prepared.X_train.shape[1])
            self.assertEqual(prepared.audit['datasets'][0]['target_validation']['excluded'], 1)
            self.assertEqual(prepared.audit['datasets'][1]['ml_preprocessing']['unseen_categories']['proto'], 1)
            self.assertEqual([training_path.read_bytes(), testing_path.read_bytes()], originals)
            self.assertNotIn('label', prepared.preprocessor.feature_names_out_)
            self.assertNotIn('attack_cat', prepared.preprocessor.feature_names_out_)


if __name__ == '__main__':
    unittest.main()
