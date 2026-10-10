"""Small-fixture checks only; full official experiment is an explicit offline run."""
from pathlib import Path
import json
import tempfile
import unittest
import numpy as np
import pandas as pd
from csv_loading import load_csv
from experiments.data_quality_experiment import degrade, metrics, CapturingPredictor, GROUPS, digest
from experiments.merge_quality_experiment import merge

class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({'dur': ['1'] * 30, 'rate': ['2'] * 30, 'sbytes': ['10'] * 30, 'proto': ['tcp'] * 30, 'service': ['http'] * 30, 'state': ['FIN'] * 30, 'label': [0, 1] * 15, 'attack_cat': ['Normal', 'Attack'] * 15, 'id': list(range(30))})
    def test_reproducible_and_nested(self):
        for kind in GROUPS:
            first, audit = degrade(self.frame, kind, .1)
            second, repeated = degrade(self.frame, kind, .1)
            pd.testing.assert_frame_equal(first, second); self.assertEqual(audit, repeated)
            mild, _ = degrade(self.frame, kind, .05)
            moderate, _ = degrade(self.frame, kind, .1)
            severe, _ = degrade(self.frame, kind, .2)
            names = list(GROUPS[kind])
            low = (mild[names] != self.frame[names]).to_numpy()
            mid = (moderate[names] != self.frame[names]).to_numpy()
            high = (severe[names] != self.frame[names]).to_numpy()
            self.assertTrue(np.all(~low | mid)); self.assertTrue(np.all(~mid | high))
            self.assertEqual(int(high.sum()), int(30 * 3 * .2))
    def test_original_truth_and_nonpredictive_fields_unchanged(self):
        before = self.frame.copy(deep=True)
        for kind in GROUPS:
            degraded, _ = degrade(self.frame, kind, .2)
            pd.testing.assert_frame_equal(degraded[['label', 'attack_cat', 'id']], before[['label', 'attack_cat', 'id']])
        pd.testing.assert_frame_equal(self.frame, before)
    def test_selection_is_label_blind(self):
        alternate = self.frame.assign(label=1-self.frame.label, attack_cat='changed truth')
        for kind in GROUPS:
            first, a = degrade(self.frame, kind, .2)
            second, b = degrade(alternate, kind, .2)
            self.assertEqual(a, b)
            pd.testing.assert_frame_equal(first[list(GROUPS[kind])], second[list(GROUPS[kind])])
    def test_safe_representation_respects_case(self):
        output, _ = degrade(self.frame, 'representation', 1)
        self.assertEqual(output.proto.iloc[0], '  TCP  ')
        self.assertEqual(output.service.iloc[0], '  http  ')
        self.assertEqual(output.state.iloc[0], '  FIN  ')
    def test_metrics_known_matrix(self):
        result = metrics([0,0,1,1], [0,1,0,1])
        self.assertEqual(result['confusion_matrix'], [[1,1],[1,1]])
        for key in ['accuracy','precision','recall','f1']: self.assertEqual(result[key], .5)
        self.assertEqual(result['false_positives'], 1); self.assertEqual(result['false_negatives'], 1)
        with self.assertRaises(ValueError): metrics([0,1], [1,-1])
    def test_nonpredictive_degradation_group_rejected(self):
        with self.assertRaises(ValueError): degrade(self.frame, 'numeric_missing', .1, predictive_features=['proto'])
    def test_merge_refuses_incomplete_or_mismatched_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            baseline = {'condition': 'baseline'}
            root = {'configuration': {'seed': 16042}, 'conditions': [baseline]}
            (output / 'experiment_results.json').write_text(json.dumps(root))
            for name in ['categorical', 'representation']:
                folder = output / 'workers' / name
                folder.mkdir(parents=True)
                (folder / 'experiment_results.json').write_text(json.dumps(dict(root, complete=False)))
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                merge(output)
            self.assertEqual(json.loads((output / 'experiment_results.json').read_text()), root)
            root['configuration']['seed'] = 1
            (output / 'workers' / 'categorical' / 'experiment_results.json').write_text(json.dumps(root))
            with self.assertRaisesRegex(ValueError, 'Configuration'):
                merge(output)
    def test_saved_inference_without_fitting_or_source_changes(self):
        root = Path(__file__).resolve().parents[1]
        paths = [root/'data/UNSW_NB15_testing-set.csv', root/'backend/models/intrusion_model.joblib', root/'backend/models/preprocessor.joblib', root/'backend/models/model_metadata.json']
        before = [digest(path) for path in paths]
        contents = b'\n'.join(paths[0].read_bytes().splitlines()[:21]) + b'\n'
        frame = load_csv(contents)
        predictor = CapturingPredictor(root/'backend/models')
        combined, predictions = predictor.evaluate(frame, 'small.csv')
        self.assertEqual(len(predictions), 20)
        self.assertEqual(combined['summary']['records_predicted'], 20)
        model, preprocessor, _ = predictor._load()
        matrix = preprocessor.transform(frame)
        np.testing.assert_array_equal(predictions, model.predict(matrix))
        for kind in GROUPS:
            degraded, _ = degrade(frame, kind, .2)
            _, result = predictor.evaluate(degraded, 'degraded.csv')
            self.assertTrue(np.isin(result, [0,1]).all())
        self.assertEqual([digest(path) for path in paths], before)

if __name__ == '__main__': unittest.main()
