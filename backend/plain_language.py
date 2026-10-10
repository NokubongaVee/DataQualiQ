"""User-facing wording built from measured findings and supported context hints."""

TITLES = {
    'missing': 'Missing values detected',
    'duplicate': 'Duplicate records detected',
    'outlier': 'Outlier values detected',
    'format': 'Inconsistent formats detected',
    'invalid_email': 'Invalid email formats detected',
    'invalid_phone': 'Invalid phone formats detected',
    'invalid_date': 'Invalid dates detected',
    'invalid_numeric': 'Suspicious numeric values detected',
    'invalid_currency': 'Invalid amount formats detected',
    'invalid_text': 'Unexpected text values detected',
    'invalid_categorical': 'Possible category spelling variants detected',
    'header_conflict': 'Column name and values do not agree',
    'repeated_identifier': 'Repeated identifiers need review',
    'relationship_deviation': 'Unexpected combinations of values detected',
    'pattern_deviation': 'Values with an unusual pattern detected',
    'ambiguous_date': 'Dates with more than one possible meaning',
}


def readable_guidance(issue, profile, context):
    evidence = issue['evidence']
    explanation = evidence['explanation']
    check, column = issue['check'], issue.get('column')
    count, pct = issue.get('count', 0), issue.get('pct', 0)
    target = repr(column) if column is not None else 'the dataset'
    unit = 'record' if check in {'duplicate', 'repeated_identifier', 'relationship_deviation'} else 'value'
    subject = f"{count:,} {unit}{'' if count == 1 else 's'} in {target} ({pct:g}% of {evidence.get('population', 'assessed records')})"
    verb = 'is' if count == 1 else 'are'
    findings = {
        'missing': f'{verb} missing.',
        'duplicate': 'repeat earlier rows.' if count != 1 else 'repeats an earlier row.',
        'outlier': f'{verb} unusually far from the typical values in this field. These may be valid exceptions rather than errors.',
        'format': 'use a different format from comparable values in this field.' if count != 1 else 'uses a different format from comparable values in this field.',
        'invalid_email': 'do not follow the expected email format.' if count != 1 else 'does not follow the expected email format.',
        'invalid_phone': 'do not follow the expected phone format.' if count != 1 else 'does not follow the expected phone format.',
        'invalid_date': 'could not be read as valid dates.',
        'invalid_numeric': 'could not be read as finite numbers.',
        'invalid_currency': 'could not be read as valid amounts.',
        'ambiguous_date': 'can be interpreted as more than one date.',
        'repeated_identifier': 'occur in repeated identifier groups; a repeated identifier is not necessarily a duplicate record.',
        'relationship_deviation': 'form combinations that differ from the relationship usually seen between these fields.',
        'header_conflict': 'do not support the meaning suggested by the column name.',
        'invalid_text': 'do not match the expected text representation.',
        'invalid_categorical': ('look like possible spelling variants of more common categories.' if count != 1 else 'looks like a possible spelling variant of a more common category.') + ' These are candidates for review, not established errors.',
        'pattern_deviation': 'differ from the usual pattern in this field; confirm whether the alternatives are valid.',
    }
    description = subject + ' ' + findings.get(check, 'need review against the source records.')
    impact = explanation['consequence']
    action = explanation['next_step']
    domain = context.get('name', 'unknown')
    supported = bool(context.get('evidence')) and context.get('confidence', 0) >= .5 and not context.get('conflicting')
    if not supported:
        domain = 'unknown'
    role = profile.get('role', 'unknown')
    field_supported = profile.get('confidence', 0) >= .6 and not profile.get('contradictions')
    words = set(str(column).lower().replace('_', ' ').replace('-', ' ').split())
    flagged = f"the {count:,} flagged {'value' if count == 1 else 'values'} in {target}"
    location = bool(words & {'longitude', 'latitude', 'coordinates'}) and not profile.get('contradictions')
    measurement = bool(words & {'weight', 'height', 'temperature', 'distance', 'kg', 'cm'}) and not profile.get('contradictions')

    if check == 'duplicate':
        consequences = {
            'recruitment': 'If these records track applications, repeated rows may inflate application counts or lead to repeated follow-up with the same applicant.',
            'education': 'If these records support education reporting, repeated rows may inflate enrolment or assessment counts and distort summaries.',
            'sales': 'If these records represent sales, repeated rows may inflate order counts or revenue totals when every row is counted.',
            'inventory': 'If these records represent stock entries, repeated rows may overstate quantities and mislead replenishment planning.',
            'human_resources': 'If these records support staff reporting, repeated rows may inflate record counts or compensation totals.',
            'finance': 'If these records represent transactions, repeated rows may inflate totals or cause amounts to be counted twice.',
            'healthcare': 'If these records represent visits or services, repeated rows may inflate activity counts and distort operational reports.',
        }
        impact = consequences.get(domain, 'With the dataset context uncertain, repeated records may inflate record counts and aggregate summaries, potentially affecting downstream processing.')
        action = f"Review the {count:,} repeated {'row' if count == 1 else 'rows'} against source records; establish whether they represent duplicate entries or legitimate repeated events before merging or deleting anything."
    elif check in {'invalid_email', 'invalid_phone'}:
        channel = 'email addresses' if check == 'invalid_email' else 'phone numbers'
        outcome = {
            'recruitment': 'interview invitations or application updates',
            'education': 'student notifications or course updates',
            'sales': 'customer follow-up or order updates',
            'human_resources': 'staff communications',
        }.get(domain, 'messages or follow-up')
        impact = f'If this field is used for contact, these formats may prevent {outcome} from reaching the intended people. A format check does not establish whether an address or number is actually reachable.'
        action = f'Check the {count:,} affected records against the original source and confirm the {channel}. Use another verified contact method where available; do not guess replacement details.'
    elif check == 'missing' and 'contact_coverage' in evidence and domain not in {'unknown', 'recruitment'}:
        workflow = {'education': 'student notifications and course updates',
                    'sales': 'customer follow-up and order updates',
                    'human_resources': 'staff communications',
                    'healthcare': 'appointment communications',
                    'finance': 'account-related follow-up',
                    'inventory': 'supplier or stock-related follow-up'}.get(domain, 'follow-up')
        coverage = evidence['contact_coverage']
        impact = (f'If this contact field is used for {workflow}, missing details may delay reaching the intended people. '
                  f"{coverage['without_alternative']} of the {count} affected records have no value in any recognised contact field. "
                  'Any alternative contact details still need to be checked for usability.')
    elif check == 'missing' and 'contact_coverage' not in evidence:
        # Age-specific advice remains intact, including its cautious priority.
        words = str(column).lower().replace('_', ' ').replace('-', ' ').split()
        age = set(words) & {'age', 'dob', 'birthdate'}
        if not age and domain == 'education' and set(words) & {'mark', 'marks', 'score', 'grade', 'gwa', 'gpa'} and not profile.get('contradictions'):
            impact = 'If this field contains academic results, missing values can leave learners out of averages or comparisons. This can make summaries unrepresentative of the full group; a missing result must not be treated as a zero.'
            action = 'Check the original assessment or admissions records and confirm whether each result is unavailable, pending, or not applicable. Use only verified results in comparisons and state how many records were excluded.'
        elif not age and field_supported:
            if role == 'monetary_value' and domain in {'sales', 'finance', 'human_resources'}:
                use = {'sales': 'sales totals', 'finance': 'financial summaries', 'human_resources': 'compensation summaries'}[domain]
                impact = f'If this amount contributes to {use}, missing values can make the totals incomplete. Do not substitute zero unless the source confirms that no amount applies.'
            elif role == 'quantity' and domain == 'inventory':
                impact = 'Missing quantities can leave stock totals incomplete and make replenishment planning unreliable. Confirm whether the quantity is unknown or genuinely zero.'
        elif not age and domain == 'unknown':
            impact = 'With the dataset context uncertain, missing information may exclude these records from summaries or comparisons that use this field. Confirm whether the field is required before deciding how urgently to complete it.'
    elif check == 'outlier':
        impact = 'If these values are entry errors and remain uncorrected, they may pull averages away from typical results and distort comparisons. Unusual values can also be genuine observations, so removing them without checking could hide important information.'
        if location:
            impact = f'If {target} represents geographic coordinates, an incorrect value may place a record in the wrong location and distort maps or regional summaries. Being unusual in this file does not prove that a coordinate is wrong.'
        elif measurement:
            impact = f'If {target} is a measurement, a unit mix-up or entry error could distort averages and comparisons. Genuine unusually large or small measurements should be retained.'
        elif field_supported and role == 'monetary_value':
            impact = 'An incorrect amount may distort totals, averages, and comparisons. A genuine large transaction or amount should be retained rather than removed simply because it is unusual.'
        action = f'Inspect {flagged} against the original records; check units and entry mistakes, retain legitimate exceptions, and correct only confirmed errors.'
        stats = evidence.get('statistics') or issue.get('statistics')
        if stats:
            action += f" For comparison, the middle half of the measured values lies between {stats['q1']:g} and {stats['q3']:g}; this is a reference, not an allowed range."
    elif check == 'invalid_categorical':
        impact = 'If the same category has been entered with different spellings, reports may split it into separate groups. Counts and filters can then miss records or make comparisons misleading. A genuinely different category should remain separate.'
        action = f'Compare {flagged} with the intended category list and source records. Correct spelling only when the meanings match; retain legitimate categories and run the assessment again.'
    elif check in {'format', 'pattern_deviation'}:
        impact = 'Different representations of the same information may be treated as different values when records are grouped, filtered, or matched. This can split totals or leave records out of a report even though the information is present.'
        if profile.get('type') == 'date':
            impact = 'Mixed date formats may be read in different day/month orders or rejected by another system, placing records in the wrong period or leaving them out of date-based reports.'
        action = f'Compare {flagged} with the source and the agreed format. Standardise only values that mean the same thing; keep meaningful differences.'
        variants = evidence.get('format_evidence') or []
        if variants:
            variant = variants[0]
            action += f" Compare {variant['variants']!r} with {variant['reference']!r} before deciding whether they should be grouped together."
        elif issue.get('observed_pattern'):
            action += f" The observed reference is: {issue['observed_pattern']} Confirm it before applying it to every record."
    elif check == 'ambiguous_date':
        impact = 'A date read in the wrong day/month order can move a record to the wrong reporting period or change its place in a timeline. The file alone may not establish which interpretation was intended.'
        action = f'Check {flagged} against the original dates and confirm the source date convention. Do not automatically swap the day and month; use an agreed unambiguous format once verified.'
    elif check == 'header_conflict':
        impact = 'If users or software rely on this column name, they may choose the wrong calculation or validation rule and misinterpret the results. The name or the values may need correction; the file alone does not establish which.'
        action = f'Compare the name and values in {target} with the source specification. Confirm what the field actually contains before renaming it or converting its values.'
    elif check == 'relationship_deviation':
        impact = 'If the usual relationship is an intended rule, these combinations may put records in the wrong group and distort grouped reports. Exceptions can also be legitimate changes, so the pattern alone is not proof of error.'
        # Retain the measured field names and relationship from the detector.
        action = explanation['next_step'] + ' Correct only confirmed mismatches and keep valid exceptions.'
    elif check == 'repeated_identifier':
        impact = 'If each identifier is expected to identify one record, repeats may cause double counting or link the wrong details when tables are combined. An identifier may legitimately appear in multiple events.'
        action = explanation['next_step'] + ' Confirm the intended record structure before merging or deleting rows.'
    elif check == 'invalid_text':
        impact = 'Unexpected text may prevent reliable searching or matching and can make labels difficult to interpret. Some short or unusual text may still be valid for this field.'
        action = f'Verify {flagged} against the source and the intended text requirements. Correct confirmed entry errors, preserve legitimate names or codes, and assess the file again.'
    elif check in {'invalid_numeric', 'invalid_currency'}:

        impact = 'Calculations may reject these entries or leave them out, making totals and averages incomplete. Do not treat unreadable values as zero.'
        if field_supported and role == 'monetary_value' and domain in {'sales', 'finance'}:
            impact += ' If these amounts are used in sales or financial reports, reconcile them before relying on those totals.'
        if measurement:
            impact = f'If {target} is a measurement, unreadable values may be excluded from calculations, making measurement averages and comparisons incomplete. Treating them as zero could introduce a different error.'
        elif location:
            impact = f'If {target} represents geographic coordinates, unreadable values may prevent records from appearing on a map or being included in regional summaries.'
        action = f'Verify {flagged} against the original source; confirm units, decimal separators, and whether text entries are meaningful codes. Correct only confirmed errors, then run the assessment again.'
    elif check == 'invalid_date':
        impact = 'These records may be left out of date-based reports or assigned to the wrong period. Their actual dates cannot be recovered reliably from an invalid value alone.'
        action = f'Check the original dates in {target}, confirm the intended day/month order, and correct verified entry errors. Keep unavailable dates marked as unknown.'

    # Preserve measured distinctions that change the next step, even when the
    # main advice is simplified (for example, a gap concentrated in one group).
    for question in evidence.get('review_questions', []):
        if ('collection coverage' in question or 'optional section' in question or 'no observed values' in question) and question not in action:
            action += ' ' + question
    if domain != 'unknown' and domain != 'recruitment' and (check == 'duplicate' or (check == 'missing' and domain == 'education' and 'academic results' in impact)):
        impact = f"The column evidence suggests a {domain.replace('_', ' ')} dataset. " + impact
    return description, impact, action
