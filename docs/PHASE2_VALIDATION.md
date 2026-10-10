# DataQualiQ Phase 2: assessment, network validation and safe preprocessing

Scope: backend data quality only. No frontend changes, model training, train/test
split, encoders, scalers, model persistence or prediction API.

Machine-readable evidence: [validation.json](phase2/validation.json). This contains
per-file source hashes, baseline and configured results, inferred/configured types,
selected/skipped checks with reasons, every triggered finding with its audit
decision, schema warnings and preprocessing audits. Counts of finding occurrences
can overlap; they are not distinct erroneous rows.

## 1. Existing files inspected

`pipeline.py`, `csv_loading.py`, `value_utils.py`, `profiling.py`, `type_inference.py`,
`dataset_context.py`, `check_selection.py`, `generic_checks.py`, `validity_checks.py`,
`anomaly_detection.py`, `relationships.py`, `finding_evidence.py`,
`contextual_guidance.py`, `scoring.py`, `recommendation_policy.py`, `translator.py`,
`plain_language.py`, `main.py`, `requirements.txt`, and existing backend tests.
The existing customer, sales, HR, education, spectrometry and statistical CSV
fixtures were inspected/tested. Pre-existing user changes were retained.

## 2. Problems found

- IQR candidates had `review_only=True` but still reduced the legacy quality score.
  A skewed traffic distribution could therefore look like widespread bad data.
- Rare edit-distance category candidates used the legacy `invalid_categorical`
  name. They were uncertain spelling suggestions, not proven illegal values.
- Inferred representations cannot reliably establish network semantics when many
  values fail numeric parsing or when compact codes resemble identifiers/phones.
  In the supplied files, decimal durations were specifically inferred as phones:
  the old engine reported 16,113/8,305 false invalid-phone findings on `dur`.
  Numeric-dominant unnamed measurements now stay numeric. Explicit phone headers
  and supported nonnumeric phone representations remain available.
- No optional network schema, separate preprocessing contract, transformation
  audit or explicit leakage-field projection existed.
- Relationships could use targets to describe feature combinations. Configured
  targets/leakage fields must be excluded from feature relationship analysis.

## 3. Generic rules kept

Strict CSV structure/header/encoding checks, shared null-marker semantics,
missingness, exact duplicate detection, measured profiles, conservative inferred
types, parse/finiteness checks, category/numeric/date representation checks,
IQR detection, bounded relationships, evidence and contextual recommendations
remain. No source file is rewritten by assessment.

## 4. Generic rules modified and complete rule audit

| Rule family | Decision | Why |
|---|---|---|
| Missing values | KEEP | Observable under the documented null-marker policy; never automatically zero-filled. |
| Exact duplicate rows | KEEP | Count excess identical raw rows; provenance determines whether removal is justified. |
| Invalid numeric/email/phone/date/currency/text/percentage representations | KEEP | Generic parsing/structure checks; type inference and exporter semantics still limit interpretation. |
| Numeric parsing vs floating-point limits | MODIFY | Finite decimals are not malformed merely because float64 cannot represent them. Preserve precision-limited values; statistical summaries remain arithmetic-limited. |
| Phone inference from decimal measurements | MODIFY | Numeric-dominant unnamed fields stay numeric; punctuation/digit counts alone cannot establish a phone role. |
| Category/numeric/date representation consistency | KEEP | Candidates for source review; no unconditional normalization. |
| IQR outliers | MODIFY | Classified as analytical/security anomalies; retain values and remove the quality-error penalty. |
| Rare categorical spelling candidates | MODIFY | Quality review only, without error penalty or automatic correction. Legacy check name retained for compatibility. |
| Inferred header/key/date/pattern/dependency candidates | KEEP | Review evidence, never established business constraints. Pattern/dependency exceptions are analytical anomalies. |
| Explicit structural network constraints | DOMAIN-SPECIFIC | Only a supplied schema establishes these rules. |
| Generic category spelling/structure checks on schema-mapped fields | NOT APPLICABLE | Explicit domain rules supersede them, avoiding duplicate penalties and frequency-derived validity. |
| Feature checks/relationships involving declared targets or leakage fields | NOT APPLICABLE | They must not decide feature correctness. Targets may receive read-only explicitly configured validation. |
| Rules/files removed | REMOVE: none | Working detection/evidence functionality was retained. |

Every triggered finding has an individual KEEP/MODIFY/DOMAIN-SPECIFIC decision in
the JSON report. Selected and skipped checks explain applicability per field.
Scoring is now `quality_errors_weighted_penalty_v2`: analytical anomalies and
uncertain semantic/category candidates do not reduce it. Other legacy weights and
extent thresholds remain. Schema findings supply their own score weight rather
than adding network-specific bounds to the generic scorer. The score is still a
heuristic, not a percentage of correct data or model readiness.

## 5. Network-specific rules added

Finite numeric syntax; nonnegative semantically configured durations/measures;
nonnegative integral packet/byte counts; integral ports 0–65535; explicitly binary
indicators; IPv4/IPv6 syntax; categorical structure and optional explicit allowed
values; named protocol syntax or integral protocol numbers 0–255. Reserved/unusual
ports and rare protocol names are not automatically errors. No frequency-based
vocabulary or upper bounds on packet counts, rates or durations are learned.

The network bounds follow the [IANA port registry](https://www.iana.org/assignments/service-names-port-numbers)
and [IANA protocol-number registry](https://www.iana.org/assignments/protocol-numbers).
The initial protocol token rule was revised after full-file validation: registered
names can start with digits and contain `.`, `+` and `/`. The final rule accepts
that structure without hard-coding a dataset vocabulary. The regression fixtures
include `3PC`, `AX.25`, `TP++` and `A/N`, verified against the IANA registry.
Protocol spelling validation is structural; it does not establish that a name is
registered or that a captured protocol was correctly identified.

## 6. Configurable schemas and architecture

`NetworkSchema` maps arbitrary column names to `FieldRule` definitions. Schemas
declare targets, leakage fields, identifiers, required field presence, permitted
categories and case semantics; they serialize to/from JSON. Callers explicitly
supply a schema. Headers, filenames and distributions do not silently select the
UNSW configuration. File-only `/assess` requests remain generic; an optional JSON
`network_schema` multipart field enables domain validation.

Generic assessment → optional schema-driven validation → finding categories →
separate, explicitly invoked preprocessing → copied DataFrame plus audit.

UNSW names appear in `domains/network/configs.py`, not generic detectors.
`id`, `attack_cat` and `label` are protected and excluded by `feature_columns()`.
`label` is validated read-only as binary; it is never inferred, imputed or used to
decide feature validity. `is_ftp_login` is conservatively nonnegative rather than
blindly binary; exporter-specific semantics require verification. No exact list
of UNSW protocol, service, state or attack-category names is hard-coded.

## 7. New files

- `backend/domains/__init__.py`
- `backend/domains/network/__init__.py`, `schema.py`, `validators.py`, `configs.py`
- `backend/finding_categories.py`
- `backend/preprocessing/__init__.py`, `generic_preprocessor.py`, `network_preprocessor.py`
- `backend/test_phase2.py`
- `backend/phase2_baseline.py`, `phase2_validate.py`
- `docs/PHASE2_VALIDATION.md`
- `docs/phase2/baseline.json`, `validation.json`, `final_verification.json`
- `docs/phase2/fixtures/unsw_like_synthetic.csv`, `alternate_network.csv`

`baseline.json` was captured before changing the engine on the then-available
generic datasets and synthetic network fixture. The two full UNSW files arrived
later. Their baseline uses the original HEAD pipeline/scoring/type inference/numeric detector with
the existing generic detectors and no network schema; only the added category
review metadata differs in those detectors. The baseline capture script refuses
to overwrite historical evidence. The comparison runner is repeatable in this
repository and requires its Git history for legacy comparison.

## 8. Existing files modified in this phase

`backend/pipeline.py`, `check_selection.py`, `scoring.py`, `validity_checks.py`,
`value_utils.py`, `type_inference.py`, `main.py`, `README.md`, `test_backend.py`,
`test_recommendation_policy.py`, and `test_statistics_audit.py`.
Frozen statistical audit fixtures remain unchanged; tests still compare their
original measured evidence while independently asserting the intentional score
and category changes. Other pre-existing backend edits were not reverted.
No frontend source, tests, assets or configuration were modified in this phase.

## 9. Automatic preprocessing operations

The default is identity: retain all values/rows and detect duplicates only.
Explicit, reason-bearing policies can trim whitespace, normalize case only where
the configured meaning permits it, parse numbers losslessly, mark independently
invalid features as unknown, fill approved constants, reject invalid/missing
required rows, or remove exact duplicates with explicit policy permission and
provenance justification. Duplicate comparisons use raw rows, never rows made
equal by normalization. Source DataFrames/files remain intact.

Audits include column, operation/rule/category, affected-row count, source row
positions, reason, optional examples, skipped operations, excluded source rows,
output-to-source mapping, finding statuses and preserved anomalies. Examples are
opt-in and limited; inherited assessment evidence may still contain source values.
Lossy/overflowing conversion candidates remain raw with an audit reason, rather
than becoming false structural errors. No guessed targets, automatic zero-fill,
outlier removal/capping/replacement or winsorization is implemented.

## 10. Findings deliberately preserved

Unusual but structurally valid observations, rare/new protocol names, category
review candidates, default missing values, exact repeated flows by default, and
all protected fields. Lossless numeric casting preserves anomaly magnitude and
records that separately from literal spelling. If an explicitly permitted raw
duplicate or independently invalid row is excluded, the audit reports it rather
than claiming every original anomaly row was retained.

## 11. Generic compatibility tests

Tests cover customer CSVs, numeric-heavy data, categorical data, HR, sales,
education, spectrometry, missing markers, exact duplicates, representation
consistency, malformed CSVs, generic API uploads/CORS, unchanged source evidence
and meaningful score boundaries. Network validation is absent without a schema.

## 12. Alternate-network-schema tests

The same validators are tested with `protocol`, `duration_seconds`,
`packets_sent/received`, `bytes_sent/received` and renamed equivalents such as
`wire_kind`, `elapsed`, `outbound`, `inbound`, `octets_out/in`. Tests cover port
boundaries, IPs, fractional/negative counts, missing required schema columns,
unseen protocols, independent target protection, policy validation, audits,
duplicate indexes and actual multipart schema requests. No UNSW names are needed.

## 13. Full UNSW-NB15 validation

Both user-supplied CSVs were assessed in full independently; no train/test split
or preprocessing fit was performed. All 162 backend tests pass, including the
original regression suite, new policy tests and actual multipart API tests.

| Metric | Training file | Testing file |
|---|---:|---:|
| Rows | 175,341 | 82,332 |
| Columns | 45 | 45 |
| Missing values | 0 | 0 |
| Exact raw duplicate excess rows | 0 | 0 |
| Domain data-error occurrences | 0 | 0 |
| Representation inconsistency occurrences | 0 | 0 |
| Preserved IQR occurrences | 604,884 | 248,284 |
| Fields with IQR findings | 32 | 32 |
| Legacy invalid-phone false positives on duration | 16,113 | 8,305 |
| Final invalid-phone findings on duration | 0 | 0 |
| Legacy heuristic score | 0/100 | 0/100 |
| Phase 2 heuristic score | 100/100 | 100/100 |
| Automatic changes / rows excluded | 0 / 0 | 0 / 0 |
| Future predictive fields after declared exclusions | 42 | 42 |
| Schema warnings | 0 | 0 |

IQR occurrences overlap across fields, so their totals exceed the number of rows.
They are preserved analytical observations, not attack counts or incorrect-row
counts. The legacy IQR totals were 589,143/242,416; corrected duration typing adds
15,741/5,868 duration observations rather than hiding them as phone errors.
The first domain-validation draft also rejected four legitimate protocol spellings
on 400/128 records. That structural restriction was corrected using registry
semantics and general token syntax, not a list learned from UNSW frequencies.

No preprocessing was needed under the tested, conservative protocol-normalization
policy: all supplied protocol spellings were already canonical. Synthetic cases
demonstrate actual normalization and explicit invalid/missing-value handling.
The full-file audit confirms all source rows, protected fields and IQR candidates
were retained, with no guessed labels or fitted preprocessing parameters.
`id`, `attack_cat` and `label` remain in the copied supervised dataset but are
excluded from the future predictive-field projection.

A score of 100/100 means no penalized findings were produced under these selected
rules. It does not establish universal validity, calibrated reliability, absence
of attacks or readiness for model training. The initial legacy score of zero was
misleading because it treated many genuine statistical extremes as quality errors.
The [final verification](phase2/final_verification.json) separately checks the
current domain rules, generic duration inference, exact copied-DataFrame equality,
source hashes and predictive-field exclusions on both full files, and records
hashes of the final backend source modules.

The [official dataset description](https://research.unsw.edu.au/projects/unsw-nb15-dataset)
describes the two provided partitions. Local source hashes identify the exact
copies tested; they do not independently certify provenance against an official
checksum.

## 14. Remaining limitations

- No universal correctness or calibrated error/attack accuracy is claimed.
- Inferred types, role hints, null tokens, categorical similarity and IQR fences
  remain heuristic. Schema assumptions must match the actual exporter.
- The UNSW mapping does not validate every feature's full semantics. Some counters
  and protocol-specific fields need a verified data dictionary before stricter
  constraints; `sttl/dttl` are currently finite numeric fields, not bounded TTLs.
- Required field presence and missing-value policies are separate concerns.
- Generic `NA`/`null` markers can be legitimate domain codes. The current marker
  policy is documented and unchanged; callers must verify its applicability.
- Pair relationships remain bounded to 20,000 rows/24 columns. Profiling performs
  exact full-column counts but some representation evidence uses a 1,000-value
  sample. Full files are loaded in memory and validation is not streaming.
- Assessment JSON can contain many row references; the development report keeps
  exact counts and sampled positions instead of embedding every raw record.
- Schema configuration is explicit, not automatic network-dataset discovery.
- Schema-mapped categorical/protocol fields use domain structural validation, not
  inferred category spelling or dependency constraints. The generic relationship
  engine remains available; this layer does not claim comprehensive protocol-
  specific traffic semantics or cross-field consistency validation.
- Median/mode imputation, encoding and scaling are intentionally absent. Unknown
  values and precision-limited raw numerics may need an explicit Phase 3 policy.
- Old frontend browser-audit expectations hard-code the former outlier-penalized
  score. Their expected arithmetic will need updating when frontend work resumes;
  the frontend itself continues displaying the actual backend score.
- The unchanged frontend does not yet expose the new category summary or
  preprocessing audit as separate views; these are available to backend callers.

## 15. Recommendation for Phase 3

First verify the exporter schema and approve field-specific unknown/rejection
policies. Use `schema.feature_columns()` to exclude identifiers, targets and
leakage fields from predictive inputs. Then fit imputation/encoding/scaling on the
training partition only and reuse the fitted state on testing/validation/uploads.
Retain valid extremes and publish exclusions/audits alongside model results.
Only after that should model training and evaluation begin. This implementation
does not train Random Forest or any other model.
