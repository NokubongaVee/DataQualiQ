import { jsPDF } from 'jspdf'
import { percentage } from './intrusionResults'

export const IMPORTANT_RECORD_LIMIT = 20
const text = value => String(value ?? 'Not supplied').slice(0, 2000)
const probability = value => value == null ? 'Not available' : percentage(value)

// Export ordering only; backend classification, reliability and recommendations stay unchanged.
export function importantReportRecords(records) {
  const rank = row => row.prediction_status === 'Rejected' ? 2
    : row.label === 'Malicious' && row.reliability === 'Review' ? 0
      : row.label === 'Malicious' && row.reliability === 'Low' ? 1
        : row.label === 'Malicious' && row.reliability === 'High' ? 3 : 4
  return records.filter(row => rank(row) < 4).sort((a, b) => rank(a) - rank(b) || a.record_index - b.record_index).slice(0, IMPORTANT_RECORD_LIMIT)
}

export function networkReportSections(result) {
  if (!result?.intrusion_summary || !result.data_quality || !Array.isArray(result.records)) throw new Error('No active network analysis is available.')
  const s = result.intrusion_summary, q = result.data_quality, r = result.reliability_summary, m = result.model_performance
  const classified = s.normal_count + s.malicious_count
  const sections = []
  const add = (title, lines) => sections.push({ title, lines: lines.map(text) })
  add('Executive summary', [`${s.records_analysed} network records were analysed. ${s.normal_count} were classified as Normal and ${s.malicious_count} as Malicious. The uploaded data received a quality score of ${q.score}/100 (Grade ${q.grade}). ${r.review_count} records require Review; ${r.rejected_count} were rejected.`, 'Current-upload findings below are separate from saved official model evaluation.'])
  const qualityLines = ['Data errors, quality issues and analytical/security anomalies are distinct. Counts can overlap; analytical anomalies are not automatically incorrect data or attacks.']
  for (const [label, key, category] of [['Missing values', 'missing_values', 'Quality issues'], ['Duplicate rows', 'duplicates', 'Quality issues'], ['Invalid values', 'invalid_values', 'Data errors'], ['Inconsistencies', 'inconsistencies', 'Quality issues'], ['Analytical/security anomalies', 'analytical_anomalies', 'Analytical/security anomalies']]) {
    const group = q[key]
    qualityLines.push(`${label} (${category}): ${group.affected_records} affected records; ${group.occurrences} occurrences; ${group.finding_count} findings`)
    for (const field of group.by_column.slice(0, 10)) qualityLines.push(`Field ${text(field.column)}: ${field.occurrences} occurrences`)
    if (group.by_column.length > 10 || group.columns_truncated) qualityLines.push('Field details truncated for this report.')
  }
  qualityLines.push('Duplicate counts exclude the first occurrence.')
  qualityLines.push(...(q.warnings || []).slice(0, 20).map(warning => `Warning: ${text(warning)}`))
  if ((q.warnings || []).length > 20) qualityLines.push('Additional warnings omitted from this bounded summary.')
  add('Data quality', [`Quality score: ${q.score}/100; Grade ${q.grade}. Heuristic quality score, not prediction accuracy.`, ...qualityLines])
  add('Intrusion detection - current upload', [`Normal: ${s.normal_count}; Malicious: ${s.malicious_count}; Rejected: ${s.rejected_count}`, `Normal percentage: ${classified ? percentage(s.normal_count / classified) : 'Not available'}; Malicious percentage: ${classified ? percentage(s.malicious_count / classified) : 'Not available'}. Percentages use classified records only; rejected rows are excluded.`, `Average predicted-class probability: ${probability(s.average_predicted_class_probability)}`, 'Model probabilities are estimates, not calibrated guarantees.'])
  if (m.source === 'official_test_evaluation' && m.is_current_upload_metric === false) {
    add('Model Performance - Official Test Evaluation', ['Saved official test evaluation: Phase 5 results from the reserved test dataset; NOT calculated from the current uploaded file.', `${m.dataset}; ${m.records_evaluated} evaluated records`, `Accuracy: ${percentage(m.accuracy)}; Precision: ${percentage(m.precision)}; Recall: ${percentage(m.recall)}; F1-score: ${percentage(m.f1)}`, 'Confusion matrix: rows actual, columns predicted; order Normal, Malicious.', `True Normal: ${m.confusion_matrix?.[0]?.[0]}; False Alarm: ${m.confusion_matrix?.[0]?.[1]}`, `Missed Attack: ${m.confusion_matrix?.[1]?.[0]}; Correctly Detected Attack: ${m.confusion_matrix?.[1]?.[1]}`, 'False positives are normal traffic classified as malicious. False negatives are missed malicious traffic.'])
  } else add('Model Performance - Official Test Evaluation', ['Official evaluation metadata unavailable; no upload metrics substituted.'])
  add('Reliability - predictive-input integrity', [`High: ${r.high_count}; Review: ${r.review_count}; Low: ${r.low_count}; Rejected: ${r.rejected_count} (included in Low).`, 'High: prediction produced with no unresolved predictive-input integrity issue.', 'Review: prediction produced, but input had a relevant handled quality issue.', 'Low: prediction could not be safely produced due to invalid required input; rejected records have no class or probability.', 'Reliability describes input integrity, separate from model probability; it is not guaranteed correctness.'])
  const selected = importantReportRecords(result.records)
  const recordLines = [`Bounded selection: ${selected.length} important records, maximum ${IMPORTANT_RECORD_LIMIT}, from ${result.pagination.returned_records} returned rows of ${result.pagination.total_records} total (offset ${result.pagination.offset}). This is not a full-file ranking.`, 'Order: Malicious + Review, Malicious + Low, rejected records, Malicious + High. Rejected status takes precedence over any supplied class.', 'Record numbers are original one-based CSV data-row positions, excluding the header. No extra pages were fetched.']
  if (!selected.length) recordLines.push('No important records in the current returned page match these selection categories.')
  for (const row of selected) {
    recordLines.push(`Record ${row.record_index + 1}: ${row.prediction_status === 'Rejected' ? 'Rejected' : row.label}; predicted probability ${row.prediction_status === 'Rejected' ? 'Not available' : probability(row.predicted_class_probability)}; reliability ${row.reliability}; ${row.quality_status}`, `Reliability reason: ${text(row.reliability_reason)}`)
    for (const finding of row.quality_findings.slice(0, 3)) recordLines.push(`${text(finding.column || 'Dataset')}: ${text(finding.reason || finding.check)}`)
    if (row.quality_findings_truncated || row.quality_findings.length > 3) recordLines.push('Finding evidence truncated in this preview.')
    if (row.rejection_reason || row.prediction_status === 'Rejected') recordLines.push(`Rejection: ${text(row.rejection_reason || row.reliability_reason)}`)
  }
  add('Suspicious / important records', recordLines)
  const recommendations = []
  for (const item of result.recommendations.slice(0, 20)) recommendations.push(`${item.priority} priority: ${text(item.message)}`, `Reason: ${text(item.reason)}`, `Affected records: ${item.affected_records ?? 'Not supplied'}`)
  if (!recommendations.length) recommendations.push('No recommendations were returned by the backend.')
  if (result.recommendations.length > 20) recommendations.push('Additional backend recommendations omitted from this bounded report.')
  add('Security recommendations', ['Backend decision-support recommendations for human review and investigation.', ...recommendations])
  add('Limitations', ['Model probabilities are estimates, not calibrated guarantees. Input reliability is not guaranteed prediction correctness.', 'Analytical anomalies are not automatically attacks. The model requires compatible network features.', 'This prototype analyses uploaded network records, not live packet capture.', 'Only the currently returned record window is available for selection. The PDF does not include all predictions, evidence arrays, anomaly occurrences or raw audit structures.', 'Official evaluation is saved Phase 5 performance; model selection used that testing split, so it is not a fresh independent evaluation of the selected winner.', 'Analysis date/time is not supplied by the current backend response; no analysis timestamp was inferred.'])
  return sections
}

export function networkReportLines(result) {
  return ['DataQualiQ - Network Intrusion Analysis Report', `File: ${text(result.filename)}`, `Records analysed: ${result.intrusion_summary.records_analysed}`, ...networkReportSections(result).flatMap(section => [section.title, ...section.lines])]
}

export function createNetworkPdf(result) {
  const sections = networkReportSections(result)
  const pdf = new jsPDF({ format: 'a4', unit: 'mm' })
  const margin = 18, width = 174, bottom = 274
  let y = 20
  const header = () => {
    pdf.setFillColor(13, 30, 44); pdf.rect(0, 0, 210, 36, 'F')
    pdf.setTextColor(255, 255, 255); pdf.setFont('helvetica', 'bold'); pdf.setFontSize(18)
    pdf.text('Network Intrusion Analysis Report', margin, 17)
    pdf.setFont('helvetica', 'normal'); pdf.setFontSize(10); pdf.text('DataQualiQ | Cybersecurity decision support', margin, 27)
    y = 46
  }
  const nextPage = () => { pdf.addPage(); header() }
  const write = raw => {
    pdf.setFont('helvetica', 'normal'); pdf.setFontSize(11); pdf.setTextColor(35, 49, 62)
    // Standard PDF font: normalize common punctuation and keep line widths bounded.
    const value = text(raw).replace(/[\u2013\u2014]/g, '-').replace(/[\u2018\u2019]/g, "'").replace(/\u00b7/g, ' / ')
    const lines = pdf.splitTextToSize(value, width)
    if (y + Math.min(lines.length, 3) * 5.5 > bottom) nextPage()
    for (const line of lines) {
      if (y + 5.5 > bottom) nextPage()
      pdf.setFont('helvetica', 'normal'); pdf.setFontSize(11); pdf.setTextColor(35, 49, 62)
      pdf.text(line, margin, y); y += 5.5
    }
    y += 3
  }
  header()
  write(`Analysed filename: ${text(result.filename)}`)
  write(`Records analysed: ${result.intrusion_summary.records_analysed}`)
  for (const section of sections) {
    if (y + 28 > bottom) nextPage()
    pdf.setFillColor(235, 243, 249); pdf.rect(margin - 2, y - 5, width + 4, 10, 'F')
    pdf.setFont('helvetica', 'bold'); pdf.setFontSize(13); pdf.setTextColor(13, 66, 98)
    pdf.text(section.title, margin, y + 1); y += 13
    for (const line of section.lines) write(line)
    y += 4
  }
  const pages = pdf.getNumberOfPages()
  for (let page = 1; page <= pages; page++) {
    pdf.setPage(page); pdf.setDrawColor(210, 221, 230); pdf.line(margin, 281, 192, 281)
    pdf.setFont('helvetica', 'normal'); pdf.setFontSize(9); pdf.setTextColor(90, 105, 119)
    pdf.text('DataQualiQ | Decision-support summary', margin, 288); pdf.text(`Page ${page} of ${pages}`, 192, 288, { align: 'right' })
  }
  return pdf
}

export function downloadNetworkPdf(result) {
  createNetworkPdf(result).save('DataQualiQ-network-report.pdf')
}
