import { useState, useEffect } from 'react'

const TAG_STYLES = {
  FORMAT: 'bg-teal-500/15 text-teal-300 border border-teal-500/30',
  DUPLICATE: 'bg-violet-500/15 text-violet-300 border border-violet-500/30',
  MISSING: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
}
const ROWS = [
  { name: 'Thabo Nkosi', email: 'thabo.nkosi@example.com', date: '2026-01-15', country: 'South Africa' },
  { name: 'Amara Chukwu', email: 'amara@example', emailTag: 'FORMAT', date: '2026/13/40', dateTag: 'FORMAT', country: 'Nigeria' },
  { name: 'Amara Chukwu', email: 'amara.chukwu@example.com', emailTag: 'DUPLICATE', date: '2024-02-02', country: 'Nigeria' },
  { name: 'Wanjiru Kamau', email: '?', emailTag: 'MISSING', date: '2024-03-11', country: 'Kenya' },
  { name: 'Kwame Mensah', email: 'kwame.mensah@example.com', date: '2024-04-05', country: 'Ghana' },
  { name: 'Yasmin El-Sayed', email: 'y.elsayed@example.com', date: '2024-05-22', country: 'Egypt' },
]
const STATS = [
  { label: 'Missing', value: 1, color: 'text-amber-400' },
  { label: 'Duplicate', value: 1, color: 'text-violet-400' },
  { label: 'Format', value: 2, color: 'text-teal-400' },
  { label: 'Outlier', value: 1, color: 'text-rose-400' },
]
const TAGGED_CELLS = ['1-email', '1-date', '2-email', '3-email']

export default function ScanPreview() {
  const [scanPos, setScanPos] = useState(0)
  const [activeTagIndex, setActiveTagIndex] = useState(0)
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const id = setInterval(() => {
      if (!preference.matches) setScanPos(p => p >= 100 ? 0 : p + 1)
    }, 45)
    return () => clearInterval(id)
  }, [])
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const id = setInterval(() => {
      if (preference.matches) return
      setActiveTagIndex(index => (index + 1) % TAGGED_CELLS.length)
    }, 1000)
    return () => clearInterval(id)
  }, [])
  const tag = (label, key) => label && (
    <span className={`inline-block max-w-full px-1 py-0.5 rounded text-[9px] font-bold tracking-wide transition-opacity duration-300 ${TAG_STYLES[label]}`}
      style={{
        opacity: TAGGED_CELLS[activeTagIndex] === key ? 1 : 0,
        transitionDelay: TAGGED_CELLS[activeTagIndex] === key ? '300ms' : '0ms',
      }}>{label}</span>
  )
  return (
    <div className="scan-preview min-w-0 rounded-3xl shadow-xl" style={{ background: '#0B1E33' }}>
      <div className="flex items-center justify-between gap-2 px-3 sm:px-5 py-3 border-b border-white/10">
        <span className="text-xs font-mono text-slate-300">customers_raw.csv &middot; scanning&hellip;</span>
        <div className="flex gap-1.5 shrink-0" aria-hidden="true">
          {[0,1,2].map(i => <span key={i} className="w-1.5 h-1.5 rounded-full bg-slate-500" />)}
        </div>
      </div>
      <div className="mx-3 sm:mx-5 pt-1 relative">
        <div aria-hidden="true" className="scan-beam pointer-events-none absolute left-0 right-0"
          style={{
            height: '48px',
            top: `calc(${scanPos}% - ${scanPos * .48}px)`,
            background: 'linear-gradient(180deg, transparent, rgba(0,186,177,0.85), transparent)',
          }}>
          <div className="absolute left-0 right-0" style={{
            top: '50%',
            height: '2px',
            background: '#00BAB1',
            boxShadow: '0 0 8px 2px rgba(0,186,177,0.9)',
            transform: 'translateY(-50%)',
          }} />
        </div>
        <table className="preview-table w-full text-xs font-mono border-collapse relative" aria-label="Illustrative customer CSV scan">
          <colgroup><col style={{width:'22%'}}/><col style={{width:'34%'}}/><col style={{width:'26%'}}/><col style={{width:'18%'}}/></colgroup>
          <thead><tr className="text-slate-400">
            {['Name','Email','Signup date','Country'].map(text => <th key={text} scope="col" className="pb-1 pr-1 sm:pr-3 font-medium">{text}</th>)}
          </tr></thead>
          <tbody>{ROWS.map((row,i) => <tr key={i} className="border-t border-white/5 text-slate-200">
            <td className="py-2.5 pr-1 sm:pr-3">{row.name}</td>
            <td className="py-2.5 pr-1 sm:pr-3"><span className={row.emailTag ? 'text-rose-300' : ''}>{row.email}</span> {tag(row.emailTag,`${i}-email`)}</td>
            <td className="py-2.5 pr-1 sm:pr-3">{row.date} {tag(row.dateTag,`${i}-date`)}</td>
            <td className="py-2.5">{row.country}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 px-3 sm:px-5 py-2">
        {STATS.map(stat => <div key={stat.label} className="min-w-0 rounded-lg bg-white/5 border border-white/10 px-3 py-1">
          <div className={`text-lg font-bold ${stat.color}`}>{stat.value}</div>
          <div className="text-[11px] text-slate-400 mt-0.5">{stat.label}</div>
        </div>)}
      </div>
    </div>
  )
}
