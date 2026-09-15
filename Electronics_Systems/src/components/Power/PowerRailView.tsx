import { useCircuitStore } from '../../lib/store'
import type { RailId } from '../../types/circuit'
import './PowerRailView.css'

const RAIL_VOLTAGE: Record<RailId, string> = {
  '12V': '~12V',
  '5V': '5V',
  '3.3V': '3.3V',
  BAT: '11.1V nom',
  SOLAR: '12V nom',
}

export function PowerRailView() {
  const rails = useCircuitStore((s) => s.rails)

  return (
    <section className="rail-panel">
      <header>
        <h2>Power rails</h2>
        <p>Current budget vs supply on each rail</p>
      </header>
      <div className="rail-grid">
        {rails.map((r) => {
          const pct =
            r.supplyMa > 0 ? Math.min(100, Math.round((r.drawMa / r.supplyMa) * 100)) : 0
          const live = r.supplyMa > 0
          return (
            <article
              key={r.rail}
              className={`rail-card ${r.overloaded ? 'over' : ''} ${live ? 'live' : ''}`}
            >
              <div className="rail-card__top">
                <strong>{r.rail}</strong>
                <span>{RAIL_VOLTAGE[r.rail]}</span>
              </div>
              <div className="rail-card__bar">
                <div
                  className="rail-card__fill"
                  style={{ width: `${live ? pct : 0}%` }}
                />
              </div>
              <div className="rail-card__nums">
                <span>{Math.round(r.drawMa)} mA draw</span>
                <span>{Math.round(r.supplyMa)} mA supply</span>
              </div>
              {live && (r.drawMa > 0 || r.feedsDownstream) && (
                <div className="rail-card__flow">
                  <span className="dot on" />
                  {r.overloaded
                    ? 'Overloaded'
                    : r.drawMa > 0
                      ? 'Power flowing'
                      : 'Feeding downstream'}
                </div>
              )}
              {live && r.drawMa === 0 && !r.feedsDownstream && (
                <div className="rail-card__flow muted">
                  <span className="dot" />
                  Ready — no load connected
                </div>
              )}
              {!live && <div className="rail-card__flow muted">No power</div>}
              {r.loads.length > 0 && (
                <ul className="rail-card__loads">
                  {r.loads.slice(0, 4).map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                  {r.loads.length > 4 && <li>+{r.loads.length - 4} more</li>}
                </ul>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
