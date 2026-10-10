"""Known confusion counts and small fitted fixtures; no full dataset evaluation."""
import json
import unittest
from unittest.mock import patch
import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator
from ml.evaluation import evaluate_predictions, evaluate_classifier, compare_models, overfitting_diagnostic, evaluate_prepared_split, main
from ml.training import train_prepared_split
from test_ml_training import prepared_fixture


class FixedClassifier(BaseEstimator):
    def __init__(self, predictions):
        self.predictions = predictions
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = 1

    def predict(self, X):
        return np.asarray(self.predictions)

    def fit(self, X, y):
        raise AssertionError('Evaluation must never fit')


class EvaluationTests(unittest.TestCase):
    def test_exact_counts_and_malicious_positive_metrics(self):
        result = evaluate_predictions([0, 0, 0, 1, 1, 1], [0, 0, 1, 0, 1, 1])
        self.assertEqual(result['confusion_matrix'], [[2, 1], [1, 2]])
        self.assertEqual(result['counts'], {'true_negatives': 2, 'false_positives': 1, 'false_negatives': 1, 'true_positives': 2})
        for key in ['accuracy', 'precision', 'recall', 'f1', 'f2']:
            self.assertAlmostEqual(result['metrics'][key], 2/3)
        self.assertEqual(result['positive_class'], 1)
        self.assertEqual(result['classification_report']['Malicious']['support'], 3)

    def test_asymmetric_false_positives_and_false_negatives_not_swapped(self):
        result = evaluate_predictions([0, 0, 0, 1, 1, 1], [1, 1, 0, 0, 1, 1])
        self.assertEqual(result['counts']['false_positives'], 2)
        self.assertEqual(result['counts']['false_negatives'], 1)
        self.assertAlmostEqual(result['metrics']['precision'], .5)
        self.assertAlmostEqual(result['metrics']['recall'], 2/3)

    def test_zero_division_single_class_and_fixed_matrix_order(self):
        result = evaluate_predictions([0, 1], [0, 0])
        self.assertEqual(result['metrics']['precision'], 0)
        self.assertEqual(result['metrics']['recall'], 0)
        self.assertEqual(result['metrics']['f1'], 0)
        self.assertEqual(result['counts']['false_negatives'], 1)
        self.assertEqual(evaluate_predictions([1, 1], [1, 1])['confusion_matrix'], [[0, 0], [0, 2]])
        json.dumps(result, allow_nan=False)

    def test_stable_output_contains_only_serializable_values(self):
        args = ([0, 1, 1], [0, 1, 0])
        self.assertEqual(evaluate_predictions(*args), evaluate_predictions(*args))
        json.dumps(evaluate_predictions(*args), allow_nan=False)

    def test_generic_classifier_is_evaluated_without_fit(self):
        model = FixedClassifier([0, 1, 0])
        with patch.object(model, 'fit', side_effect=AssertionError('No test fitting')):
            result = evaluate_classifier(model, sparse.csr_matrix([[0], [1], [2]]), [0, 1, 1])
        self.assertEqual(result['counts']['false_negatives'], 1)
        self.assertGreaterEqual(result['prediction_seconds'], 0)

    def test_invalid_vectors_and_row_alignment_rejected(self):
        for invalid in [[], [0, 2], [0, np.nan], [[0, 1]], ['0', '1']]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluate_predictions(invalid, invalid)
        with self.assertRaises(ValueError):
            evaluate_predictions([0, 1], [0])
        with self.assertRaises(ValueError):
            evaluate_classifier(FixedClassifier([0]), np.ones((2, 1)), [0])

    def test_accuracy_alone_does_not_choose_winner(self):
        truth = [0] * 8 + [1] * 2
        cautious = evaluate_predictions(truth, [0] * 10)  # 80% accuracy, misses all attacks.
        detector = evaluate_predictions(truth, [1, 1] + [0] * 6 + [1, 1])
        decision = compare_models({'cautious': cautious, 'detector': detector})
        self.assertEqual(decision['selected_model'], 'detector')

    def test_decision_tree_can_win_and_forest_is_not_forced(self):
        truth = [0, 0, 1, 1]
        tree = evaluate_predictions(truth, truth)
        forest = evaluate_predictions(truth, [0, 0, 1, 0])
        self.assertEqual(compare_models({'decision_tree': tree, 'random_forest': forest})['selected_model'], 'decision_tree')

    def test_precision_penalizes_all_attack_predictions(self):
        truth = [0] * 50 + [1] * 50
        noisy = evaluate_predictions(truth, [1] * 100)
        useful = evaluate_predictions(truth, [0] * 49 + [1] * 50 + [0])
        self.assertEqual(compare_models({'noisy': noisy, 'useful': useful})['selected_model'], 'useful')

    def test_recall_tradeoff_is_reported_without_claiming_better_f1(self):
        truth = [0] * 80 + [1] * 20
        baseline = evaluate_predictions(truth, [1] * 10 + [0] * 70 + [1] * 18 + [0] * 2)
        detector = evaluate_predictions(truth, [1] * 16 + [0] * 64 + [1] * 20)
        result = compare_models({'baseline': baseline, 'detector': detector})
        self.assertEqual(result['selected_model'], 'detector')
        changes = result['observed_tradeoffs']['baseline']
        self.assertEqual(changes['false_negatives_change'], -2)
        self.assertEqual(changes['false_positives_change'], 6)
        self.assertLess(changes['metric_changes']['f1'], 0)

    def test_similar_performance_prefers_simpler_model(self):
        same = evaluate_predictions([0, 1], [0, 1])
        result = compare_models({'random_forest': same, 'decision_tree': same}, {'decision_tree': 1, 'random_forest': 100})
        self.assertEqual(result['selected_model'], 'decision_tree')
        self.assertIn('complexity', result['reason'])

    def test_different_test_population_rejected(self):
        first = evaluate_predictions([0, 1], [0, 1])
        second = evaluate_predictions([1, 0], [1, 0])
        with self.assertRaisesRegex(ValueError, 'same target'):
            compare_models({'first': first, 'second': second})

    def test_training_gap_is_diagnostic_not_a_selection_metric(self):
        training = evaluate_predictions([0, 1, 1, 0], [0, 1, 1, 0])
        test = evaluate_predictions([0, 1, 1, 0], [0, 0, 1, 1])
        diagnostic = overfitting_diagnostic(training, test)
        self.assertTrue(diagnostic['possible_overfitting_or_distribution_shift'])
        self.assertEqual(diagnostic['accuracy_gap'], .5)

    def test_prepared_evaluation_reuses_same_test_data_without_fitting(self):
        prepared = prepared_fixture()
        prepared.X_test = prepared.X_train.copy()
        prepared.y_test = prepared.y_train.copy()
        prepared.audit = {'test_fixture': True}
        trained = train_prepared_split(prepared)
        original = prepared.X_test.copy()
        with patch.object(trained.decision_tree, 'fit', side_effect=AssertionError('No test fitting')), patch.object(trained.random_forest, 'fit', side_effect=AssertionError('No test fitting')), patch.object(prepared.preprocessor, 'fit', side_effect=AssertionError('No refitting')):
            report = evaluate_prepared_split(prepared, trained)
        self.assertEqual(report['models']['decision_tree']['target_digest'], report['models']['random_forest']['target_digest'])
        self.assertEqual((original != prepared.X_test).nnz, 0)
        json.dumps(report, allow_nan=False)

    def test_cli_saves_serializable_report(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        fixture = evaluate_predictions([0, 1], [0, 1])
        report = {'selection': {'selected_model': 'fixture'}, 'models': {'fixture': fixture}}
        with TemporaryDirectory() as directory:
            output = Path(directory) / 'evaluation.json'
            with patch('ml.evaluation.run_official_evaluation', return_value=report), patch('sys.argv', ['evaluation', '--output', str(output)]):
                main()
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), report)


if __name__ == '__main__':
    unittest.main()
