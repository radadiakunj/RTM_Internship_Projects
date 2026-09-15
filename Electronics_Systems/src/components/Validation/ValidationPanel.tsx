import { useCircuitStore } from '../../lib/store'
import type { ValidationSeverity } from '../../types/circuit'
import './ValidationPanel.css'

const SEVERITY_ORDER: ValidationSeverity[] = ['error', 'warning', 'info', 'ok']

export function ValidationPanel() {
  const issues = useCircuitStore((s) => s.issues)
  const setHighlightedWire = useCircuitStore((s) => s.setHighlightedWire)
  const setSelected = useCircuitStore((s) => s.setSelected)
  const removeWire = useCircuitStore((s) => s.removeWire)

  const sorted = [...issues].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity),
  )

  const errors = issues.filter((i) => i.severity === 'error').length
  const warnings = issues.filter((i) => i.severity === 'warning').length

  return (
    <section className="val-panel">
      <header className="val-panel__head">
        <h2>Live checks</h2>
        <div className="val-panel__counts">
          <span className="err">{errors} errors</span>
          <span className="warn">{warnings} warnings</span>
        </div>
      </header>
      <ul className="val-panel__list">
        {sorted.map((issue) => (
          <li
            key={issue.id}
            className={`val-item severity-${issue.severity}`}
            onMouseEnter={() => issue.wireId && setHighlightedWire(issue.wireId)}
            onMouseLeave={() => setHighlightedWire(null)}
            onClick={() => {
              if (issue.instanceIds?.[0]) setSelected(issue.instanceIds[0])
            }}
          >
            <div className="val-item__top">
              <strong>{issue.title}</strong>
              <span className="tag">{issue.severity}</span>
            </div>
            <p>{issue.detail}</p>
            {issue.wireId && issue.severity === 'error' && (
              <button
                type="button"
                className="val-item__fix"
                onClick={(e) => {
                  e.stopPropagation()
                  removeWire(issue.wireId!)
                }}
              >
                Remove bad wire
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
