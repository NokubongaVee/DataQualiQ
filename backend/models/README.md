# Verified saved model bundle

- `intrusion_model.joblib`: selected Random Forest, trained using the official training population.
- `preprocessor.joblib`: training-fitted medians, one-hot encoder and feature/schema state.
- `model_metadata.json`: exact parameters, required/encoded feature order, label mapping, dependency versions, artifact checksums and saved official evaluation.

Use the pinned backend requirements with Python 3.13. Upload inference loads this trusted local bundle and reuses transform/predict/predict_proba; it does not retrain or extend categories. No model recreation is needed to run the application.

The loader verifies checksums, compatibility and feature consistency. Joblib deserialization is for trusted bundles only; hashes detect accidental mismatches, not malicious replacements. See [Phase 6 persistence](../../docs/phase6/README.md) and [Phase 5 evaluation](../../docs/phase5/README.md). Official test selection and probability limitations remain documented.
