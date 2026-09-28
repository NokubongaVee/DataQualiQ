# Backend and integration review — 27 September 2026

## Already working

The module boundaries suit the current project: profiling/context, generic checks,
validity, anomalies, scoring, and translation remain separate. Exact duplicate
counting, identifier exclusion from outliers, and grade boundaries were sound.
The frontend already checked HTTP errors and read structured recommendations;
the old README warnings were stale. The documented currency-profile indentation
bug was also already fixed. Regression coverage now protects it.

## Problems and changes

| Finding | Resolution |
| --- | --- |
| Malformed CSV rows silently disappeared; automatic numeric conversion lost leading zeros | Shared strict CSV loader preserves original strings and rejects malformed rows |
| Fragile delimiter/encoding handling and silent header renaming | Constrained delimiter detection, encoding support, explicit header validation |
| Unbounded upload read before size check | Read at most the limit plus one byte and always close the upload |
| Processing blocked the async handler | Run parsing and assessment in the thread pool |
| Sample route depended on working directory | Resolve sample relative to the module |
| Client responses exposed exception internals | Generic failure response with server-side logging |
| Emoji printing crashed with Windows console encoding | Standard logging without dataset contents |
| Missing tokens were also marked invalid and skewed inference | Shared missing-value semantics |
| Damaged phone/date columns could escape validation | Honor explicit column-name signals |
| Numeric checks ignored parsing failures, small datasets and most-negative columns | Validate parsing/finiteness and apply only selected clear nonnegative bounds |
| Ordinary text, Unicode and rare categories produced false positives | Remove unsupported text constraints; require spelling evidence for category candidates |
| Category normalization collapsed punctuation/non-Latin labels | Normalize case/outer whitespace only |
| Currency syntax accepted bad comma grouping and rejected signs | Correct the shared currency pattern |
| Mixed date formats were missed; mixed timezones could fail | Add format checks and UTC-based parsing without rewriting source values |
| Zero-IQR data hid exceptional values | Detect departures from a constant majority |
| Small-dataset context confidence failed its test; substring matching created weak evidence | Cap confidence with limited support and use token-boundary matching |
| First-row-only type/pattern samples | Deterministic samples across up to 1,000 present values |
| Zero-count penalties and size-dependent duplicate severity | Ignore zero counts and use affected percentage for duplicates |
| Missing issue titles and unconditional duplicate deletion advice | Specific text/category titles and verify-before-merge/delete wording |
| Demo imports crashed test discovery | Main guards and current structured response fields |
| No backend dependency manifest | Record verified direct dependencies |
| Frontend severity casing mismatch selected low styles for all issues | Normalize severity in IssueCard, retaining existing style definitions |

The only frontend source change is `src/components/IssueCard.jsx`. Its reason was
explained before editing. Layout, styling definitions, navigation and features were
preserved. Existing architecture and API response structure were retained.

## Verification

- Initial discovery: one assertion failure (small-dataset context confidence), two
  import errors (console encoding and obsolete translator fields).
- Final `venv\Scripts\python.exe -m unittest discover -q`: **48 tests passed**.
  A new currency regression initially failed; it passed after the pattern fix.
- Live Uvicorn tests covered status/health, sample from a different working
  directory, multipart uploads, uppercase extension, empty/malformed input,
  missing multipart fields, frontend response shape and all four CORS origins.
- Regression coverage includes encoding/delimiter/quoting variants, preserved
  zeros, long fields, missing/duplicates, validation, formats/timezones, outliers,
  context, grade boundaries, score floor, upload-size handling, error redaction,
  and strict JSON serialization. Size enforcement was tested with a reduced mocked
  limit, not a full-size load benchmark.
- All four original demo scripts executed successfully after correction.
- `pip check`: no broken requirements. Python compilation check passed.
- Frontend build and lint passed before and after the integration fix. A build
  warning remains for a minified bundle larger than 500 kB.
- **Headless Edge browser smoke test passed**: real file upload, stored assessment,
  rendered recommendations, high-severity badge, four dashboard tabs, visible
  malformed-upload error and no uncaught exceptions. The deliberate error upload
  generates the frontend's expected console.error log.
- Sandboxed browser execution stalled; the run outside the sandbox passed. It
  routed API requests to a fresh isolated backend, leaving the existing port-8000
  service untouched. Restart that service to load the fixes.

## Remaining limitations

1. **Score policy:** the retained model is not normalized by column count; 6% and
   100% affected receive the same modifier. One entirely missing column costs
   22.5 points before other checks. Grades must not be interpreted as percentages
   of correct data. A proposed future policy is a normalized score across
   completeness, validity, consistency and uniqueness, using continuous affected
   proportions and explicit overlap handling. Its weights and definitions need
   agreement before replacing the current model.
2. **Heuristic assessment:** inferred types/roles/context are not a schema or
   calibrated probabilities. Highly corrupted/unusual columns can be missed.
   Outliers and repeated events can be legitimate. `NA` may be a real domain code.
   Ambiguous date ordering, locale-specific currency syntax, formatted currency
   outliers, and business-specific bounds are not exhaustively covered.
3. **Counts and presentation:** dashboard counts can overlap across fields/checks;
   they are not unique affected-row totals. The field chart shows its top five
   fields. These semantics were documented without redesigning the frontend.
4. **Capacity:** in-memory processing, multipart spooling and complete row-index
   arrays can consume substantial memory; sessionStorage can fill on large reports.
   Concurrency, maximum-size performance and deployment were not load-tested.
   The browser smoke test did not validate every action, PDF export, or all browsers.
5. **Deployment/reproducibility:** frontend API URL and CORS remain configured for
   local development. Direct dependencies are pinned, but a fresh installation and
   full transitive lock were not tested. No database, authentication or queue was added.
6. **Legacy helpers:** some unused translator role/severity helpers and context
   metadata remain. They are off the active path and were retained to avoid removing
   potentially externally used compatibility helpers without evidence.

Neither workspace is a Git checkout here; no Git diff, commit or pristine-baseline
comparison was available. Existing files were reviewed directly and verified with
the original suite, added regression tests and a real browser smoke test.
