"""Small Phase 3 fixtures exercise training without touching official test records."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.utils.validation import check_is_fitted
from domains.network import NetworkSchema, FieldRule
from ml.preprocessing import NetworkMLPreprocessor, prepare_supervised_dataset
from ml.training import train_models, train_prepared_split, training_matrix, main
from ml.models import decision_tree, random_forest


def prepared_fixture():
    schema = NetworkSchema(fields={'elapsed': FieldRule('nonnegative'), 'wire': FieldRule('protocol'), 'truth': FieldRule('binary')},
        target_fields=('truth',), leakage_fields=('attack_type',), identifier_fields=('flow_id',))
    frame = pd.DataFrame({'elapsed': [str(i % 20) if i != 3 else '' for i in range(60)],
        'wire': ['tcp' if i % 2 else 'udp' for i in range(60)],
        'truth': ['0' if i % 20 < 10 else '1' for i in range(60)],
        'attack_type': ['do not learn'] * 60, 'flow_id': [str(i) for i in range(60)]})
    cleaned, y, _ = prepare_supervised_dataset(frame, schema, 'truth')
    preprocessor = NetworkMLPreprocessor(schema)
    X = preprocessor.fit_transform(cleaned)
    return SimpleNamespace(X_train=X, y_train=y, preprocessor=preprocessor)


class TrainingTests(unittest.TestCase):
    def test_both_models_return_fitted_estimators_from_phase3(self):
        prepared = prepared_fixture()
        run = train_prepared_split(prepared)
        for estimator in [run.decision_tree, run.random_forest]:
            check_is_fitted(estimator)
            self.assertEqual(estimator.n_features_in_, prepared.X_train.shape[1])
            np.testing.assert_array_equal(estimator.classes_, [0, 1])
        self.assertEqual(run.summary['models']['random_forest']['number_of_trees'], 100)
        self.assertLessEqual(run.summary['models']['decision_tree']['tree_depth'], 16)
        self.assertIs(run.preprocessor, prepared.preprocessor)
        self.assertFalse(run.summary['evaluation_performed'])
        self.assertIsNone(run.summary['selected_model'])
        json.dumps(run.summary, allow_nan=False)

    def test_cli_writes_only_json_summary_with_native_integer_counts(self):
        run = train_prepared_split(prepared_fixture())
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'training.json'
            with patch('ml.training.run_official_training', return_value=run), patch('sys.argv', ['training', '--summary', str(output)]):
                main()
            saved = json.loads(output.read_text(encoding='utf-8'))
            self.assertIsInstance(saved['models']['decision_tree']['leaves'], int)
            self.assertIsInstance(saved['models']['decision_tree']['tree_depth'], int)
            self.assertEqual(list(Path(directory).iterdir()), [output])
            self.assertFalse(saved['model_artifacts_saved'])

    def test_fixed_seeds_reproduce_fitted_tree_structures(self):
        prepared = prepared_fixture()
        first, second = train_prepared_split(prepared), train_prepared_split(prepared)
        for left, right in [(first.decision_tree, second.decision_tree), *zip(first.random_forest.estimators_, second.random_forest.estimators_)]:
            np.testing.assert_array_equal(left.tree_.feature, right.tree_.feature)
            np.testing.assert_array_equal(left.tree_.threshold, right.tree_.threshold)
            np.testing.assert_array_equal(left.tree_.value, right.tree_.value)

    def test_training_never_accesses_testing_data_or_refits_preprocessing(self):
        fixture = prepared_fixture()
        class GuardedSplit:
            X_train, y_train, preprocessor = fixture.X_train, fixture.y_train, fixture.preprocessor
            @property
            def X_test(self):
                raise AssertionError('Official test features accessed')
            @property
            def y_test(self):
                raise AssertionError('Official test targets accessed')
        medians = deepcopy(fixture.preprocessor.medians_)
        categories = [category.copy() for category in fixture.preprocessor.encoder_.categories_]
        with patch.object(fixture.preprocessor, 'fit', side_effect=AssertionError('Refit forbidden')), patch.object(fixture.preprocessor, 'transform', side_effect=AssertionError('Reprocessing forbidden')):
            train_prepared_split(GuardedSplit())
        self.assertEqual(fixture.preprocessor.medians_, medians)
        for before, after in zip(categories, fixture.preprocessor.encoder_.categories_):
            np.testing.assert_array_equal(before, after)

    def test_sparse_training_never_densifies_or_modifies_input(self):
        fixture = prepared_fixture()
        original = fixture.X_train.copy()
        y = fixture.y_train.copy()
        with patch.object(sparse.csr_matrix, 'toarray', side_effect=AssertionError('Densification forbidden')), patch.object(sparse.csc_matrix, 'toarray', side_effect=AssertionError('Densification forbidden')):
            run = train_prepared_split(fixture)
        self.assertEqual(run.summary['resources']['fit_format'], 'csc')
        self.assertEqual(run.summary['resources']['fit_dtype'], 'float32')
        self.assertEqual((fixture.X_train != original).nnz, 0)
        pd.testing.assert_series_equal(fixture.y_train, y)

    def test_small_dense_input_is_supported_without_altering_it(self):
        fixture = prepared_fixture()
        dense = fixture.X_train.toarray()
        before = dense.copy()
        run = train_models(dense, fixture.y_train, fixture.preprocessor)
        check_is_fitted(run.decision_tree)
        np.testing.assert_array_equal(dense, before)
        self.assertEqual(run.summary['resources']['fit_format'], 'dense ndarray')

    def test_invalid_or_missing_targets_are_rejected(self):
        fixture = prepared_fixture()
        for bad in [2, -1, np.nan]:
            labels = fixture.y_train.to_numpy(dtype=float)
            labels[0] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'binary'):
                train_models(fixture.X_train, labels, fixture.preprocessor)
        with self.assertRaisesRegex(ValueError, 'Both'):
            train_models(fixture.X_train, np.zeros(len(fixture.y_train)), fixture.preprocessor)

    def test_target_alignment_and_feature_width_are_checked(self):
        fixture = prepared_fixture()
        with self.assertRaisesRegex(ValueError, 'aligned'):
            train_models(fixture.X_train, fixture.y_train.iloc[:-1], fixture.preprocessor)
        with self.assertRaisesRegex(ValueError, 'width'):
            train_models(fixture.X_train[:, :-1], fixture.y_train, fixture.preprocessor)

    def test_protected_predictors_are_rejected(self):
        fixture = prepared_fixture()
        fixture.preprocessor.feature_columns_.append('truth')
        with self.assertRaisesRegex(ValueError, 'Protected'):
            train_prepared_split(fixture)

    def test_nonfinite_and_float32_overflow_rejected_without_clipping(self):
        for value in [np.nan, np.inf, 1e100]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                training_matrix(sparse.csr_matrix([[value]]))
        for empty in [np.empty((0, 2)), np.empty((2, 0)), np.array([1, 2])]:
            with self.assertRaises(ValueError):
                training_matrix(empty)

    def test_simple_initial_parameters_do_not_weight_or_evaluate_classes(self):
        tree, forest = decision_tree(), random_forest()
        self.assertEqual(tree.random_state, 42)
        self.assertEqual(forest.random_state, 42)
        self.assertIsNone(tree.class_weight)
        self.assertIsNone(forest.class_weight)
        self.assertFalse(forest.oob_score)
        self.assertEqual(forest.n_jobs, 2)

    def test_unfitted_preprocessor_is_rejected(self):
        fixture = prepared_fixture()
        fixture.preprocessor.fitted_ = False
        with self.assertRaisesRegex(ValueError, 'training-fitted'):
            train_prepared_split(fixture)


if __name__ == '__main__':
    unittest.main()
