const PAGES = ['upload', 'overview', 'data-quality', 'intrusion-detection', 'results', 'reports']
const LEGACY = { issues: 'results', 'by-field': 'data-quality', actions: 'reports' }

export function restorePage(storage) {
  let saved
  try { saved = storage?.getItem('currentPage') } catch { return 'upload' }
  const page = LEGACY[saved] || saved
  return PAGES.includes(page) ? page : 'upload'
}

export function rememberPage(storage, page) {
  const mapped = LEGACY[page] || page
  const next = PAGES.includes(mapped) ? mapped : 'upload'
  try { storage?.setItem('currentPage', next) } catch { /* Navigation works without persistence. */ }
  return next
}
