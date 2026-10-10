import { normalizeNetworkAnalysis } from '../utils/networkAnalysis.js'

export const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')

export function validateNetworkFile(file) {
  if (!file) return 'Please upload a CSV file first.'
  if (typeof file.name !== 'string' || !/\.csv$/i.test(file.name)) return 'Please choose a CSV file.'
  if (file.size === 0) return 'The selected CSV file is empty.'
  if (file.size > 50 * 1024 * 1024) return 'Please choose a CSV file no larger than 50 MiB.'
  return ''
}

export function backendErrorMessage(payload, status) {
  const detail = payload?.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    if (Array.isArray(detail.missing_fields) && detail.missing_fields.length) {
      return `Missing required features: ${detail.missing_fields.filter(value => typeof value === 'string').join(', ')}.`
    }
    if (typeof detail.message === 'string') return detail.message
  }
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return 'The backend rejected the upload request. Check the selected CSV and try again.'
  if (status === 503) return 'The saved model or its evaluation metadata is unavailable. Please contact the backend administrator.'
  return 'The backend could not analyse this network dataset. Please try again.'
}

export async function analyzeNetwork(file, { offset = 0, limit = 100, signal, baseUrl = API_BASE_URL, fetchImpl = globalThis.fetch } = {}) {
  const validation = validateNetworkFile(file)
  if (validation) throw new Error(validation)
  if (!Number.isInteger(offset) || offset < 0 || !Number.isInteger(limit) || limit < 0 || limit > 1000) throw new Error('Invalid record-page request.')
  const body = new FormData()
  body.append('file', file)
  let response
  try {
    response = await fetchImpl(`${baseUrl.replace(/\/+$/, '')}/analyze-network?${new URLSearchParams({ offset, limit })}`, { method: 'POST', body, signal })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('The backend is unavailable. Check the connection and try again.', { cause: error })
  }
  let payload
  try { payload = await response.json() } catch { throw new Error('The backend returned an unreadable response. Please try again.') }
  if (!response.ok) throw new Error(backendErrorMessage(payload, response.status))
  const result = normalizeNetworkAnalysis(payload)
  if (!result) throw new Error('The backend returned an incompatible network analysis response.')
  return result
}
