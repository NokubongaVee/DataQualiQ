"""Explain measured findings in terms of plausible use, without inventing rules."""
import re
from value_utils import missing_mask


def tokens(label):
    return set(re.sub(r'([a-z])([A-Z])', r'\1_\2', str(label)).lower().replace('-', '_').replace(' ', '_').split('_'))


def add_contextual_guidance(df, issues, profiles, context):
    labels = {col: tokens(col) for col in df.columns}
    applicant_columns = [col for col, words in labels.items() if words & {'applicant', 'applicants', 'candidate', 'candidates'}]
    recruitment_columns = [col for col, words in labels.items() if words & {'job', 'position', 'interview', 'application', 'vacancy'}]
    recruitment = bool(applicant_columns and recruitment_columns)
    if recruitment:
        context.update(name='recruitment', confidence=.75,
                       evidence=['Applicant and recruitment fields: ' + ', '.join(dict.fromkeys(applicant_columns + recruitment_columns))],
                       limitations=['Inferred from column names; the intended workflow has not been confirmed.'])
    contacts = [col for col, words in labels.items() if not profiles[col].get('contradictions') and (
        profiles[col].get('role') in {'email', 'phone', 'contact_information'} or
        words & {'email', 'phone', 'telephone', 'mobile', 'contact'})]
    for issue in issues:
        col, check = issue.get('column'), issue['check']
        evidence = issue['evidence']
        count, denominator = issue['count'], issue['denominator']
        target = f'“{col}”' if col is not None else 'the dataset'
        why = {
            'missing': f'{count} of {denominator} records have no value in {target}. Blank cells and recognised missing-value markers are counted as missing.',
            'duplicate': f'{count} records repeat an earlier row exactly. They could be repeated imports or separate events with identical details.',
            'outlier': f'{count} values in {target} are unusually far from the typical values in this file. Unusual does not necessarily mean incorrect.',
            'format': f'{count} values in {target} use a different representation from other values in the same field.',
            'invalid_email': f'{count} values in {target} do not match the expected email format. This check cannot confirm whether a mailbox exists.',
            'invalid_phone': f'{count} values in {target} do not match the expected phone representation. This check cannot confirm whether a number is reachable.',
            'invalid_date': f'{count} values in {target} could not be read as valid dates under the date checks.',
            'invalid_numeric': f'{count} values in {target} could not be read as finite numbers.',
        }.get(check, f'{count} values in {target} differ from the expected type or the patterns found in this file. Review the examples before deciding they are errors.')
        impact = ' '.join(evidence['potential_impact'])
        action = ' '.join(evidence['review_questions'])
        reason = evidence['priority_reason']
        priority = issue['priority']
        if check == 'missing' and col in contacts:
            affected = df.index.isin(issue['row_indices'])
            no_contact = missing_mask(df[col])
            for other in contacts:
                no_contact &= missing_mask(df[other])
            unavailable = int((no_contact & affected).sum())
            subject = 'applicants' if recruitment else 'records'
            impact = (('This looks like an applicant dataset. Missing contact details can delay interview invitations and application updates. ' if recruitment else
                       'If this dataset is used to contact people, missing contact details can prevent messages from reaching them. ') +
                      f'{unavailable} of the {count} affected {subject} have no value in any recognised contact field. '
                      'Other contact values, where present, still need to be checked for usability.')
            action = ('Check the original application forms' if recruitment else 'Check the original source records') + \
                     '; recover verified contact details, starting with records that have no alternative contact. Do not invent contact details or discard otherwise valid records.'
            priority = 'high' if unavailable / max(len(df), 1) >= .1 else 'medium' if unavailable or issue['pct'] >= 10 else 'low'
            reason = f'{unavailable} records lack all recognised contact options; {count - unavailable} have another populated contact field. Priority reflects contact coverage, not just the number of blank cells.'
            evidence['contact_coverage'] = {'without_alternative': unavailable, 'with_alternative': count - unavailable, 'columns': contacts}
        elif check == 'missing' and labels.get(col, set()) & {'age', 'dob', 'birthdate'}:
            dependent = any(words & {'eligibility', 'pediatric', 'paediatric', 'dosage'} or {'age', 'group'} <= words for words in labels.values())
            priority = 'medium' if dependent else 'low'
            impact = 'Missing ages limit age-based summaries. They do not by themselves prevent contacting or reviewing an applicant. ' if recruitment else 'Missing ages limit age-based summaries. '
            impact += ('Other fields suggest an age-dependent use, so confirm the requirement before relying on those results.' if dependent else 'No explicit age-dependent requirement has been established from this file.')
            action = 'Confirm whether age is needed for the intended analysis or a documented requirement. If it is optional, leave unknown ages blank; if required, obtain verified values from the source rather than guessing.'
            reason = 'Age is not automatically high risk. ' + ('Possible age-dependent fields need review.' if dependent else 'Treat this as low priority unless the intended use requires age.')
        elif check == 'missing' and profiles.get(col, {}).get('role') in {'monetary_value', 'quantity', 'identifier', 'date'}:
            role = profiles[col]['role']
            impact = {'monetary_value': 'Totals and averages using this amount may be incomplete; a blank amount must not automatically be treated as zero.',
                      'quantity': 'Quantity totals may understate what was ordered or held when these records are excluded.',
                      'identifier': 'These records may be difficult to match to their source or link reliably to other tables.',
                      'date': 'These records may be left out of time-based reports or placed in the wrong reporting period.'}[role]
            action = f'Check the source for the missing values in {target} before using this field in reports. Keep unknown values marked as unknown and report how many records are excluded.'
        evidence['explanation'] = {'why': why, 'consequence': impact, 'next_step': action, 'priority_reason': reason}
        evidence['potential_impact'] = [impact]
        evidence['review_questions'] = [action]
        evidence['priority_reason'] = reason
        issue['priority'] = priority
        issue['priority_score'] = {'high': .8, 'medium': .5, 'low': .1}[priority]
        evidence['priority_score'] = issue['priority_score']
    return issues
