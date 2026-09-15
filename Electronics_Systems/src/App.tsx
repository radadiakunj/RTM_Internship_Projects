import { useEffect } from 'react'
import { useCircuitStore } from './lib/store'
import { buildWiringGuide, downloadText } from './lib/exportGuide'
import { InventoryPanel } from './components/Inventory/InventoryPanel'
import { CircuitCanvas } from './components/Canvas/CircuitCanvas'
import { ValidationPanel } from './components/Validation/ValidationPanel'
import { PowerRailView } from './components/Power/PowerRailView'
import { LearnPanel } from './components/Learn/LearnPanel'
import { CATALOG_BY_ID } from './data/catalog'
import './App.css'

function seedStarterLayout() {
  const store = useCircuitStore.getState()
  store.clearCanvas()
  const ids: Record<string, string> = {}
  const place = (defId: string, x: number, y: number) => {
    const id = store.addComponent(defId, x, y)
    if (id) ids[defId] = id
  }

  place('battery-11v1', 40, 80)
  place('rocker-3pin', 40, 280)
  place('pdb-xt60', 280, 80)
  place('xl4016-buck', 280, 300)
  place('buck-4015', 520, 300)
  place('zero-pcb-large', 520, 60)
  place('esp32-devkit', 760, 60)
  place('scd4x', 1000, 40)
  place('veml7700', 1000, 220)
  place('nova-pm', 1000, 400)
  place('charge-controller', 40, 480)
  place('solar-12v', 40, 680)

  // Power chain wires
  const w = store.addWire
  if (ids['battery-11v1'] && ids['rocker-3pin']) {
    // Positive path through the switch (COM→NO). LED− ties to pack negative so
    // the illuminated rocker shares common GND; load return is still via PDB.
    w(ids['battery-11v1'], 'BAT_P', ids['rocker-3pin'], 'COM')
    w(ids['battery-11v1'], 'BAT_N', ids['rocker-3pin'], 'LED_GND')
  }
  if (ids['rocker-3pin'] && ids['pdb-xt60']) {
    w(ids['rocker-3pin'], 'NO', ids['pdb-xt60'], 'XT60_P')
  }
  if (ids['battery-11v1'] && ids['pdb-xt60']) {
    w(ids['battery-11v1'], 'BAT_N', ids['pdb-xt60'], 'XT60_N')
  }
  if (ids['pdb-xt60'] && ids['xl4016-buck']) {
    w(ids['pdb-xt60'], 'DIST_P', ids['xl4016-buck'], 'IN_P')
    w(ids['pdb-xt60'], 'DIST_N', ids['xl4016-buck'], 'IN_N')
  }
  if (ids['xl4016-buck'] && ids['buck-4015']) {
    w(ids['xl4016-buck'], 'OUT_P', ids['buck-4015'], 'IN_P')
    w(ids['xl4016-buck'], 'OUT_N', ids['buck-4015'], 'IN_N')
  }
  if (ids['buck-4015'] && ids['zero-pcb-large']) {
    w(ids['buck-4015'], 'OUT_P', ids['zero-pcb-large'], 'RAIL_3V3')
    w(ids['buck-4015'], 'OUT_N', ids['zero-pcb-large'], 'GND_PLANE')
  }
  if (ids['xl4016-buck'] && ids['zero-pcb-large']) {
    w(ids['xl4016-buck'], 'OUT_P', ids['zero-pcb-large'], 'RAIL_5V')
  }
  if (ids['pdb-xt60'] && ids['zero-pcb-large']) {
    w(ids['pdb-xt60'], 'DIST_P', ids['zero-pcb-large'], 'RAIL_12V')
  }
  if (ids['zero-pcb-large'] && ids['esp32-devkit']) {
    w(ids['zero-pcb-large'], 'RAIL_5V', ids['esp32-devkit'], 'VIN')
    w(ids['zero-pcb-large'], 'GND_PLANE', ids['esp32-devkit'], 'GND')
  }
  if (ids['zero-pcb-large'] && ids['scd4x']) {
    w(ids['zero-pcb-large'], 'RAIL_3V3', ids['scd4x'], 'VDD')
    w(ids['zero-pcb-large'], 'GND_PLANE', ids['scd4x'], 'GND')
  }
  if (ids['esp32-devkit'] && ids['scd4x']) {
    w(ids['esp32-devkit'], 'GPIO21', ids['scd4x'], 'SDA')
    w(ids['esp32-devkit'], 'GPIO22', ids['scd4x'], 'SCL')
  }
  if (ids['zero-pcb-large'] && ids['veml7700']) {
    w(ids['zero-pcb-large'], 'RAIL_3V3', ids['veml7700'], 'VDD')
    w(ids['zero-pcb-large'], 'GND_PLANE', ids['veml7700'], 'GND')
  }
  if (ids['esp32-devkit'] && ids['veml7700']) {
    w(ids['esp32-devkit'], 'GPIO21', ids['veml7700'], 'SDA')
    w(ids['esp32-devkit'], 'GPIO22', ids['veml7700'], 'SCL')
  }
  if (ids['zero-pcb-large'] && ids['nova-pm']) {
    w(ids['zero-pcb-large'], 'RAIL_5V', ids['nova-pm'], 'VCC')
    w(ids['zero-pcb-large'], 'GND_PLANE', ids['nova-pm'], 'GND')
  }
  if (ids['esp32-devkit'] && ids['nova-pm']) {
    w(ids['nova-pm'], 'TX', ids['esp32-devkit'], 'RX0')
  }
  if (ids['solar-12v'] && ids['charge-controller']) {
    w(ids['solar-12v'], 'PV_P', ids['charge-controller'], 'SOLAR_IN')
    w(ids['solar-12v'], 'PV_N', ids['charge-controller'], 'SOLAR_GND')
  }
  if (ids['charge-controller'] && ids['battery-11v1']) {
    w(ids['charge-controller'], 'BAT_OUT', ids['battery-11v1'], 'BAT_P')
    w(ids['charge-controller'], 'BAT_GND', ids['battery-11v1'], 'BAT_N')
  }
}

export default function App() {
  const mode = useCircuitStore((s) => s.mode)
  const setMode = useCircuitStore((s) => s.setMode)
  const theme = useCircuitStore((s) => s.theme)
  const setTheme = useCircuitStore((s) => s.setTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  const clearCanvas = useCircuitStore((s) => s.clearCanvas)
  const placed = useCircuitStore((s) => s.placed)
  const wires = useCircuitStore((s) => s.wires)
  const boardJumpers = useCircuitStore((s) => s.boardJumpers)
  const trackCuts = useCircuitStore((s) => s.trackCuts)
  const issues = useCircuitStore((s) => s.issues)
  const rails = useCircuitStore((s) => s.rails)
  const selectedInstanceId = useCircuitStore((s) => s.selectedInstanceId)
  const removeComponent = useCircuitStore((s) => s.removeComponent)

  const selected = placed.find((p) => p.instanceId === selectedInstanceId)
  const selectedDef = selected ? CATALOG_BY_ID[selected.defId] : null

  const exportGuide = () => {
    const text = buildWiringGuide(
      placed,
      wires,
      issues,
      rails,
      boardJumpers,
      trackCuts,
    )
    downloadText('wiring-guide.md', text)
  }

  return (
    <div className="app-shell">
      <header className="app-top">
        <div className="brand">
          <span className="brand__mark" aria-hidden />
          <div>
            <h1>BenchWire</h1>
            <p>Personal electronics layout · validate before you solder</p>
          </div>
        </div>

        <nav className="mode-tabs" aria-label="App modes">
          <button
            type="button"
            className={mode === 'manual' ? 'active' : ''}
            onClick={() => setMode('manual')}
          >
            Manual
          </button>
          <button
            type="button"
            className={mode === 'guided' ? 'active' : ''}
            onClick={() => setMode('guided')}
            title="Phase 2"
          >
            Guided
          </button>
          <button
            type="button"
            className={mode === 'learn' ? 'active' : ''}
            onClick={() => setMode('learn')}
          >
            Learn
          </button>
        </nav>

        <div className="app-actions">
          <div className="theme-toggle" role="group" aria-label="Color theme">
            <button
              type="button"
              className={theme === 'light' ? 'active' : ''}
              onClick={() => setTheme('light')}
              title="White mode"
            >
              ☀ White
            </button>
            <button
              type="button"
              className={theme === 'dark' ? 'active' : ''}
              onClick={() => setTheme('dark')}
              title="Dark mode"
            >
              ● Dark
            </button>
          </div>
          {mode === 'manual' && (
            <>
              <button type="button" className="ghost" onClick={seedStarterLayout}>
                Load starter power chain
              </button>
              <button type="button" className="ghost" onClick={clearCanvas}>
                Clear
              </button>
              <button type="button" className="primary" onClick={exportGuide}>
                Export wiring guide
              </button>
            </>
          )}
        </div>
      </header>

      {mode === 'learn' && (
        <main className="app-main learn">
          <LearnPanel />
        </main>
      )}

      {mode === 'guided' && (
        <main className="app-main guided">
          <div className="phase2-card">
            <h2>Guided mode — Phase 2</h2>
            <p>
              Auto-suggest wiring plans from your component specs: route 3.3V sensors to the 3.3V
              rail, flag overloaded rails, and tell you when you need a second buck or a charge
              controller. Manual mode already validates every wire you draw.
            </p>
            <button type="button" className="primary" onClick={() => setMode('manual')}>
              Back to Manual (MVP)
            </button>
          </div>
        </main>
      )}

      {mode === 'manual' && (
        <main className="app-main manual">
          <InventoryPanel />
          <div className="center-col">
            <PowerRailView />
            <div className="canvas-wrap">
              <CircuitCanvas />
            </div>
            {selected && selectedDef && (
              <div className="selection-bar">
                <div>
                  <strong>{selected.label}</strong>
                  <span>{selectedDef.name}</span>
                </div>
                <button type="button" onClick={() => removeComponent(selected.instanceId)}>
                  Remove from canvas
                </button>
              </div>
            )}
          </div>
          <aside className="right-col">
            <ValidationPanel />
            <div className="howto">
              <h3>How to use</h3>
              <ol>
                <li>Add parts from your inventory (+)</li>
                <li>On Zero PCB: Wire = jumper (2 holes), Cut = track break</li>
                <li>Drag module pin → pin for off-board cables</li>
                <li>Watch live voltage / polarity / GND checks</li>
                <li>Export guide (includes PCB jumpers + cuts)</li>
              </ol>
              <p className="howto__note">
                Known rule: Solar → Charge controller → Battery. Bucks only step rails
                (12V→5V→3.3V), they do not charge from solar.
              </p>
            </div>
          </aside>
        </main>
      )}
    </div>
  )
}
