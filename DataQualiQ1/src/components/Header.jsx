import { useRef } from 'react'
import LogoMark from './LogoMark'

const PAGES = [['upload', 'Upload'], ['overview', 'Overview'], ['by-field', 'By field'], ['issues', 'Issues'], ['actions', 'Actions']]

export default function Header({ activePage = 'upload', onNavigate }) {
  const menu = useRef(null)
  const navigate = (page) => {
    if (menu.current) menu.current.open = false
    onNavigate?.(page)
  }
  return (
    <header className="w-full bg-white border-b border-slate-200">
      <div className="max-w-[1800px] mx-auto flex flex-wrap items-center justify-between gap-2 px-4 sm:px-8 py-2">
        <div className="flex items-center gap-3">
          <LogoMark size={38} />
          <span className="text-xl font-bold text-[#002A54]">DataQualiQ</span>
        </div>
        <nav aria-label="Primary navigation" className="hidden md:flex gap-4 text-sm font-semibold">
          {[['upload', 'Upload'], ['overview', 'Dashboard']].map(([page, label]) => (
            <button type="button" key={page} onClick={() => navigate(page)}
              aria-current={(page === 'upload' ? activePage === 'upload' : activePage !== 'upload') ? 'page' : undefined}
              className="px-3 py-2 text-slate-600 aria-[current=page]:text-[#08756F] aria-[current=page]:border-b-2">{label}</button>
          ))}
        </nav>
        <details ref={menu} className="mobile-menu w-full md:hidden" onKeyDown={event => {
          if (event.key === 'Escape') { menu.current.open = false; menu.current.querySelector('summary').focus() }
        }}>
          <summary className="cursor-pointer rounded-lg px-3 py-2 font-semibold text-[#08756F]">Menu</summary>
          <nav aria-label="Mobile navigation" className="grid grid-cols-2 gap-2 py-2">
            {PAGES.map(([page, label]) => <button type="button" key={page} onClick={() => navigate(page)} aria-current={activePage === page ? 'page' : undefined}
              className="rounded-lg px-3 py-2 text-left text-sm font-semibold text-slate-600 aria-[current=page]:bg-[#E6FBFA] aria-[current=page]:text-[#08756F]">{label}</button>)}
          </nav>
        </details>
      </div>
    </header>
  )
}
