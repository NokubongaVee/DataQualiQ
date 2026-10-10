"""Render measured findings as clear, contextual review guidance."""
from plain_language import readable_guidance


def build_recommendation(issue, column_profile=None, dataset_context=None):
    evidence = issue.get('evidence', {})
    profile = column_profile or {}
    target = repr(issue['column']) if issue.get('column') is not None else 'the dataset'
    count, pct = issue.get('count', 0), issue.get('pct', 0)
    population = evidence.get('population', 'assessed records')
    observations = evidence.get('observations', [])
    questions = evidence.get('review_questions', [])
    # Public helper callers may supply old raw findings. Do not fabricate
    # evidence or infer a workflow for them.
    if not questions:
        questions = ['Inspect the affected records and source evidence; the supplied finding has no detailed assessment context.']
    priority = issue.get('priority', 'high' if pct >= 10 and count else 'medium' if count else 'low')
    impact = ' '.join(evidence.get('potential_impact', [])) or 'The effect on downstream use is uncertain.'
    if profile.get('role', 'unknown') == 'unknown' or profile.get('confidence', 0) < .6 or profile.get('contradictions'):
        impact += ' The field purpose is uncertain.'
    candidate = evidence.get('candidate', issue.get('check') in {'outlier', 'invalid_categorical', 'format'})
    status = 'Review candidates, not established errors.' if candidate else ''
    description = f"{count:,} affected records in {target} ({pct:g}% of {population}). "
    description += ' '.join(observations[:2]) + (' ' + status if status else '')
    if evidence.get('explanation'):
        description = evidence['explanation']['why']
    action = f"Review the {count:,} affected records in {target}. " + ' '.join(questions)
    if evidence.get('explanation'):
        description, impact, action = readable_guidance(issue, profile, dataset_context or {})
    reason = evidence.get('priority_reason', 'Insufficient evidence for contextual prioritisation.')
    reason += ' This is a review priority, separate from the numerical quality-score penalty.'
    return {'description': description.strip(), 'impact': impact, 'severity': priority,
            'recommendation': {'title': f'Review {target} ({pct:g}% affected)',
                               'action': action, 'reason': reason, 'priority': priority}}
