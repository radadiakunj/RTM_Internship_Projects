import { useState } from 'react'
import './LearnPanel.css'

type ConceptId =
  | 'voltage'
  | 'current'
  | 'ohm'
  | 'capacitor'
  | 'resistor'
  | 'buck'
  | 'charge'

const CONCEPTS: { id: ConceptId; title: string; blurb: string }[] = [
  {
    id: 'voltage',
    title: 'Voltage',
    blurb: 'Electrical “pressure” that pushes charge. Higher voltage can push harder — and fry low-voltage pins.',
  },
  {
    id: 'current',
    title: 'Current',
    blurb: 'Flow of charge. Motors and servos gulp current; thin wires and weak bucks overheat.',
  },
  {
    id: 'ohm',
    title: 'Ohm’s Law',
    blurb: 'V = I × R. Change resistance and watch current and power update.',
  },
  {
    id: 'capacitor',
    title: 'Capacitors',
    blurb: 'Tiny rechargeable cushions. Bulk caps smooth motor dips; ceramics kill high-frequency noise.',
  },
  {
    id: 'resistor',
    title: 'Resistors',
    blurb: 'Limit current and divide voltage. Essential before feeding 5V-ish signals into ESP32 ADC.',
  },
  {
    id: 'buck',
    title: 'Buck converter',
    blurb: 'Steps a higher DC voltage down efficiently (e.g. 12V → 5V). Not for charging batteries from solar.',
  },
  {
    id: 'charge',
    title: 'Charge controller',
    blurb: 'Sits between solar and battery. Limits charge current and survives panel open-circuit voltage.',
  },
]

export function LearnPanel() {
  const [concept, setConcept] = useState<ConceptId>('ohm')
  const [resistance, setResistance] = useState(1000)
  const voltage = 5
  const current = voltage / resistance
  const power = voltage * current

  return (
    <div className="learn-panel">
      <header>
        <h2>Learn mode</h2>
        <p>Interactive concepts — not a circuit generator. Phase 2 preview.</p>
      </header>

      <div className="learn-panel__picks">
        {CONCEPTS.map((c) => (
          <button
            key={c.id}
            type="button"
            className={concept === c.id ? 'active' : ''}
            onClick={() => setConcept(c.id)}
          >
            {c.title}
          </button>
        ))}
      </div>

      <article className="learn-card">
        <h3>{CONCEPTS.find((c) => c.id === concept)?.title}</h3>
        <p>{CONCEPTS.find((c) => c.id === concept)?.blurb}</p>

        {concept === 'ohm' && (
          <div className="ohm-playground">
            <div className="ohm-visual" aria-hidden>
              <div className="tank">
                <div className="pressure" style={{ height: '70%' }} />
                <span>5V</span>
              </div>
              <div className="pipe">
                <div
                  className="flow"
                  style={{
                    animationDuration: `${Math.max(0.35, resistance / 800)}s`,
                    opacity: Math.min(1, 800 / resistance),
                  }}
                />
              </div>
              <div className="resistor-block">
                <span>{resistance} Ω</span>
              </div>
            </div>
            <label>
              Resistance
              <input
                type="range"
                min={100}
                max={10000}
                step={100}
                value={resistance}
                onChange={(e) => setResistance(Number(e.target.value))}
              />
            </label>
            <dl className="ohm-stats">
              <div>
                <dt>Voltage</dt>
                <dd>{voltage.toFixed(1)} V</dd>
              </div>
              <div>
                <dt>Current</dt>
                <dd>{(current * 1000).toFixed(1)} mA</dd>
              </div>
              <div>
                <dt>Power</dt>
                <dd>{(power * 1000).toFixed(1)} mW</dd>
              </div>
            </dl>
          </div>
        )}

        {concept === 'voltage' && (
          <div className="analogy">
            <div className="water high">High pressure = high voltage</div>
            <div className="water low">Low pressure = low voltage</div>
            <p className="warn-line">
              Feeding 12V into a 5V sensor is like putting firehose pressure into a garden hose fitting.
            </p>
          </div>
        )}

        {concept === 'buck' && (
          <div className="chain">
            <span className="chip">12V rail</span>
            <span className="arrow">→</span>
            <span className="chip accent">Buck</span>
            <span className="arrow">→</span>
            <span className="chip">5V / 3.3V</span>
          </div>
        )}

        {concept === 'charge' && (
          <div className="chain">
            <span className="chip">Solar</span>
            <span className="arrow">→</span>
            <span className="chip accent">Charge ctrl</span>
            <span className="arrow">→</span>
            <span className="chip">Battery</span>
            <p className="warn-line">Replacing the middle block with a buck is a common beginner mistake.</p>
          </div>
        )}
      </article>
    </div>
  )
}
