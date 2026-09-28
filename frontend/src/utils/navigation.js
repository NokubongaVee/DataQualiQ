const PAGES = ['upload', 'overview', 'issues', 'by-field', 'actions']

export function restorePage(storage) {
  const saved = storage.getItem('currentPage')
  return PAGES.includes(saved) ? saved : 'upload'
}

export function rememberPage(storage, page) {
  const next = PAGES.includes(page) ? page : 'upload'
  storage.setItem('currentPage', next)
  return next
}
