# Stage 4 Presentation Summary

Use this outline with the [final academic documentation](README.md). Tables and exact evidence remain in that document and the linked phase reports, avoiding a second full results narrative.

## 1. Problem and Aim

Network intrusion classifiers can produce confident-looking predictions from incomplete or incompatible inputs. DataQualiQ integrates supervised traffic classification with input-integrity explanations and human security decision support. State the research question: **How does data quality affect the reliability of machine-learning-based network intrusion detection?**

## 2. Computer Science Architecture

Show the architecture diagram in [section 4](README.md#4-final-architecture): network CSV → FastAPI quality assessment and validation → saved preprocessing/imputation/one-hot encoding → Random Forest → predictions and probabilities, with a separate input-reliability layer → recommendations → React Dashboard, detailed pages and PDF. Highlight reusable model serving, source-row linking, API integration and bounded responses. This is uploaded-record analysis, not live packet protection.

## 3. Algorithms and Model Selection

Explain Gini-based Decision Tree as the baseline and the saved 100-tree Random Forest as the selected classifier. Numeric imputation uses training medians; categorical encoding reuses the fitted vocabulary. IQR supplies analytical review evidence and is not the intrusion classifier. Use the [verified comparison table](README.md#8-model-comparison): the recall-weighted policy selected Random Forest for 1,203 fewer missed attacks, accepting 1,706 additional false alarms. Do not claim it won accuracy, precision or F1.

## 4. Official Test Evaluation

Label the results **Official test evaluation**, with Malicious as the positive class. Random Forest achieved 86.4111% accuracy, 80.6874% precision, 99.0206% recall and 88.9188% F1, with 444 missed attacks and 10,744 false alarms. Explain the confusion matrix using [section 9](README.md#9-final-model-evaluation--official-test-evaluation). Acknowledge that this split participated in model selection and is not a fresh independent estimate.

## 5. System Demonstration and Verification

Demonstrate Upload, Dashboard, Data Quality, Intrusion Detection, Results and Reports using the [screenshot checklist](README.md#16-report-and-presentation-screenshots). Keep probability and reliability visibly separate, and show a specific Review/rejection reason. Present recorded Phase 15 evidence: **28/28 end-to-end scenarios**, **274 backend tests**, **49 frontend tests**, lint and build passed. The full 82,332-row file succeeded, but took about 239.5 seconds. PDF previews and filters cover the returned page; no traffic is automatically blocked.

## 6. Experiment and Research Answer

Use the [Phase 16 comparison](README.md#10-final-data-quality-experiment) and its accuracy/recall figures. The fixed model was tested at 5%, 10% and 20% numeric missingness, categorical missingness and supported formatting changes. Categorical missingness affected performance most. Missingness reduced accuracy, precision and F1 while slightly increasing recall and reducing false negatives. Normalized formatting produced identical predictions. Conclude that the effect is mechanism-dependent, rather than asserting poor data always increases missed attacks.

## 7. Contribution, Limits and Conclusion

The contribution is an integrated ML-based cybersecurity prototype: reusable preprocessing/inference, backend model serving, frontend decision support, input-quality explanations and controlled evaluation. State limits: UNSW-NB15 scope, required schema, uncalibrated probability, input integrity rather than guaranteed correctness, slow large-file processing, refresh loss, page-local evidence, single-seed experimental mechanisms and no uncertainty intervals. Close with the verified achievement, without claiming production readiness or universal accuracy. Future independent-data replication and reusable analysis IDs are proposals, not completed features.
