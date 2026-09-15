import { Handle, Position, type NodeProps } from '@xyflow/react'
import { CATALOG_BY_ID } from '../../data/catalog'
import type { PinSpec } from '../../types/circuit'
import './ComponentNode.css'

export type CircuitNodeData = {
  instanceId: string
  defId: string
  label: string
  selected?: boolean
}

function pinSide(index: number, total: number): 'left' | 'right' {
  return index < Math.ceil(total / 2) ? 'left' : 'right'
}

function pinColor(pin: PinSpec): string {
  if (pin.role === 'gnd' || pin.polarity === 'negative') return '#495057'
  if (pin.role === 'power_in' || pin.role === 'power_out') return '#C1121F'
  if (pin.role === 'motor') return '#9B2226'
  if (pin.role === 'data') return '#2A9D8F'
  if (pin.role === 'analog') return '#BC6C25'
  if (pin.role === 'pwm') return '#E09F3E'
  return '#457B9D'
}

export function ComponentNode({ data, selected }: NodeProps) {
  const d = data as unknown as CircuitNodeData
  const def = CATALOG_BY_ID[d.defId]
  if (!def) return null

  const pins = def.pins
  const leftPins = pins.filter((_, i) => pinSide(i, pins.length) === 'left')
  const rightPins = pins.filter((_, i) => pinSide(i, pins.length) === 'right')

  return (
    <div
      className={`comp-node ${selected ? 'is-selected' : ''}`}
      style={{ borderColor: def.color }}
    >
      <div className="comp-node__header" style={{ background: def.color }}>
        <span className="comp-node__cat">{def.category}</span>
        <strong>{d.label}</strong>
      </div>
      <div className="comp-node__body">
        <div className="comp-node__col">
          {leftPins.map((pin) => (
            <div key={pin.id} className="comp-node__pin left">
              <Handle
                type="source"
                position={Position.Left}
                id={pin.id}
                className="comp-node__handle"
                style={{ background: pinColor(pin) }}
                title={`${pin.name} · ${pin.role}${pin.voltageOut != null ? ` · ${pin.voltageOut}V` : ''}${pin.voltageMax != null ? ` · max ${pin.voltageMax}V` : ''}`}
              />
              <span className="comp-node__pin-name" style={{ color: pinColor(pin) }}>
                {pin.name}
              </span>
            </div>
          ))}
        </div>
        <div className="comp-node__col right">
          {rightPins.map((pin) => (
            <div key={pin.id} className="comp-node__pin right">
              <span className="comp-node__pin-name" style={{ color: pinColor(pin) }}>
                {pin.name}
              </span>
              <Handle
                type="source"
                position={Position.Right}
                id={pin.id}
                className="comp-node__handle"
                style={{ background: pinColor(pin) }}
                title={`${pin.name} · ${pin.role}${pin.voltageOut != null ? ` · ${pin.voltageOut}V` : ''}${pin.voltageMax != null ? ` · max ${pin.voltageMax}V` : ''}`}
              />
            </div>
          ))}
        </div>
      </div>
      {def.isChargeController && (
        <div className="comp-node__badge">Charge controller — not a buck</div>
      )}
      {def.isBuckConverter && (
        <div className="comp-node__badge muted">Buck converter</div>
      )}
    </div>
  )
}
