import { CATALOG_BY_ID } from '../data/catalog'
import { stripRowLabel } from '../components/Canvas/ZeroPcbNode'
import type {
  BoardJumper,
  PlacedComponent,
  RailStatus,
  TrackCut,
  ValidationIssue,
  Wire,
} from '../types/circuit'

export function buildWiringGuide(
  placed: PlacedComponent[],
  wires: Wire[],
  issues: ValidationIssue[],
  rails: RailStatus[],
  boardJumpers: BoardJumper[] = [],
  trackCuts: TrackCut[] = [],
): string {
  const lines: string[] = []
  lines.push('# Electronics Wiring Guide')
  lines.push(`Generated: ${new Date().toLocaleString()}`)
  lines.push('')
  lines.push('## Bill of Materials (on canvas)')
  const counts = new Map<string, number>()
  for (const p of placed) counts.set(p.defId, (counts.get(p.defId) ?? 0) + 1)
  for (const [defId, n] of counts) {
    const d = CATALOG_BY_ID[defId]
    lines.push(`- ${n}× ${d?.name ?? defId}`)
  }
  if (placed.length === 0) lines.push('- (none)')

  lines.push('')
  lines.push('## Off-board wire list')
  if (wires.length === 0) {
    lines.push('- (no wires yet)')
  } else {
    const byId = Object.fromEntries(placed.map((p) => [p.instanceId, p]))
    wires.forEach((w, i) => {
      const a = byId[w.sourceInstanceId]
      const b = byId[w.targetInstanceId]
      const ap = CATALOG_BY_ID[a?.defId ?? '']?.pins.find((p) => p.id === w.sourcePinId)
      const bp = CATALOG_BY_ID[b?.defId ?? '']?.pins.find((p) => p.id === w.targetPinId)
      lines.push(
        `${i + 1}. ${a?.label ?? '?'}.${ap?.name ?? w.sourcePinId}  →  ${b?.label ?? '?'}.${bp?.name ?? w.targetPinId}`,
      )
    })
  }

  lines.push('')
  lines.push('## Zero PCB jumpers (on-board)')
  if (boardJumpers.length === 0) {
    lines.push('- (none)')
  } else {
    const byId = Object.fromEntries(placed.map((p) => [p.instanceId, p]))
    boardJumpers.forEach((j, i) => {
      const board = byId[j.boardInstanceId]
      lines.push(
        `${i + 1}. [${board?.label ?? 'PCB'}] ${stripRowLabel(j.row1)}${j.col1 + 1} ↔ ${stripRowLabel(j.row2)}${j.col2 + 1} (${j.color})`,
      )
    })
  }

  lines.push('')
  lines.push('## Track cuts')
  if (trackCuts.length === 0) {
    lines.push('- (none)')
  } else {
    const byId = Object.fromEntries(placed.map((p) => [p.instanceId, p]))
    trackCuts.forEach((c, i) => {
      const board = byId[c.boardInstanceId]
      lines.push(
        `${i + 1}. [${board?.label ?? 'PCB'}] cut at ${stripRowLabel(c.row)}${c.col + 1}`,
      )
    })
  }

  lines.push('')
  lines.push('## Power rails')
  for (const r of rails) {
    if (r.supplyMa === 0 && r.drawMa === 0) continue
    lines.push(
      `- ${r.rail}: supply ${Math.round(r.supplyMa)} mA, draw ${Math.round(r.drawMa)} mA, headroom ${Math.round(r.headroomMa)} mA${r.overloaded ? ' ⚠ OVERLOADED' : ''}`,
    )
  }

  lines.push('')
  lines.push('## Validation')
  const blockers = issues.filter((i) => i.severity === 'error' || i.severity === 'warning')
  if (blockers.length === 0) {
    lines.push('- No errors or warnings. Safe to proceed carefully with a meter.')
  } else {
    for (const i of blockers) {
      lines.push(`- [${i.severity.toUpperCase()}] ${i.title}: ${i.detail}`)
    }
  }

  lines.push('')
  lines.push('## Suggested physical build order')
  lines.push('1. Mount Zero PCB and mark track cuts first.')
  lines.push('2. Solder on-board jumpers, then components.')
  lines.push('3. Wire common GND across all modules before signal wires.')
  lines.push('4. Set buck converter outputs with a multimeter (no loads attached).')
  lines.push('5. Power sensors / ESP32 on correct rails (3.3V vs 5V).')
  lines.push('6. Add motor drivers last; verify direction with short low-duty PWM tests.')
  lines.push('')
  lines.push('Always double-check polarity with a meter before soldering permanent joints.')

  return lines.join('\n')
}

export function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
