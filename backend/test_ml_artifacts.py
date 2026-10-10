"""Small-fixture persistence tests; never train the official model here."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from ml.artifacts import save_artifacts, load_artifacts, verify_reload
from ml.models import decision_tree, random_forest
from ml.training import training_matrix
from test_ml_training import prepared_fixture


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)
        prepared = prepared_fixture()
        self.preprocessor = prepared.preprocessor
        self.model = decision_tree().fit(training_matrix(prepared.X_train), prepared.y_train)
        self.sample = pd.DataFrame({'elapsed': ['1', '', '7'], 'wire': ['tcp', 'udp', 'tcp']})
        self.save()

    def save(self):
        return save_artifacts(self.path, self.model, self.preprocessor, 'decision_tree', 60, {'fixture': True})

    def change_metadata(self, update):
        path = self.path / 'model_metadata.json'
        metadata = json.loads(path.read_text())
        update(metadata)
        path.write_text(json.dumps(metadata))

    def test_files_created(self):
        self.assertEqual({p.name for p in self.path.iterdir()}, {'intrusion_model.joblib', 'preprocessor.joblib', 'model_metadata.json'})

    def test_forest_probabilities_exact_with_verification_backend(self):
        prepared = prepared_fixture()
        model = random_forest().fit(training_matrix(prepared.X_train), prepared.y_train)
        save_artifacts(self.path, model, prepared.preprocessor, 'random_forest', 60, {})
        result = verify_reload(self.path, model, prepared.preprocessor, self.sample)
        self.assertTrue(result['probabilities_identical'])
        self.assertEqual(model.n_jobs, 2)
        self.assertEqual(load_artifacts(self.path)[0].n_jobs, 2)

    def test_roundtrip_without_fitting_or_target(self):
        with patch.object(type(self.preprocessor), 'fit', side_effect=AssertionError('no refitting')), patch.object(type(self.model), 'fit', side_effect=AssertionError('no retraining')):
            verification = verify_reload(self.path, self.model, self.preprocessor, self.sample)
        self.assertTrue(verification['transform_identical'])
        self.assertTrue(verification['predictions_identical'])
        self.assertTrue(verification['probabilities_identical'])

    def test_feature_order_categories_medians_and_schema(self):
        _, loaded, metadata = load_artifacts(self.path)
        np.testing.assert_array_equal(loaded.get_feature_names_out(), self.preprocessor.get_feature_names_out())
        self.assertEqual(loaded.medians_, self.preprocessor.medians_)
        self.assertEqual(loaded.schema.to_dict(), self.preprocessor.schema.to_dict())
        self.assertEqual(metadata['features']['required_features'], ['elapsed', 'wire'])
        for first, second in zip(loaded.encoder_.categories_, self.preprocessor.encoder_.categories_):
            np.testing.assert_array_equal(first, second)

    def test_protected_columns_do_not_affect_predictions(self):
        model, preprocessor, _ = load_artifacts(self.path)
        protected = self.sample.assign(truth=1, flow_id='ignored', attack_type='ignored')
        np.testing.assert_array_equal(model.predict(preprocessor.transform(self.sample)), model.predict(preprocessor.transform(protected)))

    def test_missing_input_feature_rejected(self):
        _, preprocessor, _ = load_artifacts(self.path)
        with self.assertRaisesRegex(ValueError, 'absent'):
            preprocessor.transform(self.sample.drop(columns='wire'))

    def test_missing_model(self):
        (self.path / 'intrusion_model.joblib').unlink()
        with self.assertRaises(FileNotFoundError):
            load_artifacts(self.path)

    def test_missing_preprocessor(self):
        (self.path / 'preprocessor.joblib').unlink()
        with self.assertRaises(FileNotFoundError):
            load_artifacts(self.path)

    def test_incompatible_version(self):
        self.change_metadata(lambda m: m.update(artifact_version=999))
        with self.assertRaisesRegex(ValueError, 'version'):
            load_artifacts(self.path)

    def test_missing_feature_metadata(self):
        self.change_metadata(lambda m: m['features'].pop('required_features'))
        with self.assertRaisesRegex(ValueError, 'feature information'):
            load_artifacts(self.path)

    def test_changed_encoded_order(self):
        self.change_metadata(lambda m: m['features']['encoded_feature_order'].reverse())
        with self.assertRaisesRegex(ValueError, 'preprocessing'):
            load_artifacts(self.path)

    def test_checksum_checked_before_loading(self):
        with (self.path / 'intrusion_model.joblib').open('ab') as handle:
            handle.write(b'changed')
        with patch('ml.artifacts.joblib.load', side_effect=AssertionError('must not deserialize')):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_artifacts(self.path)

    def test_sklearn_version_checked(self):
        self.change_metadata(lambda m: m['environment'].update(sklearn='different'))
        with self.assertRaisesRegex(ValueError, 'scikit-learn'):
            load_artifacts(self.path)


if __name__ == '__main__':
    unittest.main()
