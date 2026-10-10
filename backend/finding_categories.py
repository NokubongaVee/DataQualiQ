"""Separate observed errors, quality concerns and non-error analytical candidates."""
from copy import deepcopy

ANALYTICAL = 'analytical_security_anomaly'
QUALITY = 'quality_issue'
ERROR = 'data_error'


def classify_findings(issues):
    findings = deepcopy(issues)
    for issue in findings:
        check = issue['check']
        if check in {'outlier', 'relationship_deviation', 'pattern_deviation'}:
            category = ANALYTICAL
        elif check in {'missing', 'duplicate', 'format', 'ambiguous_date',
                       'header_conflict', 'repeated_identifier', 'invalid_categorical'}:
            category = QUALITY
        elif check.startswith(('invalid_', 'network_invalid_')) or check == 'network_missing_field':
            category = ERROR
        else:
            category = QUALITY
        issue['category'] = category
        if category == ANALYTICAL or check == 'invalid_categorical':
            issue['review_only'] = True
        issue.setdefault('evidence', {})['category'] = category
    return findings


def category_summary(issues):
    return {category: {'findings': sum(i['category'] == category for i in issues),
                      'occurrences': sum(i['count'] for i in issues if i['category'] == category)}
            for category in (ERROR, QUALITY, ANALYTICAL)}
