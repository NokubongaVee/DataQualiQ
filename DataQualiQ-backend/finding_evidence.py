"""Attach measured observations and review questions to detector results."""
import pandas as pd
from value_utils import present_values


def enrich_findings(df, issues, profiles, relationships):
    for number, issue in enumerate(issues):
        col, check = issue.get('column'), issue['check']
        profile = profiles.get(col, {})
        full = profile.get('measurements', {}).get('full', {})
        population = 'all data records' if check in {'missing', 'duplicate'} else 'present values assessed'
        denominator = len(df) if check in {'missing', 'duplicate'} else full.get('present_count', len(df))
        if check == 'outlier':
            population = 'finite numeric values assessed'
        if check == 'format' and profile.get('type') == 'date':
            values = present_values(df[col]).astype(str)
            parsed = pd.to_datetime(values, errors='coerce', format='mixed', utc=True)
            denominator = int((parsed.notna() & values.str.match(r'^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}')).sum())
            population = 'parseable dates with comparable numeric styles'
        denominator = issue.get('denominator', denominator)
        if check == 'relationship_deviation':
            population = 'records in supported relationship groups'
        issue['denominator'] = denominator
        issue['pct'] = round(100 * issue['count'] / max(denominator, 1), 1)
        examples = ([str(df.at[i, col])[:120] for i in issue['row_indices'][:3]] if col is not None else [])
        context = [r for r in relationships['observations'] if
                   (r.get('column') == col or col in r.get('columns', []))]
        observations, questions, limitations = [], [], []
        impact = []
        pattern = issue.get('observed_pattern')
        relation = issue.get('relationship')
        if check == 'missing':
            observations.append(f'{full.get("blank_count", 0)} blank strings; {issue["count"]} total missing values under the documented null-marker policy.')
            if issue['count'] == len(df):
                questions.append('Check whether this field was omitted from the export or is intentionally unused; there are no observed values from which to infer replacements.')
            elif issue['pct'] >= 20:
                questions.append('Trace the collection or export process before filling gaps; missingness covers a substantial part of this field. Retain unknowns where the source cannot verify a value.')
            else:
                questions.append('Inspect the listed missing records against source evidence; retain unknowns where the source cannot verify a value.')
            impact.append('Summaries using this field exclude or otherwise handle the missing records.')
            limitations.append('Null markers such as NA may be legitimate codes. Missingness is not proven random.')
        elif check == 'duplicate':
            observations.append('These complete rows exactly repeat earlier rows; counts exclude the first occurrence.')
            questions.append('Compare event provenance or source record keys to establish whether these are repeated imports or legitimate identical events before merging or deleting anything.')
            impact.append('Counting every occurrence can increase record totals and aggregates.')
        elif relation and relation['kind'] == 'repeated_identifier':
            cols = relation['conflicting_columns']
            observations.append(f'{relation["distinct_repeated_values"]} candidate key values occur more than once.')
            if cols:
                observations.append('Associated values differ in: ' + ', '.join(cols) + '.')
                questions.append('Compare ' + ', '.join(cols) + ' within each repeated key group; determine whether the key identifies an entity with multiple events or should identify a single record.')
                impact.append('A join assuming one row per key can multiply records or select conflicting values.')
            else:
                observations.append('No differences were observed in the associated fields examined.')
                questions.append('Check source event identity for these matching key groups; matching associated fields alone do not establish accidental duplication.')
                impact.append('A join assuming unique keys may multiply records.')
            if not relation['complete']:
                limitations.append('Associated-field comparisons were bounded; unexamined rows or fields may differ.')
            limitations.append('A repeated entity identifier is often legitimate in event data.')
        elif relation:
            observations.append(f'{relation["agreement"]:.1%} agreement across {relation["support"]} repeated observations for {relation["determinant"]} → {relation["dependent"]}.')
            questions.append(f'Compare the exceptions with the observed mappings from {relation["determinant"]}; establish whether the relationship is intended before correcting anything.')
            impact.append('Grouping by these fields may produce unexpected combinations.')
            limitations.append('An observed mapping is not an established business constraint; exceptions may be valid.')
        elif 'statistics' in issue:
            s = issue['statistics']
            observations.append(f'IQR fences are {s["lower_bound"]:g} to {s["upper_bound"]:g}; Q1={s["q1"]:g}, Q3={s["q3"]:g}, multiplier={s["multiplier"]:g}.')
            questions.append(f'Compare the flagged values with the middle half of the observed distribution ({s["q1"]:g}–{s["q3"]:g}) and verify units or source entries; retain legitimate extremes.')
            if s['iqr'] == 0:
                questions.append('The middle half is constant; check whether defaults or rounding explain the repeated baseline.')
            impact.append('Extreme observations can influence means and totals.')
            limitations.append('IQR flags candidates, not errors; skewed or mixed populations can contain valid extremes.')
        elif profile.get('contradictions') and check == 'header_conflict':
            observations.extend(profile['contradictions'])
            questions.append('Compare the header and representative values with the export specification; establish which representation was intended before renaming or converting this field.')
            impact.append('Selecting transformations from the header alone could misinterpret the values.')
            limitations.append('The dataset alone cannot determine whether the header or the values are wrong.')
        elif pattern:
            observations.append(str(pattern))
            if 'pattern_support' in issue:
                observations.append(f'The reference shape occurs in {issue["pattern_support"]} of {denominator} present values.')
            questions.append(f'Confirm the intended convention against the observed pattern ({pattern}); preserve alternative representations until their meaning is established.')
            impact.append('Ambiguous or inconsistent representation can affect parsing or matching.')
        elif check == 'format':
            observations.append('Values differ from the most frequent comparable representation; ties do not establish a preferred convention.')
            observations.append('Observed sampled shapes: ' + ', '.join(f'{p["value"]} ({p["count"]})' for p in profile['measurements']['sample']['patterns'][:3]) + '.')
            variants = issue.get('format_evidence', [])
            if variants:
                observations.extend(f'Observed variants {v["variants"]!r} share a case/whitespace-normalised form with {v["reference"]!r} ({v["reference_count"]} reference occurrences).' for v in variants)
                questions.append('Compare ' + '; '.join(f'{v["variants"]!r} with {v["reference"]!r}' for v in variants[:2]) + '; establish whether case or whitespace carries meaning before standardising these groups.')
            else:
                questions.append('Compare the shown variants with the common values and agree a convention before standardizing equivalent representations.')
            impact.append('Equivalent values may be split during grouping or matching.')
            limitations.append('Representation differences may be intentional, particularly in case-sensitive fields.')
        else:
            observations.append(issue.get('selection_reason', f'The {check.replace("_", " ")} detector identified these values.'))
            observations.append(f'Representative flagged values: {examples!r}.')
            questions.append(f'Check {examples!r} against the observed {profile.get("type", "unknown")} representation and source records; correct only confirmed errors and revalidate.')
            if profile.get('type') == 'numeric':
                observations.append(f'{full.get("finite_numeric_ratio", 0):.1%} of present values parse as finite numbers; no domain range was assumed.')
                questions.append('Establish whether the nonnumeric entries are source errors or meaningful codes before choosing numeric conversion.')
            impact.append('Parsing or grouping this field may omit or separate the flagged values.')
            limitations.append('Syntax and statistical consistency do not establish real-world correctness.')
        concentrations = [r for r in context if r['kind'] == 'missing_concentration']
        for r in concentrations[:2]:
            observations.append(f'Missingness for {r["group_column"]}={r["group_value"]}: {r["missing_count"]}/{r["group_count"]} ({r["group_rate"]:.1%}), versus {r["outside_rate"]:.1%} outside the group.')
            questions.append(f'Compare collection coverage for {r["group_column"]}={r["group_value"]} with other groups before using this field in group comparisons.')
        for r in [r for r in context if r['kind'] == 'co_missingness'][:2]:
            observations.append(f'{r["overlap_count"]} examined records are missing both ' + ' and '.join(r['columns']) + '.')
            questions.append('Check whether the jointly missing fields share an optional section or collection step.')
        if context and relationships['coverage']['sampled']:
            limitations.append('Relationship context is sampled; counts describe examined records only.')
        if profile.get('role', 'unknown') == 'unknown':
            limitations.append('Field purpose is uncertain; units and business impact cannot be established from these values alone.')
        candidate = bool(issue.get('review_only')) or check in {'outlier', 'invalid_categorical', 'format'}
        semantic = {'role': profile.get('role', 'unknown'), 'confidence': profile.get('confidence', 0),
                    'support': profile.get('evidence', []), 'contradictions': profile.get('contradictions', []),
                    'alternatives': profile.get('alternatives', [])}
        # Extent drives priority, not a guessed domain or job-specific consequence.
        extent = issue['count'] / max(denominator, 1)
        importance = .15 if semantic['role'] == 'identifier' and semantic['confidence'] >= .6 else 0
        systemic = .15 if concentrations or (relation and relation.get('conflicting_columns')) else 0
        rank = min(1, extent * .65 + (.1 if candidate else .3) + importance + systemic)
        priority = 'high' if rank >= .5 else 'medium' if rank >= .2 else 'low'
        issue.update(id=f'finding-{number + 1}', priority=priority, priority_score=round(rank, 4))
        issue['evidence'] = {'denominator': denominator, 'population': population,
            'row_indices': issue['row_indices'], 'examples': examples,
            'observations': observations, 'statistics': issue.get('statistics'),
            'format_evidence': issue.get('format_evidence', []),
            'relationship': relation, 'context': context[:4], 'semantic': semantic,
            'observation_confidence': 1.0, 'observation_confidence_scope': 'Exact counts under the implemented detector and stated population; not certainty of error.',
            'interpretation_confidence': semantic['confidence'], 'candidate': candidate,
            'limitations': limitations, 'review_questions': questions, 'potential_impact': impact,
            'priority_score': issue['priority_score'],
            'priority_reason': f'{extent:.1%} of the stated population is affected. '
                + ('Candidate-key evidence increases review priority. ' if importance else '')
                + ('A concentrated or conflicting pattern increases review priority. ' if systemic else '')
                + ('This is a review candidate, so its error status remains uncertain.' if candidate else 'The detector observed a structural or syntax failure.'),
            'selection_reason': issue.get('selection_reason', 'Selected from observed structural or relationship evidence.')}
    return issues
