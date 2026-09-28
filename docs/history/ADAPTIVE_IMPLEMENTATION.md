# Adaptive assessment implementation — 28 September 2026

## Outcome

### Contextual guidance update

The pipeline now adds plain-language explanations through `contextual_guidance.py`.
Each finding explains what was observed, the possible consequence, a next step,
and the reason for its review priority. Supporting detector evidence is retained.
Applicant plus recruitment column signals identify a possible recruitment dataset;
the filename alone does not. Missing contact findings count affected rows with no
alternative populated contact field. Presence does not establish contact validity.
Missing age defaults to low review priority; age-dependent column signals raise it
to medium pending confirmation. The numerical quality-score formula is unchanged.
These are bounded, explainable rules, not unrestricted understanding of business
requirements. Source files are never modified. Existing saved assessments must be
run again to receive the new explanations.

The frontend restores the last visited page independently of saved results, shows
plain-language guidance before technical evidence, and uses red/high, orange/medium,
green/low badges. Regression coverage includes applicant contact alternatives,
optional versus age-dependent fields, unknown context, and refresh navigation.

The original implementation below describes the baseline before this update.

The existing FastAPI/React application now measures column evidence before
inferring types and selecting checks. Findings contain observations, denominators,
row indices, interpretation support, contradictions, review questions and limits.
Recommendations render those review questions rather than selecting a business
workflow from domain dictionaries. No external AI service, new dependency,
database or application rewrite was introduced.

CSV loading, upload endpoints, dashboard navigation, charts, PDF export and the
existing score formula remain. Source CSV values are never cleaned automatically.

## Changed files

| File | Responsibility/change |
| --- | --- |
| `profiling.py` (new) | Full-column missingness, blanks, frequencies, uniqueness, numeric parsing and distribution summaries; bounded pattern/date/length observations and examples |
| `type_inference.py` | Replaced large additive vocabulary scoring with corroborated hypotheses, alternatives and contradictions; removed unused role/tag dictionaries and high-uniqueness prose inference |
| `check_selection.py` (new) | Selected/skipped checks with reasons; dispatch to retained detectors; header conflicts, identifier shapes, date ambiguity and percent syntax |
| `relationships.py` (new) | Repeated candidate keys with differing associated fields; bounded co-missingness, concentration and supported categorical mappings |
| `finding_evidence.py` (new) | Evidence contract, contextual review questions, potential impacts, limitations and explicit review priority |
| `recommendation_policy.py` | Evidence-plan rendering; removed domain/workflow/consequence dictionaries; conservative compatibility fallback for raw findings without evidence |
| `translator.py` | Field-specific titles, structured evidence, legacy adapter and ordered reviews; removed redundant keyword/domain fallback |
| `pipeline.py` | Connect components; additive relationships/score-policy metadata; exclude new semantic/relationship candidates from legacy error penalties |
| `generic_checks.py` | Return exact compared denominators, observed reference formats and category variants |
| `validity_checks.py` | Removed header-triggered nonnegative constraints; retained reusable syntax detectors |
| `anomaly_detection.py` | Return IQR fences, quantiles, multiplier and finite-value denominator |
| `dataset_context.py` | Mark domain vocabulary as optional metadata and cap hypothesis support at 0.75 |
| `test_generalisation.py` (new) | Thirty-one behavioural tests, including multi-dataset, invariance, adversarial and changed-evidence cases |
| `test_backend.py` | Replace two obsolete assertions requiring header authority and name-only bounds |
| `test_recommendation_policy.py` | Replace seven obsolete domain/role-message expectations with evidence-driven behaviour; retain compatibility, immutability and score-independence checks; accept additive response metadata |
| `browser_smoke.mjs` | Evidence expansion, actual returned severity style, unfamiliar upload, priority order and downloaded PDF checks |
| `sample_data/generalisation/*.csv` (new) | Uploadable sales, HR, education and unfamiliar spectrometry examples |
| `README.md` | Current architecture, API additions, score semantics, coverage limits and tests |
| Frontend `src/utils/reviewOrder.js` and `.test.js` (new) | Stable review ordering and tests; no mutation of original findings |
| Frontend `src/components/IssueCard.jsx` | Recommendation plus expandable observations, examples, row numbers, support, contradictions and limitations |
| Frontend `src/pages/OverviewPage.jsx`, `IssuesPage.jsx` | Pass evidence to cards and order findings by review priority; use safe field-count dictionaries for arbitrary headers |
| Frontend `src/pages/ActionsPage.jsx` | Order actions and show the priority explanation |
| Frontend `src/pages/ByFieldPage.jsx` | Expandable column understanding and selected/skipped check coverage; readable new finding labels |
| Frontend `src/components/RecommendedActions.jsx` | Select top four after ranking |
| Frontend `src/components/ScoreCard.jsx` | Replace unsupported reliability/fitness claims with heuristic-score wording |
| Frontend `src/components/ScanPreview.jsx` | Label the fixed upload animation as an illustrative example |
| Frontend `src/components/IssuesByFieldChart.jsx` | Clarify that the chart counts occurrences |
| Frontend `src/utils/downloadAssessmentPdf.js` | Ordered evidence/limitations and heuristic-score explanation; line-by-line page overflow handling |

The frontend production output in `dist` was regenerated by the build. Neither
workspace contains Git metadata, so no Git diff or commit is available.

## Evidence and inference

Full-column measurements include row/present/missing/blank counts, exact distinct
and repeated-value counts, top frequencies, singleton/repeated-value summaries,
numeric parsing/finiteness, minimum, maximum, mean, median, standard deviation,
quartiles and skew. String/date observations use at most 1,000 deterministic
sampled present values, with sample size, population and method exposed.

Semantic roles are hypotheses. Headers may corroborate values, but cannot force
email/phone/date validation on incompatible values. Confidence is explicitly
heuristic support, capped for small samples, not a calibrated probability.
Observation confidence describes the count under a stated detector and population;
it is not certainty that the affected data is erroneous.

Examples of repaired behaviour:

- Unique sentences become free text, not an identifier with 0.98 confidence.
- Generic numeric `value` remains semantically unknown rather than monetary.
- Numeric values under `email` receive numeric checks and a header/value conflict.
- Date-shaped values no longer win a phone interpretation through overlapping syntax.
- Scientific notation remains numeric rather than becoming an alphanumeric key.
- Negative numeric values are not invalidated solely by a header token.

Selected and skipped checks are recorded in each column profile. Outlier checks
exclude candidate identifiers, constants, binary indicators and insufficient
finite-value support. Unknown semantic roles still receive representation-based
checks. Domain guesses do not affect detection, recommendations or priority.

## Relationships and review questions

Candidate identifiers are checked for repeated values across the full column.
All occurrences in a repeated key group are counted; exact-row duplicates retain
their previous excess-occurrence definition. Associated-field comparisons inspect
at most 20,000 repeated rows and 24 columns, with partial coverage explicit.

Pair exploration examines at most 20,000 deterministically sampled rows and the
first 24 sorted column names. Co-missingness needs at least five overlaps and
Jaccard agreement of 0.8. Concentration needs at least five rows inside and outside
a group, three missing observations, and a 25 percentage-point rate difference.
Categorical mappings require at least two repeated groups, five observations per
group, at least 20 supported records, multiple dependent values, and strong
agreement (90% within supported groups; 95% overall). Unique determinants cannot
create trivial dependencies. These are descriptive associations, not causal claims
or verified business constraints.

Review plans depend on the evidence:

- Entirely missing fields prompt export/optional-field review; substantial gaps
  prompt collection review; isolated gaps prompt source-record inspection.
- Concentration adds the observed group, its missingness rate and a group-coverage
  comparison; jointly missing fields add an optional-section/collection question.
- Repeated keys with differing fields prompt comparison of those fields and the
  intended record granularity. Matching associated fields prompt provenance review.
- Outlier advice cites measured quartiles and adds a default/rounding question
  when the middle half of the distribution is constant.
- Format advice includes observed variants or the supported reference pattern.
- Validation advice includes examples and the inferred representation; numeric
  parsing failures prompt review of meaningful codes before conversion.

There is still deterministic narrative vocabulary and reusable detector-family
logic. It is deliberately maintained and testable; it is not unrestricted natural
language reasoning. The complete recommendation depends on measured values,
distribution, relationships and uncertainty, not a domain or column-name lookup.

Review priority uses affected proportion, candidate uncertainty, corroborated key
evidence and observed concentration/conflicts. Formula: `min(1, 0.65 * proportion
+ base + key + systematic)`, with base 0.1 for review candidates and 0.3 otherwise,
key/systematic contributions 0.15 each, and high/medium cutoffs 0.5/0.2. The UI and
backend sort by this policy; the first four actions are genuinely the top four.
These policy weights describe review urgency, not business-loss probabilities.

## Score compatibility

`scoring.py` is unchanged. Existing scored checks retain their original weights,
percentage bands and grade boundaries. Better inference can change which checks
apply and therefore change a score. New header conflicts, repeated identifiers,
relationship/shape deviations and ambiguous dates are review-only and do not
receive the scorer's default error penalty. Percentage syntax uses its existing
default validity weight. Existing IQR/category/format penalties remain for
compatibility despite their candidate status. A score of 100 can therefore coexist
with review-only findings; the UI explains the heuristic nature of the score.

## Verification

- Baseline rerun: 78 backend tests, 4 frontend utility tests, frontend lint passed.
- Current backend: **109 tests passed**, including real HTTP uploads/error handling.
- New generalisation suite: **31 tests passed**. Four domain-varied datasets plus
  anonymous/misleading headers, filename invariance, equal-count changed evidence,
  unique prose, numeric identifiers, legitimate events, sparse fields, date
  ambiguity, scientific notation, syntax overlap, extreme numeric magnitudes, coverage limits and supported
  delimiters/encodings are covered.
- Frontend: **6 utility tests**, lint and production build passed.
- Headless Edge: sample and unfamiliar CSV uploads, evidence expansion, severity
  styling, review order, all dashboard tabs, PDF download and malformed-upload
  errors passed without uncaught browser exceptions.
- Manual output review confirmed distinct advice for concentrated missingness,
  conflicting identifiers, actual category variants and measured outlier fences.
- Search review found no domain workflow dictionaries in recommendations, no
  exact dataset-name branching and no header-only numeric bounds. Remaining
  semantic vocabulary is corroborating evidence; domain vocabulary is isolated.

## Limits and future work

- No semantic model can establish arbitrary business meaning from CSV values
  alone. Units, intentional repeated events, missing codes and valid ranges remain
  uncertain. Compact codes may be categories; anonymous unpadded numeric keys
  cannot reliably be distinguished from measurements.
- Parsing/pattern thresholds are heuristics, not learned/calibrated probabilities.
  Highly corrupted columns can escape specialised checks. Patterns outside the
  supported syntax, locale-specific numbers/currencies and compact dates may be
  missed. Currency-formatted values do not currently receive IQR analysis.
- IQR can flag valid extremes in skewed/multimodal populations. Spelling and
  formatting candidates may be intentional. Dependency checks are exploratory
  and have no multiple-testing correction or independent validation sample.
- Date inference uses a sample; full validity scans parse selected date columns.
  Relationship sampling/column limits can miss associations. They are exposed in
  the response, not silently presented as full-dataset discovery.
- The in-memory loader, full frequency summaries and row-index arrays still have
  size costs. Unrepresentable numeric summaries return null, and unrepresentable IQR fences skip outlier analysis with an explicit selection reason. No maximum-upload/concurrent-load benchmark was performed. Browser
  session storage can fill before the upload limit.
- The retained score is width-dependent and saturates at its percentage bands.
  Future score redesign should define dimensions and overlapping-cell treatment
  explicitly rather than silently changing historical grades.
- PDF generation retains built-in font limitations for some Unicode text. The
  browser test verifies generation/download, not all fonts and every page layout.
- The build retains the existing warning about a bundle over 500 kB. No fresh
  dependency installation or production deployment was performed.
- Optional future semantic assistance should be evaluated separately against these
  tests and grounded in observations; it must not invent findings or change scores.
