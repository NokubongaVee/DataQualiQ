import { jsPDF } from 'jspdf'
import { rankReviews } from './reviewOrder'
import { getIntrusionResults, percentage, normaliseStatus, QUALITY_LABELS, RELIABILITY_LABELS } from './intrusionResults'

function getIssueDetails(issue) {
  const review = issue.issue_to_review || issue
  const recommendation = issue.recommendation || {}
  const legacy = issue.legacy || {}

  return {
    title: review.title || issue.title || legacy.title || 'Data issue detected',
    description: review.description || issue.description || legacy.description || '',
    impact: review.impact || '',
    action: recommendation.action || issue.suggestion || legacy.suggestion || 'Review the affected records.',
    priority: recommendation.priority || 'medium',
    severity: review.severity || issue.severity || legacy.severity || 'Medium',
    evidence: review.evidence || {},
  }
}

function addWrappedText(pdf, text, x, y, width, lineHeight = 5) {
  const lines = pdf.splitTextToSize(String(text || ''), width)
  for (const line of lines) {
    y = ensureSpace(pdf, y, lineHeight)
    pdf.text(line, x, y)
    y += lineHeight
  }
  return y
}

function ensureSpace(pdf, y, required = 18) {
  if (y + required > 280) {
    pdf.addPage()
    return 20
  }
  return y
}

export function downloadAssessmentPdf(result) {
  const pdf = new jsPDF()
  const issues = rankReviews(result.translated_issues || []).map(getIssueDetails)
  const rawIssues = result.issues || []
  let y = 20

  pdf.setFillColor(11, 30, 51)
  pdf.rect(0, 0, 210, 34, 'F')
  pdf.setTextColor(255, 255, 255)
  pdf.setFontSize(22)
  pdf.setFont('helvetica', 'bold')
  pdf.text('DataQualiQ Assessment Report', 15, 18)
  pdf.setFontSize(10)
  pdf.setFont('helvetica', 'normal')
  pdf.text(String(result.filename || 'Uploaded dataset'), 15, 27)

  y = 47
  pdf.setTextColor(11, 30, 51)
  pdf.setFontSize(15)
  pdf.setFont('helvetica', 'bold')
  pdf.text('Assessment summary', 15, y)
  y += 10

  const summary = [
    ['Quality score', `${result.score ?? 'N/A'}/100`],
    ['Grade', `${result.grade || 'N/A'}${result.label ? ` - ${result.label}` : ''}`],
    ['Rows scanned', result.total_rows ?? 'N/A'],
    ['Columns checked', result.total_columns ?? 'N/A'],
    ['Issues found', rawIssues.length],
    ['Dataset context', result.dataset_context?.name || 'unknown'],
  ]

  pdf.setFontSize(10)
  summary.forEach(([label, value], index) => {
    const columnX = index % 2 === 0 ? 15 : 110
    const rowY = y + Math.floor(index / 2) * 9
    pdf.setFont('helvetica', 'bold')
    pdf.text(`${label}:`, columnX, rowY)
    pdf.setFont('helvetica', 'normal')
    pdf.text(String(value), columnX + 32, rowY)
  })

  y += 32
  pdf.setFontSize(9)
  y = addWrappedText(pdf, 'Heuristic assessment score, not a percentage of correct data. Findings support review; they do not establish fitness for a business decision.', 15, y, 180)
  y += 4
  pdf.setDrawColor(220, 226, 232)
  pdf.line(15, y, 195, y)
  y += 12
  pdf.setFontSize(15)
  pdf.setFont('helvetica', 'bold')
  pdf.text('Issues to review', 15, y)
  y += 9

  if (issues.length === 0) {
    pdf.setFontSize(10)
    pdf.setFont('helvetica', 'normal')
    pdf.text('No issues were found in this dataset.', 15, y)
  } else {
    issues.forEach((issue, index) => {
      y = ensureSpace(pdf, y, 35)
      pdf.setTextColor(15, 140, 134)
      pdf.setFontSize(11)
      pdf.setFont('helvetica', 'bold')
      y = addWrappedText(pdf, `${index + 1}. ${issue.title}`, 15, y, 180, 6)
      pdf.setTextColor(70, 80, 90)
      pdf.setFontSize(9)
      pdf.setFont('helvetica', 'normal')
      y = addWrappedText(pdf, issue.description, 20, y, 170, 4.5)
      y += 2
      if (issue.impact) {
        y = addWrappedText(pdf, `Impact: ${issue.impact}`, 20, y, 170, 4.5)
        y += 2
      }
      y = addWrappedText(pdf, `Suggested action (${issue.priority} priority): ${issue.action}`, 20, y, 170, 4.5)
      for (const observation of issue.evidence.observations || []) {
        y = addWrappedText(pdf, `Evidence: ${observation}`, 20, y, 170, 4.5)
      }
      for (const limitation of issue.evidence.limitations || []) {
        y = addWrappedText(pdf, `Limit: ${limitation}`, 20, y, 170, 4.5)
      }
      y += 7
    })
  }

  const intrusion = getIntrusionResults(result)
  if (intrusion.data) {
    pdf.addPage()
    y = 20
    pdf.setFontSize(15)
    pdf.setFont('helvetica', 'bold')
    pdf.setTextColor(11, 30, 51)
    pdf.text('Intrusion detection results', 15, y)
    y += 10
    pdf.setFontSize(10)
    pdf.setFont('helvetica', 'normal')
    const modelSummary = [
      `Normal traffic: ${intrusion.normal ?? 'Pending'}`,
      `Attacks detected: ${intrusion.malicious ?? 'Pending'}`,
      `Average model confidence: ${percentage(intrusion.data.average_confidence)}`,
      ...[['Accuracy', 'accuracy'], ['Precision', 'precision'], ['Recall', 'recall'], ['F1 score', 'f1']]
        .map(([label, key]) => `${label}: ${percentage(intrusion.data.metrics?.[key])}`),
      'Record reliability is supplied by the backend, not inferred by this report.',
    ]
    for (const line of modelSummary) y = addWrappedText(pdf, line, 15, y, 180)
    if (intrusion.flaggedAttacks.length) {
      y = addWrappedText(pdf, `Reliability warning: ${intrusion.flaggedAttacks.length} supplied malicious records contain missing, inconsistent or invalid fields. Verify these records before taking action.`, 15, y, 180)
    }
    if (intrusion.malicious > 0 || intrusion.records.some(record => normaliseStatus(record.prediction) === 'malicious')) {
      y = addWrappedText(pdf, 'Security recommendation: Review malicious predictions against the original traffic records before taking action.', 15, y, 180)
    }
    y += 8
    if (!intrusion.records.length) y = addWrappedText(pdf, 'Record predictions: Pending', 15, y, 180)
    for (const record of intrusion.records) {
      y = ensureSpace(pdf, y, 30)
      y = addWrappedText(pdf, `Record ${record.record_id ?? 'Pending'}: ${record.source_ip || 'Pending'} to ${record.destination_ip || 'Pending'}; ${record.protocol || 'Pending'}`, 15, y, 180)
      const prediction = { normal: 'Normal', malicious: 'Malicious' }[normaliseStatus(record.prediction)] || 'Pending'
      const quality = QUALITY_LABELS[normaliseStatus(record.data_quality_status)] || 'Pending'
      const reliability = RELIABILITY_LABELS[normaliseStatus(record.reliability)] || 'Pending'
      y = addWrappedText(pdf, `Prediction: ${prediction}; Confidence: ${percentage(record.confidence)}; Data quality: ${quality}; Reliability: ${reliability}`, 15, y, 180)
      y += 5
    }
  }

  y = ensureSpace(pdf, y, 22)
  pdf.setDrawColor(220, 226, 232)
  pdf.line(15, y, 195, y)
  y += 11
  pdf.setTextColor(11, 30, 51)
  pdf.setFontSize(12)
  pdf.setFont('helvetica', 'bold')
  pdf.text('Generated by DataQualiQ', 15, y)
  pdf.setFontSize(8)
  pdf.setFont('helvetica', 'normal')
  pdf.setTextColor(100, 110, 120)
  pdf.text(new Date().toLocaleString(), 15, y + 6)

  const filename = `${String(result.filename || 'assessment').replace(/\.csv$/i, '')}-assessment.pdf`
  pdf.save(filename)
}
