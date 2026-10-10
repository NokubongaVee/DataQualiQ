# DataQualiQ statistics audit

Audit run: 29 September 2026. Scope: numerical accuracy and consistency of the restored application. The existing assessment rules, score weights, severity policy, component layout, CSS and statistic color ranking were retained. No backend production code was changed in this audit.

## Outcome

Three reproduced frontend defects were corrected:

1. **Incomplete overview chart:** seven affected fields produced a chart total of 5 instead of 7. `slice(0, 5)` discarded findings before calculating the total and arc proportions. Both field views now receive complete grouped data. In the seven-field fixture each segment is 1/7, rather than five segments of 1/5.
2. **Stale assessment race:** after submitting `mixed.csv`, choosing `clean.csv` while the response was delayed still allowed the mixed result (33.5/F) to overwrite storage and navigate to the dashboard. A request-generation guard now rejects responses from replaced selections and unmounted upload pages. The replacement file can be assessed normally (100/A).
3. **Field-name collision:** a real `Other` column and dataset-wide duplicate rows were combined into one field. The CSV regression produced three groups instead of four and attributed a duplicate-row count to that column. Grouping now uses column identity, with null reserved for dataset-wide findings. Only a colliding dataset label receives the suffix ` (dataset)`; the real column keeps its name.

Final validation: 130 backend unittest tests and 22 frontend tests pass. The real-browser audit passes eight HTTP/React/PDF comparisons, replacement-upload handling, and action progress checks. Frontend lint and the final production build passed. The build retains a non-blocking warning for a JavaScript chunk larger than 500 kB. These results verify the listed cases; they do not prove correctness for every possible CSV or business interpretation.

## Statistics traced

| Statistic | Calculation and presentation | Verification |
|---|---|---|
| Rows and columns | `csv_loading` preserves parsed data records; `pipeline` uses DataFrame dimensions; StatCards and PDF use the returned values | Independent standard-library CSV parsing for eight fixtures, API equality, rendered cards, PDF label/value assertions |
| Missing counts | Case-insensitive trimmed empty/NA/N/A/null/nan/none plus actual nulls; per-column count; dashboard sums missing cells | Known missing cells, all-missing columns, empty-column regressions |
| Missing percentages | Finding: count / all records, rounded to 1 decimal; profile: same fraction rounded to 2 decimals | Independently calculated for every fixture column |
| Duplicate rows | Exact extra copies after the first occurrence; denominator all records | 3 excess rows among 23 = 13.0%; card and PDF consistency |
| Repeated identifiers | All members of repeated identifier groups, not just extra copies; denominator present identifier values | Same duplicate fixture correctly has 5 repeated-member records / 23 = 21.7%; separate review-only finding |
| Invalid values | Selected email/date/phone/currency/numeric/text/category/percentage rules; denominators exclude missing values | Known email/numeric CSV errors; date/phone/currency denominator checks; existing phone, control-character, category and percentage regressions |
| Inconsistent formatting | Non-dominant comparable styles; dates use comparable parseable numeric date styles | Known case variant CSV; existing date-style, thousands-grouping, malformed-grouping and whitespace/symbol regression tests |
| Invalid / inconsistent card | Union of row indices within each column across `format` and `invalid_*`; same index in different columns remains separate | Fixture cards plus existing overlap and exclusion tests; this is a distinct-cell count, not a sum of findings |
| Outlier counts and rates | IQR rule, strict outside fences; denominator finite numeric values only; eligibility remains unchanged | Independent linear-interpolated quartiles and row positions; mixed fixture 1/18 = 5.6%, pure outlier fixture 1/20 = 5.0%; existing binary/identifier/constant/extreme-value tests |
| Overall score and penalty | Existing per-finding weights and percentage tiers; score max(0,100-penalty) | Hand-calculated fixture totals, tier boundaries, repeated-column penalty suppression and clamping tests |
| Grade and label | A >=90, B >=75, C >=60, D >=40, otherwise F | Existing exact boundary tests plus fixture scores; rendered score/grade/label and real PDF values |
| Score ring | Progress = score/100 of circumference | Rendered SVG numerical assertions for every fixture |
| Findings to review | Number of translated findings, not rows or cells | Compared to known finding lists, rendered ScoreCard, API and PDF Issues found |
| Issue summary | Number of findings per check type | Independent Counter of expected finding types |
| Field-chart total and arcs | Sum of finding occurrences by column; each arc = group / all occurrences | Both pages rendered for every fixture, actual browser totals, numerical arc test, >5-field regression, Other-column collision regression |
| Field affected values | Union of row indices per column; dataset-level rows counted separately | Existing overlapping-cell tests and Other-column regression |
| Highest affected rate | Maximum individual finding percentage for that field; not a union percentage | Traced to `Math.max(issue.pct)` with backend denominators verified; no denominator conversion is performed |
| Column coverage | Present, missing, distinct values, sample size and population | Independent CSV counts for all fixture columns; sample-limit regression |
| Full profile summaries | Blank count, uniqueness, repeated occurrences, excess repetitions, frequency summary and common-value counts | Independent counters for all fixture columns |
| Numeric profile | Finite count/ratio, min/max/mean/median, population standard deviation, quartiles, skew, integer ratio, distinct numeric count | Standard-library math/statistics comparisons; separate nonfinite fixture and extreme-magnitude regressions |
| Sampled pattern measurements | Pattern/sample counts, lengths and representation ratios | Full-coverage fixture lengths; 1,200 identical code values give sample 1,000, leading-zero ratio 1 and known representation ratios; this is not exhaustive testing of every regex/locale |
| Relationship statistics | Missing overlap/union/Jaccard, within/outside group missing rates, categorical mapping support/agreement | Independent fixture: 8/9 overlap = .889, group 8/15 = .533 vs outside 0, mapping agreement 29/30 = .967 and deviation 1/30 = 3.3% |
| Severity / priority | Individual contextual badges and recommendation ordering; scorer also has its own percentage-tier severity | Existing cross-check consistency and badge tests; no aggregate severity-count or severity-percentage chart exists in the current UI |
| Confidence/support | Heuristic profile/context interpretation scores; frontend rounds profile confidence * 100 | Inspected; existing inference tests exercise supported/conflicting cases. This is not measured probability of correctness |
| Action progress | Completed checkbox count / number of recommendations, rounded for text | Real browser: 0/0 = 0%, 0/6 = 0%, 1/6 = 17%, 6/6 = 100% |
| Scan time | Browser elapsed time including HTTP and JSON handling, rounded to 0.1 s | Formatting tested with 1.2 s; not benchmarked as backend-only processing time |
| Upload size / scan preview | File bytes / 1024 rounded to 1 decimal; landing preview uses illustrative static counts | Inspected; preview is demonstration data, not an assessment statistic |
| PDF report | Same assessment score, grade, row/column counts, finding count and translated reviews | Eight real generated PDF downloads checked by summary label/value; translated count/rate/denominator integrity tested separately |

## Reproducible CSV results

All files are in `statistics-audit/fixtures/`. The standard-library CSV reader and independently authored expectations are used in `backend/test_statistics_audit.py`; expected counts are not inferred from the application's findings. `results.json` records full responses and is checked against fresh pipeline results. Browser HTTP responses must equal those snapshots before they are rendered.

| CSV | Rows x columns | Expected counts / percentages | Expected score / grade | Actual |
|---|---|---|---|---|
| clean.csv | 20 x 4 | No findings | 100 / A | Matches |
| missing.csv | 20 x 4 | measurement 1/20 = 5.0%; email 2/20 = 10.0%; 3 missing cells, 2 findings | 62.5 / C | Matches |
| duplicates.csv | 23 x 4 | 3 excess rows/23 = 13.0%; 5 repeated identifier members/23 = 21.7%; 2 findings | 85 / B | Matches |
| invalid.csv | 20 x 4 | 1 invalid number, 1 invalid email, 1 case-format variant; each 1/20 = 5.0%; 3 distinct invalid/format cells | 82 / B | Matches |
| outlier.csv | 20 x 4 | 1 finite numeric outlier/20 = 5.0% | 97 / A | Matches |
| mixed.csv | 20 x 4 | Missing measurement 1/20=5.0%; missing emails 2/20=10.0%; invalid number 1/19=5.3%; invalid email 1/18=5.6%; format 1/20=5.0%; outlier 1/18=5.6% | 33.5 / F | Matches |
| many_fields.csv | 20 x 8 | Seven missing findings, each 1/20=5.0%; chart total 7 | 0 / F | Backend matched; chart 5 before, 7 after fix |
| all_missing.csv | 20 x 4 | Three entirely missing columns: each 20/20=100%; 60 missing cells | 32.5 / F | Matches |
| other_column.csv | 21 x 4 | 1 duplicate row; 1 measurement missing; 2 Other values missing; 2 repeated identifiers; four separate groups, six occurrences | 52.5 / D | Backend correct; three groups before, four after fix |

Dashboard category expectations (missing, duplicate rows, distinct invalid/format cells, outliers) are respectively: clean (0,0,0,0), missing (3,0,0,0), duplicates (0,3,0,0), invalid (0,0,3,0), outlier (0,0,0,1), mixed (3,0,3,1), many_fields (7,0,0,0), all_missing (60,0,0,0).

Independent score arithmetic: missing penalties 15+22.5=37.5; invalid 5+8+5=18; duplicates 15; outlier 3; mixed 15+7.5+4.5+22.5+12+5=66.5; seven missing fields 105 (score clamped to zero); three all-missing columns 67.5. Repeated identifier candidates do not add a penalty.

## Checks, failures and corrections

- Final interrupted-run follow-up: the strengthened independent numeric-profile test and all 10 statistics-rendering tests passed; previously passed suites and browser checks were not repeated. Final lint and build passed (large-chunk warning only).
- Backend suite: **130 tests passed**, zero final failures. `statistics-audit/backend-tests.txt` contains the full test names and result.
- Frontend suite: **22 tests passed**, zero final failures. Includes eight fixture renderings, score-ring/field-arc arithmetic, collision regression and the 12 prior tests.
- Real browser: **passed** for eight HTTP responses, live React chart totals and downloaded PDF summary values; replacement upload race passed; progress checks passed; no uncaught browser exceptions. See `statistics-audit/browser-results.json` and `frontend/statistics_browser_audit.mjs`.
- Empty file and header-only CSV: rejected, rather than returning a misleading successful assessment. Zero-length profile ratios and empty chart rendering are safe. Existing API tests also cover malformed uploads, encodings and JSON-safe extreme numbers.
- Initial product failures: many_fields chart 5 versus 7; stale mixed.csv response persisted after clean.csv selection; Other column produced three groups versus four. Each has a passing regression after correction.
- Initial audit-harness errors: an incorrect date-check import and profile-key assumption were corrected in the new tests. These were test setup errors, not application defects.
- One expanded browser run timed out during concurrent validation. It passed when rerun alone. Parallel Vite instances also emitted an HMR-port warning; tests passed, and serial execution avoids service contention. Do not interpret these as numerical failures or omit them from run history.

Production files changed by this audit:

- `frontend/src/pages/OverviewPage.jsx`: use complete, identity-based field aggregation.
- `frontend/src/pages/ByFieldPage.jsx`: use the same aggregation and match detail findings by column identity.
- `frontend/src/utils/fieldCounts.js`: small shared aggregation function separating dataset-wide findings from real column names.
- `frontend/src/pages/UploadPage.jsx`: invalidate superseded requests before publishing statistics.

Added audit-only files: `backend/test_statistics_audit.py`, `frontend/statistics_audit.test.mjs`, `frontend/statistics_browser_audit.mjs`, this report, CSV fixtures and audit evidence in `docs/statistics-audit/`. Earlier uncommitted explanation/recommendation changes were preserved. Git diff therefore includes earlier work that is not part of this audit. No source data was cleaned, deleted or rewritten.

## Existing methodology and remaining limits

1. The score is a heuristic penalty total, **not the percentage of correct cells or records**. Penalties accumulate by findings/columns and can reach zero on wide datasets. Existing candidate outliers retain their legacy penalty; new semantic/relationship candidates are excluded.
2. Weights are missing 15, duplicate 10, email/date/phone/currency 8, numeric/text/category/format 5, outlier 3; unlisted scored types default to 5. Multipliers use already rounded finding percentages: >5% gives 1.5, >1% gives 1, otherwise .5. Near-boundary rounding is existing policy, not changed here. `scoring.py`'s docstring incompletely describes missing penalties: actual logic also penalizes small nonzero missing rates.
3. A finding count, occurrence count, affected-cell count and duplicate-row count are different units. The four category cards are not a comprehensive total of every review-only check. Overview recommendations show four entries; the Actions page lists all. These scopes remain unchanged.
4. Field charts intentionally count repeated rule occurrences. They do not represent unique bad records or a quality percentage. Per-field highest rate is a maximum across populations, not a combined affected-row rate.
5. Scoring severity tiers and contextual recommendation priority answer different questions. Their labels may differ. Statistic colors deliberately remain count-ranked, as previously requested.
6. Semantic confidence is heuristic; an inferred domain does not establish business rules. Missing age, rare categories and statistical outliers are not universally errors. No claim of semantic accuracy across arbitrary datasets is made.
7. Expensive representation profiling samples at most 1,000 present values. Pair relationships inspect at most 20,000 rows and 24 columns with explicit coverage metadata. Rare patterns can be missed. The tests exercise coverage disclosure, not exhaustive large-file detection.
8. Exact string duplicates do not normalize whitespace/case or equate different null spellings. The missing-token convention can treat a literal category such as NA as missing. These existing detection rules were retained.
9. Old saved responses without row_indices cannot supply exact distinct-cell unions; current API findings include indices and passed the checks. Reassess such legacy data rather than treating a cached aggregate as verified.
10. Time to scan includes client/network overhead. File size uses a 1024 divisor while the UI says KB. The scan-preview figures are illustrative. No timing benchmark or preview redesign was performed.
11. Action completion is local UI state, resets on remount and does not alter/reassess uploaded data. A replacement request is ignored when obsolete but its server computation is not cancelled.
12. The PDF checks verify summary text values and backend review evidence integrity, not full visual pagination, typography or every rendered body character. Browser coverage used installed desktop Edge; no cross-browser numerical compatibility claim is made.

## Run again

From `backend` (with installed dependencies):

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
```

From `frontend`, run these sequentially to avoid local service contention:

```powershell
node --test src/utils/affectedValues.test.js src/utils/reviewOrder.test.js src/utils/navigation.test.js src/components/IssueCard.test.js statistics_audit.test.mjs
node statistics_browser_audit.mjs
npm.cmd run lint
npm.cmd run build
```

The browser script requires installed Edge, backend venv, Node with built-in WebSocket, and free port 5173. It launches its own temporary API on an available port and closes its processes afterward. Synthetic audit data contains no real user records.
