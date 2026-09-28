"""Presentation adapter retaining the public review/recommendation/legacy contract."""
from recommendation_policy import build_recommendation


def translate_issue(issue, domain='generic', dataset_context=None, column_profile=None):
    policy = build_recommendation(issue, column_profile, dataset_context)
    check, col = issue.get('check', 'unknown'), issue.get('column')
    title = check.replace('_', ' ').capitalize() + (f': {col}' if col is not None else ': complete records')
    evidence = {**issue.get('evidence', {}), 'issue_type': check, 'column': col,
                'affected_records': issue.get('count', 0), 'affected_percentage': issue.get('pct', 0),
                'dataset_context': (dataset_context or {}).get('name', 'unknown'),
                'examples': issue.get('evidence', {}).get('examples', issue.get('examples', []))}
    legacy = {'title': title, 'description': policy['description'],
              'suggestion': policy['recommendation']['action'], 'severity': policy['severity'],
              'issue_type': check, 'column': col, 'count': issue.get('count', 0), 'pct': issue.get('pct', 0)}
    return {'issue_to_review': {'title': title, 'description': policy['description'],
                                'impact': policy['impact'], 'severity': policy['severity'], 'evidence': evidence},
            'recommendation': policy['recommendation'], 'legacy': legacy}


def translate_all_issues(issues, column_names=None, dataset_context=None, column_profiles=None):
    profiles = column_profiles or {}
    ranked = sorted(issues, key=lambda i: (-i.get('priority_score', 0), -i.get('pct', 0),
                                          str(i.get('column') or ''), i.get('check', '')))
    return [translate_issue(issue, dataset_context=dataset_context,
                            column_profile=profiles.get(issue.get('column'))) for issue in ranked]
