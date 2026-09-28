# Validation and evaluation

## How to interpret the evidence

Automated regression tests check specified behavior against controlled inputs. They are different from the capstone target of at least 90% agreement with independent manual review across three datasets. That benchmark is pending; no general accuracy percentage is claimed.

The publication validation results are recorded below after running the exact public-copy code. Historical reports in `history/` describe earlier versions and may contain outdated counts or interface behavior.

## Coverage

- Upload size, filename, encoding, delimiter, malformed-file, and API error behavior.
- Missing values, duplicates, validity, format regressions, scoring, and translation.
- Conservative field/domain inference, misleading headers, unknown domains, and changed value distributions.
- Relationship evidence, repeated identifiers, bounded coverage, and numeric edge cases.
- Applicant contact alternatives, optional age, and age-dependent review priorities.
- Frontend affected-value deduplication, review ordering, card rendering, and refresh navigation.

## Planned manual benchmark

1. Select at least three permitted datasets representing different structures and uses, such as recruitment, education, and sales.
2. Keep clean baselines and record deliberate corruptions separately, or independently annotate naturally occurring findings.
3. Define the unit of evaluation for each check: missing cell, invalid cell, duplicate row, or review candidate.
4. Freeze the assessed files and expected labels before running the tool.
5. Match predictions to labels by check, column, and record index; report true positives, false positives, and false negatives.
6. Report per-check precision and recall, a clearly defined agreement metric, and per-dataset results. Do not let abundant clean cells hide poor detection.
7. Review disagreements with a human assessor and document ambiguous cases rather than silently relabelling them.
8. Test whether nontechnical users can understand the issue descriptions and identify a reasonable next action.

## Publication check results

Validated on 29 September 2026 against the publication copy on Windows:

| Check | Result |
| --- | --- |
| Python unittest discovery | 113 tests passed |
| Frontend Node tests | 9 tests passed |
| ESLint | Passed |
| Vite production build | Passed; existing large-chunk warning |
| Fresh browser capture | Four screenshots captured from the running publication copy |
| Real synthetic CSV upload | Education fixture assessed and results rendered |
| Upload-page refresh | Stayed on Upload with saved results present |
| Captured layouts | No horizontal page overflow at 1440px desktop and 390px mobile widths |
| Browser runtime | No uncaught exceptions during the capture flow |
| Public file review | No common credential-token/private-key patterns or local academic identifiers detected in the publication file set |

The backend tests used the existing pinned Python environment. Frontend dependencies
were installed into the publication copy from the lockfile. These results do not
claim physical-device testing or a fresh run of every historical browser viewport.
GitHub Actions provides subsequent push/PR validation; a configured workflow alone
is not evidence of a successful run.
