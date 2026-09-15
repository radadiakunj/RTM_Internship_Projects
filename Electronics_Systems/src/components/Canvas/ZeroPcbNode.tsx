import { memo, useCallback, useMemo, type MouseEvent } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { CATALOG_BY_ID } from '../../data/catalog'
import { useCircuitStore } from '../../lib/store'
import { JUMPER_COLORS } from '../../types/circuit'
import type { CircuitNodeData } from './ComponentNode'
import './ZeroPcbNode.css'

/** A…Z then AA…AM — DIYLC / Veroboard style */
export function stripRowLabel(index: number): string {
  if (index < 26) return String.fromCharCode(65 + index)
  return 'A' + String.fromCharCode(65 + (index - 26))
}

function ZeroPcbNodeInner({ data, selected }: NodeProps) {
  const d = data as unknown as CircuitNodeData
  const def = CATALOG_BY_ID[d.defId]
  const grid = def?.boardGrid

  const boardJumpers = useCircuitStore((s) => s.boardJumpers)
  const trackCuts = useCircuitStore((s) => s.trackCuts)
  const boardTool = useCircuitStore((s) => s.boardTool)
  const jumperColor = useCircuitStore((s) => s.jumperColor)
  const pendingHole = useCircuitStore((s) => s.pendingHole)
  const setBoardTool = useCircuitStore((s) => s.setBoardTool)
  const setJumperColor = useCircuitStore((s) => s.setJumperColor)
  const clickBoardHole = useCircuitStore((s) => s.clickBoardHole)
  const removeBoardJumper = useCircuitStore((s) => s.removeBoardJumper)
  const clearPendingHole = useCircuitStore((s) => s.clearPendingHole)

  const cols = grid?.cols ?? 38
  const rows = grid?.rows ?? 39

  // Video/DIYLC proportions: strips narrower than pitch, cream margins all around
  const cell = cols >= 30 ? 12 : 13
  const margin = Math.round(cell * 0.9)
  const labelW = 26
  const labelH = 20
  const gap = Math.max(3, cell * 0.28)
  const stripH = cell - gap
  const holeR = cell * 0.21

  const boardW = cols * cell + margin * 2
  const boardH = rows * cell + margin * 2
  const svgW = labelW + boardW + 4
  const svgH = labelH + boardH + 4
  const gridX = labelW + margin
  const gridY = labelH + margin

  const holeCenter = useCallback(
    (col: number, row: number) => ({
      x: gridX + (col + 0.5) * cell,
      y: gridY + row * cell + stripH / 2,
    }),
    [gridX, gridY, cell, stripH],
  )

  const jumpers = useMemo(
    () => boardJumpers.filter((j) => j.boardInstanceId === d.instanceId),
    [boardJumpers, d.instanceId],
  )
  const cuts = useMemo(
    () => trackCuts.filter((c) => c.boardInstanceId === d.instanceId),
    [trackCuts, d.instanceId],
  )

  const onHoleClick = useCallback(
    (e: MouseEvent, row: number, col: number) => {
      e.stopPropagation()
      e.preventDefault()
      clickBoardHole(d.instanceId, row, col)
    },
    [clickBoardHole, d.instanceId],
  )

  if (!def?.boardGrid) return null

  const pendingHere =
    pendingHole?.boardInstanceId === d.instanceId ? pendingHole : null
  const showAllCols = cols <= 24

  return (
    <div className={`zero-pcb diylc ${selected ? 'is-selected' : ''}`}>
      <div className="zero-pcb__dragbar" title="Drag to move the board">
        <span className="zero-pcb__grip" aria-hidden>
          ⠿
        </span>
        <strong>{d.label}</strong>
        <span className="zero-pcb__dragbar-sub">
          {cols}×{rows} · drag here to move
        </span>
      </div>
      <div className="zero-pcb__toolbar nodrag nopan">
        <div className="zero-pcb__tools">
          <button
            type="button"
            className={boardTool === 'jumper' ? 'active' : ''}
            onClick={() => setBoardTool('jumper')}
            title="Place jumper wire (click two holes)"
          >
            Wire
          </button>
          <button
            type="button"
            className={boardTool === 'cut' ? 'active' : ''}
            onClick={() => setBoardTool('cut')}
            title="Cut copper strip at hole (DIYLC track break)"
          >
            Cut
          </button>
          <button
            type="button"
            className={boardTool === 'erase' ? 'active' : ''}
            onClick={() => setBoardTool('erase')}
            title="Erase jumper or cut at hole"
          >
            Erase
          </button>
          {pendingHere && (
            <button type="button" className="ghost" onClick={clearPendingHole}>
              Cancel
            </button>
          )}
        </div>
        <div className="zero-pcb__colors" title="Jumper wire color">
          {JUMPER_COLORS.map((c) => (
            <button
              key={c}
              type="button"
              className={`swatch ${jumperColor === c ? 'active' : ''}`}
              style={{
                background: c,
                boxShadow: c === '#FFFFFF' ? 'inset 0 0 0 1px #999' : undefined,
              }}
              onClick={() => {
                setJumperColor(c)
                setBoardTool('jumper')
              }}
              aria-label={`Wire color ${c}`}
            />
          ))}
        </div>
        <span className="zero-pcb__meta">
          {d.label} · {cols}×{rows}
          {pendingHere
            ? ` · from ${stripRowLabel(pendingHere.row)}${pendingHere.col + 1}`
            : ''}
        </span>
      </div>

      <div className="zero-pcb__board-wrap nodrag nopan">
        <svg
          className="zero-pcb__svg"
          width={svgW}
          height={svgH}
          viewBox={`0 0 ${svgW} ${svgH}`}
        >
          {/* Cream substrate (video look) */}
          <rect
            x={labelW}
            y={labelH}
            width={boardW}
            height={boardH}
            fill="#F0E2A8"
            stroke="#C8B26E"
            strokeWidth={1}
          />

          {/* Column numbers */}
          {Array.from({ length: cols }, (_, c) => {
            if (!showAllCols && !(c === 0 || c === cols - 1 || (c + 1) % 5 === 0)) {
              return null
            }
            return (
              <text
                key={`col-${c}`}
                x={gridX + (c + 0.5) * cell}
                y={gridY - margin / 2 + 2}
                textAnchor="middle"
                className="zero-pcb__label"
              >
                {c + 1}
              </text>
            )
          })}

          {/* Salmon copper strips with rounded ends + white holes */}
          {Array.from({ length: rows }, (_, r) => {
            const y = gridY + r * cell
            return (
              <g key={`strip-${r}`}>
                <text
                  x={labelW - 4}
                  y={y + stripH / 2 + 3}
                  textAnchor="end"
                  className="zero-pcb__label"
                >
                  {stripRowLabel(r)}
                </text>
                <rect
                  x={gridX}
                  y={y}
                  width={cols * cell}
                  height={stripH}
                  rx={2}
                  fill="#CE7D5F"
                  stroke="#B26A50"
                  strokeWidth={0.6}
                />
                {Array.from({ length: cols }, (_, c) => {
                  const cx = gridX + (c + 0.5) * cell
                  const cy = y + stripH / 2
                  const isPending =
                    pendingHere?.row === r && pendingHere?.col === c
                  return (
                    <g key={`h-${r}-${c}`}>
                      {/* Larger invisible hit target for easier clicking */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={cell * 0.45}
                        fill="transparent"
                        className="zero-pcb__hole"
                        onClick={(e) => onHoleClick(e, r, c)}
                      />
                      <circle
                        cx={cx}
                        cy={cy}
                        r={holeR}
                        fill="#FFFFFF"
                        stroke="#9C5A42"
                        strokeWidth={0.5}
                        pointerEvents="none"
                      />
                      {isPending && (
                        <circle
                          cx={cx}
                          cy={cy}
                          r={holeR + 2.5}
                          fill="none"
                          stroke={jumperColor === '#FFFFFF' ? '#888' : jumperColor}
                          strokeWidth={2}
                          pointerEvents="none"
                        />
                      )}
                    </g>
                  )
                })}
              </g>
            )
          })}

          {/* Track cuts (X) */}
          {cuts.map((cut) => {
            const { x, y } = holeCenter(cut.col, cut.row)
            const s = holeR * 1.3
            return (
              <g key={cut.id} pointerEvents="none">
                <line
                  x1={x - s}
                  y1={y - s}
                  x2={x + s}
                  y2={y + s}
                  stroke="#111"
                  strokeWidth={1.6}
                  strokeLinecap="round"
                />
                <line
                  x1={x + s}
                  y1={y - s}
                  x2={x - s}
                  y2={y + s}
                  stroke="#111"
                  strokeWidth={1.6}
                  strokeLinecap="round"
                />
              </g>
            )
          })}

          {/* Curved hookup jumper wires (video style) */}
          {jumpers.map((j) => {
            const a = holeCenter(j.col1, j.row1)
            const b = holeCenter(j.col2, j.row2)
            const dx = b.x - a.x
            const dy = b.y - a.y
            const len = Math.hypot(dx, dy) || 1
            // Perpendicular bow, scaled with distance (like flexible wire)
            const bow = Math.min(22, len * 0.22)
            const mx = (a.x + b.x) / 2 - (dy / len) * bow
            const my = (a.y + b.y) / 2 + (dx / len) * bow
            const path = `M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`
            const stroke = j.color === '#FFFFFF' ? '#E8E8E8' : j.color
            const w = cell * 0.42
            return (
              <g
                key={j.id}
                className="zero-pcb__jumper"
                onClick={(e) => {
                  e.stopPropagation()
                  removeBoardJumper(j.id)
                }}
              >
                <title>
                  {stripRowLabel(j.row1)}
                  {j.col1 + 1} ↔ {stripRowLabel(j.row2)}
                  {j.col2 + 1} (click to remove)
                </title>
                {/* Wire body */}
                <path
                  d={path}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={w}
                  strokeLinecap="round"
                  opacity={0.92}
                />
                {/* Glossy highlight down the middle */}
                <path
                  d={path}
                  fill="none"
                  stroke="#FFFFFF"
                  strokeWidth={w * 0.3}
                  strokeLinecap="round"
                  opacity={0.35}
                />
                <circle cx={a.x} cy={a.y} r={holeR * 1.15} fill={stroke} stroke="#1d1d1d" strokeWidth={0.4} />
                <circle cx={b.x} cy={b.y} r={holeR * 1.15} fill={stroke} stroke="#1d1d1d" strokeWidth={0.4} />
              </g>
            )
          })}
        </svg>

        {/* Off-board rail pads */}
        {def.pins.length > 0 && (
          <div className="zero-pcb__rail-handles">
            {def.pins.map((pin, i) => (
              <div
                key={pin.id}
                className="zero-pcb__rail-slot"
                style={{ top: `${12 + (i * 70) / Math.max(def.pins.length, 1)}%` }}
              >
                <span>{pin.name}</span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={pin.id}
                  className="zero-pcb__handle"
                  style={{
                    background:
                      pin.role === 'gnd'
                        ? '#333'
                        : pin.role === 'power_out'
                          ? '#c1121f'
                          : '#1d3557',
                  }}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <p className="zero-pcb__hint">
        Stripboard: holes in the same row share copper. <b>Wire</b> = click two holes for a
        jumper · <b>Cut</b> = break strip (X) · click a jumper to remove · right pads for
        off-board cables.
      </p>
    </div>
  )
}

export const ZeroPcbNode = memo(ZeroPcbNodeInner)
