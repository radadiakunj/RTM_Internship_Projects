import { useMemo, useState } from 'react'
import { CATALOG, CATEGORY_LABELS } from '../../data/catalog'
import { connectionSuggestions } from '../../lib/validation'
import { useCircuitStore } from '../../lib/store'
import type { ComponentCategory } from '../../types/circuit'
import './InventoryPanel.css'

export function InventoryPanel() {
  const addComponent = useCircuitStore((s) => s.addComponent)
  const remainingCount = useCircuitStore((s) => s.remainingCount)
  const usedCount = useCircuitStore((s) => s.usedCount)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<ComponentCategory | 'all'>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const categories = useMemo(() => {
    const set = new Set(CATALOG.map((c) => c.category))
    return ['all', ...set] as const
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return CATALOG.filter((c) => {
      if (category !== 'all' && c.category !== category) return false
      if (!q) return true
      return (
        c.name.toLowerCase().includes(q) ||
        c.shortName.toLowerCase().includes(q) ||
        c.description.toLowerCase().includes(q)
      )
    })
  }, [query, category])

  return (
    <aside className="inv-panel">
      <header className="inv-panel__head">
        <h2>Your parts</h2>
        <p>Real inventory — quantities match what you have.</p>
      </header>

      <input
        className="inv-panel__search"
        placeholder="Search components…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="inv-panel__cats">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            className={category === cat ? 'active' : ''}
            onClick={() => setCategory(cat)}
          >
            {cat === 'all' ? 'All' : CATEGORY_LABELS[cat] ?? cat}
          </button>
        ))}
      </div>

      <ul className="inv-panel__list">
        {filtered.map((c) => {
          const left = remainingCount(c.id)
          const used = usedCount(c.id)
          const open = expanded === c.id
          return (
            <li key={c.id} className={`inv-item ${left === 0 ? 'empty' : ''}`}>
              <button
                type="button"
                className="inv-item__main"
                onClick={() => setExpanded(open ? null : c.id)}
              >
                <span
                  className={`inv-item__swatch ${c.category === 'board' ? 'stripboard' : ''}`}
                  style={c.category === 'board' ? undefined : { background: c.color }}
                />
                <span className="inv-item__meta">
                  <strong>{c.shortName}</strong>
                  <small>
                    {left}/{c.qtyAvailable} left
                    {used > 0 ? ` · ${used} on canvas` : ''}
                  </small>
                </span>
              </button>
              <button
                type="button"
                className="inv-item__add"
                disabled={left <= 0}
                onClick={() => addComponent(c.id)}
                title="Add to canvas"
              >
                +
              </button>
              {open && (
                <div className="inv-item__detail">
                  <p>{c.description}</p>
                  {c.notes && <p className="note">{c.notes}</p>}
                  <p className="pins">
                    Pins: {c.pins.map((p) => p.name).join(', ')}
                  </p>
                  <ul className="tips">
                    {connectionSuggestions(c.id).map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </aside>
  )
}
