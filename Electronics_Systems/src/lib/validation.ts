import { CATALOG_BY_ID } from '../data/catalog'
import type {
  PinSpec,
  PlacedComponent,
  RailId,
  RailStatus,
  ValidationIssue,
  Wire,
} from '../types/circuit'

function pinOf(instance: PlacedComponent, pinId: string): PinSpec | undefined {
  return CATALOG_BY_ID[instance.defId]?.pins.find((p) => p.id === pinId)
}

function defOf(instance: PlacedComponent) {
  return CATALOG_BY_ID[instance.defId]
}

function voltageFromSource(pin: PinSpec): number | undefined {
  if (pin.voltageOut != null) return pin.voltageOut
  if (pin.role === 'gnd') return 0
  return undefined
}

function checkVoltageMatch(
  src: PinSpec,
  tgt: PinSpec,
  wireId: string,
  srcLabel: string,
  tgtLabel: string,
  /** Prefer net-propagated voltage from live drivers when available */
  netVolts?: number,
): ValidationIssue | null {
  const pinV = voltageFromSource(src)
  const outV = netVolts ?? pinV
  const isPowerish =
    src.role === 'power_out' ||
    (src.role === 'power_in' && src.voltageOut != null) ||
    src.rail != null ||
    netVolts != null

  if (outV == null || tgt.role === 'gnd' || src.role === 'gnd') return null
  if (!isPowerish && tgt.role !== 'power_in') return null

  if (tgt.voltageMax != null && outV > tgt.voltageMax + 0.15) {
    return {
      id: `ov-${wireId}`,
      severity: 'error',
      title: 'Over-voltage',
      detail: `${srcLabel} carries ~${outV}V but ${tgtLabel} max is ${tgt.voltageMax}V. This can destroy the part.`,
      wireId,
    }
  }

  if (tgt.voltageMin != null && outV < tgt.voltageMin - 0.3 && tgt.role === 'power_in') {
    return {
      id: `uv-${wireId}`,
      severity: 'warning',
      title: 'Under-voltage',
      detail: `${srcLabel} provides ~${outV}V but ${tgtLabel} needs at least ${tgt.voltageMin}V.`,
      wireId,
    }
  }

  return null
}

function checkPolarity(
  src: PinSpec,
  tgt: PinSpec,
  wireId: string,
  srcLabel: string,
  tgtLabel: string,
): ValidationIssue | null {
  // Prefer the more specific GND→power message when applicable
  if (src.role === 'gnd' && tgt.role === 'power_in' && tgt.polarity === 'positive') {
    return {
      id: `gndpwr-${wireId}`,
      severity: 'error',
      title: 'GND wired to power input',
      detail: `${srcLabel} (GND) should not feed ${tgtLabel} power pin.`,
      wireId,
    }
  }
  if (tgt.role === 'gnd' && src.role === 'power_in' && src.polarity === 'positive') {
    return {
      id: `gndpwr-${wireId}`,
      severity: 'error',
      title: 'GND wired to power input',
      detail: `${tgtLabel} (GND) should not feed ${srcLabel} power pin.`,
      wireId,
    }
  }
  if (src.polarity === 'positive' && tgt.polarity === 'negative') {
    return {
      id: `pol-${wireId}`,
      severity: 'error',
      title: 'Reversed polarity',
      detail: `Connecting ${srcLabel} (+) to ${tgtLabel} (−). Flip the wire.`,
      wireId,
    }
  }
  if (src.polarity === 'negative' && tgt.polarity === 'positive') {
    return {
      id: `pol2-${wireId}`,
      severity: 'error',
      title: 'Reversed polarity',
      detail: `Connecting ${srcLabel} (−) to ${tgtLabel} (+). Flip the wire.`,
      wireId,
    }
  }
  return null
}

function checkSolarRules(
  placed: PlacedComponent[],
  wires: Wire[],
): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const byId = Object.fromEntries(placed.map((p) => [p.instanceId, p]))

  for (const w of wires) {
    const a = byId[w.sourceInstanceId]
    const b = byId[w.targetInstanceId]
    if (!a || !b) continue
    const da = defOf(a)
    const db = defOf(b)
    if (!da || !db) continue

    const solarTouchesBuck =
      (da.id === 'solar-12v' && db.isBuckConverter) ||
      (db.id === 'solar-12v' && da.isBuckConverter)
    const solarTouchesBattery =
      (da.id === 'solar-12v' && db.id === 'battery-11v1') ||
      (db.id === 'solar-12v' && da.id === 'battery-11v1')

    if (solarTouchesBuck) {
      issues.push({
        id: `solar-buck-${w.id}`,
        severity: 'error',
        title: 'Solar → buck is unsafe',
        detail:
          'A plain buck converter does not current-limit charge or handle panel Voc safely. Use a Charge Controller (PWM/MPPT) between solar and battery.',
        wireId: w.id,
        instanceIds: [a.instanceId, b.instanceId],
      })
    }
    if (solarTouchesBattery) {
      issues.push({
        id: `solar-bat-${w.id}`,
        severity: 'error',
        title: 'Solar wired directly to battery',
        detail:
          'Connect Solar → Charge Controller → Battery. Direct solar→battery can overcharge / overvolt the pack.',
        wireId: w.id,
        instanceIds: [a.instanceId, b.instanceId],
      })
    }
  }

  const hasSolar = placed.some((p) => p.defId === 'solar-12v')
  const hasBattery = placed.some((p) => p.defId === 'battery-11v1')
  const hasCC = placed.some((p) => defOf(p)?.isChargeController)
  if (hasSolar && hasBattery && !hasCC) {
    issues.push({
      id: 'missing-cc',
      severity: 'warning',
      title: 'Charge controller missing',
      detail:
        'You have solar + battery on the canvas but no charge controller block. Add one before charging.',
      instanceIds: placed
        .filter((p) => p.defId === 'solar-12v' || p.defId === 'battery-11v1')
        .map((p) => p.instanceId),
    })
  }

  return issues
}

function checkGpioOvervoltage(
  placed: PlacedComponent[],
  wires: Wire[],
  nets: NetIndex,
  energized: Set<string>,
): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const byId = nets.byId

  for (const w of wires) {
    for (const [fromInst, fromPin, toInst, toPin] of [
      [w.sourceInstanceId, w.sourcePinId, w.targetInstanceId, w.targetPinId],
      [w.targetInstanceId, w.targetPinId, w.sourceInstanceId, w.sourcePinId],
    ] as const) {
      const srcC = byId[fromInst]
      const tgtC = byId[toInst]
      if (!srcC || !tgtC) continue
      if (tgtC.defId !== 'esp32-devkit') continue
      const sp = pinOf(srcC, fromPin)
      const tp = pinOf(tgtC, toPin)
      if (!sp || !tp) continue
      if (!['signal', 'data', 'analog', 'pwm'].includes(tp.role)) continue

      const driveV =
        sp.voltageOut ??
        netDrivingVoltage(nets, placed, fromInst, fromPin, energized)
      if (driveV != null && driveV > 3.6) {
        issues.push({
          id: `gpio-${w.id}-${toPin}`,
          severity: 'error',
          title: 'ESP32 GPIO over-voltage',
          detail: `${srcC.label} ${sp.name} (~${driveV}V) → ESP32 ${tp.name}. GPIOs are 3.3V only.`,
          wireId: w.id,
        })
      }
      // ACS712 analog to ESP32 without mention of divider
      if (srcC.defId === 'acs712' && sp.id === 'OUT' && tp.role === 'analog') {
        issues.push({
          id: `acs-adc-${w.id}`,
          severity: 'warning',
          title: 'ACS712 → ESP32 ADC needs divider',
          detail:
            'ACS712 OUT can swing toward 5V. ESP32 ADC max is 3.3V — use a resistor divider or 3.3V-safe module.',
          wireId: w.id,
        })
      }
    }
  }
  return issues
}

function checkMissingGround(
  placed: PlacedComponent[],
  wires: Wire[],
): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const nets = buildNetIndex(placed, wires)
  const { byId } = nets

  // Components share ground when any of their GND/negative pins sit on the same
  // electrical net (including paths through jumpers / fuses / cables).
  const parent = new Map<string, string>()
  const find = (x: string): string => {
    const p = parent.get(x) ?? x
    if (p !== x) {
      const r = find(p)
      parent.set(x, r)
      return r
    }
    return x
  }
  const union = (a: string, b: string) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent.set(ra, rb)
  }
  for (const p of placed) parent.set(p.instanceId, p.instanceId)

  const groundLinked = new Set<string>()
  const gndPinsByNet = new Map<string, string[]>()

  for (const p of placed) {
    const d = defOf(p)
    if (!d) continue
    for (const pin of d.pins) {
      if (pin.role !== 'gnd' && pin.polarity !== 'negative') continue
      const root = nets.find(nets.key(p.instanceId, pin.id))
      const list = gndPinsByNet.get(root) ?? []
      list.push(p.instanceId)
      gndPinsByNet.set(root, list)
    }
  }

  for (const instances of gndPinsByNet.values()) {
    if (instances.length < 2) continue
    for (let i = 1; i < instances.length; i++) {
      union(instances[0], instances[i])
    }
    for (const id of instances) groundLinked.add(id)
  }

  for (const w of wires) {
    const a = byId[w.sourceInstanceId]
    const b = byId[w.targetInstanceId]
    if (!a || !b) continue
    const pa = pinOf(a, w.sourcePinId)
    const pb = pinOf(b, w.targetPinId)
    const signalish =
      ['signal', 'data', 'analog', 'pwm'].includes(pa?.role ?? '') ||
      ['signal', 'data', 'analog', 'pwm'].includes(pb?.role ?? '')
    const powerish =
      pa?.role === 'power_out' ||
      pb?.role === 'power_out' ||
      pa?.role === 'power_in' ||
      pb?.role === 'power_in'

    if (!signalish && !powerish) continue
    if (pa?.role === 'gnd' || pb?.role === 'gnd') continue

    const sameGnd =
      find(a.instanceId) === find(b.instanceId) && groundLinked.has(a.instanceId)
    if (!sameGnd) {
      issues.push({
        id: `nognd-${w.id}`,
        severity: 'warning',
        title: 'Missing common ground',
        detail: `${a.label} ↔ ${b.label} have a signal/power wire but no shared GND path yet. Add GND↔GND.`,
        wireId: w.id,
        instanceIds: [a.instanceId, b.instanceId],
      })
    }
  }

  return issues
}

/**
 * Components whose pins are internally shorted together (wire passes straight
 * through), so power propagates across them: jumpers, cables, fuses,
 * and the rocker switch (assumed ON).
 *
 * Terminal blocks are NOT listed — each PCT-218 pole is an independent clamp.
 */
const PASSTHROUGH_GROUPS: Record<string, string[][]> = {
  'jumper-ff': [['A', 'B']],
  'jumper-mm': [['A', 'B']],
  'copper-cable': [['A', 'B']],
  'fuse-0001': [['A', 'B']],
  'fuse-sato': [['A', 'B']],
  'rocker-3pin': [['COM', 'NO']],
  'barrel-female': [], // tip and sleeve stay separate
  'barrel-male': [],
  'xt60-connector': [], // + and − stay separate
}

type NetIndex = {
  find: (x: string) => string
  key: (inst: string, pin: string) => string
  byId: Record<string, PlacedComponent>
}

/** Build pin-level electrical nets (wires + internal pass-throughs). */
function buildNetIndex(placed: PlacedComponent[], wires: Wire[]): NetIndex {
  const byId = Object.fromEntries(placed.map((p) => [p.instanceId, p]))
  const parent = new Map<string, string>()
  const key = (inst: string, pin: string) => `${inst}::${pin}`
  const find = (x: string): string => {
    const p = parent.get(x) ?? x
    if (p === x) return x
    const r = find(p)
    parent.set(x, r)
    return r
  }
  const union = (a: string, b: string) => {
    const ra = find(a)
    const rb = find(b)
    if (ra !== rb) parent.set(ra, rb)
  }

  for (const w of wires) {
    if (!byId[w.sourceInstanceId] || !byId[w.targetInstanceId]) continue
    union(
      key(w.sourceInstanceId, w.sourcePinId),
      key(w.targetInstanceId, w.targetPinId),
    )
  }

  for (const p of placed) {
    const groups = PASSTHROUGH_GROUPS[p.defId]
    if (!groups) continue
    for (const group of groups) {
      for (let i = 1; i < group.length; i++) {
        union(key(p.instanceId, group[0]), key(p.instanceId, group[i]))
      }
    }
  }

  return { find, key, byId }
}

/**
 * Max driving voltage on a pin's net from live intrinsic sources / energized
 * converter outputs. Pads and unpowered labels do not contribute.
 */
function netDrivingVoltage(
  nets: NetIndex,
  placed: PlacedComponent[],
  inst: string,
  pinId: string,
  energized: Set<string>,
): number | undefined {
  const root = nets.find(nets.key(inst, pinId))
  let maxV: number | undefined

  for (const p of placed) {
    const d = defOf(p)
    if (!d) continue
    const hasPowerIn = d.pins.some((pin) => pin.role === 'power_in')
    const intrinsic = d.category === 'power' && !hasPowerIn
    const canDrive = intrinsic || energized.has(p.instanceId)
    if (!canDrive) continue
    for (const pin of d.pins) {
      if (pin.role !== 'power_out' || pin.voltageOut == null) continue
      if (nets.find(nets.key(p.instanceId, pin.id)) !== root) continue
      maxV = maxV == null ? pin.voltageOut : Math.max(maxV, pin.voltageOut)
    }
  }
  return maxV
}

/** Which converters are energized (input net fed by a live source). */
function computeEnergized(
  placed: PlacedComponent[],
  nets: NetIndex,
): { energized: Set<string>; isLive: (inst: string, pin: string) => boolean } {
  const liveNets = new Set<string>()
  const markLive = (inst: string, pin: string) =>
    liveNets.add(nets.find(nets.key(inst, pin)))
  const isLive = (inst: string, pin: string) =>
    liveNets.has(nets.find(nets.key(inst, pin)))

  for (const p of placed) {
    const d = defOf(p)
    if (!d) continue
    const hasPowerIn = d.pins.some((pin) => pin.role === 'power_in')
    if (d.category === 'power' && d.producesRails && !hasPowerIn) {
      for (const pin of d.pins) {
        if (pin.role === 'power_out') markLive(p.instanceId, pin.id)
      }
    }
  }

  const energized = new Set<string>()
  for (let pass = 0; pass < placed.length + 1; pass++) {
    let changed = false
    for (const p of placed) {
      if (energized.has(p.instanceId)) continue
      const d = defOf(p)
      if (!d) continue
      const powerIns = d.pins.filter((pin) => pin.role === 'power_in')
      const outs = d.pins.filter(
        (pin) => pin.role === 'power_out' || (pin.role === 'motor' && !pin.currentDrawMa),
      )
      if (powerIns.length === 0 || outs.length === 0) continue
      if (!powerIns.some((pin) => isLive(p.instanceId, pin.id))) continue
      energized.add(p.instanceId)
      for (const pin of outs) markLive(p.instanceId, pin.id)
      changed = true
    }
    if (!changed) break
  }

  return { energized, isLive }
}

/**
 * Connectivity-aware power flow. A rail only shows supply/draw when there is
 * an actual wired path from a real source (battery / solar) through any
 * converters to the load. Zero PCB rail pads are just pads — they are live
 * only when something live feeds them.
 */
export function computeRailStatus(
  placed: PlacedComponent[],
  wires: Wire[],
): RailStatus[] {
  const rails: RailId[] = ['12V', '5V', '3.3V', 'BAT', 'SOLAR']
  const nets = buildNetIndex(placed, wires)

  const result: RailStatus[] = rails.map((rail) => ({
    rail,
    voltage: rail === '3.3V' ? 3.3 : rail === '5V' ? 5 : rail === 'SOLAR' ? 12 : 11.1,
    supplyMa: 0,
    drawMa: 0,
    headroomMa: 0,
    overloaded: false,
    sources: [],
    loads: [],
    feedsDownstream: false,
  }))
  const map = Object.fromEntries(result.map((r) => [r.rail, r])) as Record<
    RailId,
    RailStatus
  >

  const { energized, isLive } = computeEnergized(placed, nets)

  const hasBattery = placed.some((p) => p.defId === 'battery-11v1')

  // ── Supply: intrinsic sources + energized regulators (not distributors) ──
  for (const p of placed) {
    const d = defOf(p)
    if (!d || !d.producesRails || !d.supplyCurrentMa) continue
    const hasPowerIn = d.pins.some((pin) => pin.role === 'power_in')
    const intrinsic = d.category === 'power' && !hasPowerIn
    if (!intrinsic && !energized.has(p.instanceId)) continue

    // PDB redistributes battery current — don't double-count with the pack.
    if (d.id === 'pdb-xt60') continue
    // Charge controller charges the pack; when a battery is present it is not
    // an extra parallel supply for the BAT rail budget.
    if (d.isChargeController && hasBattery) {
      // Still credit Load+ / 12V if produced — only skip BAT rail
      for (const r of d.producesRails) {
        if (r === 'BAT') continue
        map[r].supplyMa += d.supplyCurrentMa
        map[r].sources.push(p.label)
      }
      continue
    }

    for (const r of d.producesRails) {
      map[r].supplyMa += d.supplyCurrentMa
      map[r].sources.push(p.label)
    }
  }

  // ── Loads: power_in pins that draw current AND sit on a live net ──
  const countedLoads = new Set<string>()
  for (const p of placed) {
    const d = defOf(p)
    if (!d) continue
    for (const pin of d.pins) {
      if (pin.role !== 'power_in' || !pin.currentDrawMa) continue
      if (!isLive(p.instanceId, pin.id)) continue
      const rail = pin.rail
      if (!rail || !map[rail]) continue
      const k = `${p.instanceId}:${pin.id}`
      if (countedLoads.has(k)) continue
      countedLoads.add(k)
      map[rail].drawMa += pin.currentDrawMa
      map[rail].loads.push(`${p.label}.${pin.name} (${pin.currentDrawMa} mA)`)
    }
  }

  // Motor loads: motor pins wired to a live net (e.g. via BTS7960 M+)
  for (const p of placed) {
    const d = defOf(p)
    if (!d) continue
    for (const pin of d.pins) {
      if (pin.role !== 'motor' || !pin.currentDrawMa) continue
      if (!isLive(p.instanceId, pin.id)) continue
      const rail = pin.rail ?? '12V'
      const k = `${p.instanceId}:motor`
      if (countedLoads.has(k)) continue
      countedLoads.add(k)
      map[rail].drawMa += pin.currentDrawMa
      map[rail].loads.push(`${p.label} (~${pin.currentDrawMa} mA)`)
    }
  }

  // Mark rails whose power is consumed by a downstream energized converter,
  // so a source rail (e.g. BAT / 12V feeding a buck) doesn't look "unused".
  for (const p of placed) {
    if (!energized.has(p.instanceId)) continue
    const d = defOf(p)
    if (!d) continue
    for (const pin of d.pins) {
      if (pin.role !== 'power_in') continue
      if (!isLive(p.instanceId, pin.id)) continue
      if (pin.rail && map[pin.rail]) map[pin.rail].feedsDownstream = true
    }
  }

  for (const r of result) {
    r.headroomMa = r.supplyMa - r.drawMa
    r.overloaded = r.supplyMa > 0 && r.drawMa > r.supplyMa
  }
  return result
}

export function validateCircuit(
  placed: PlacedComponent[],
  wires: Wire[],
): ValidationIssue[] {
  const issues: ValidationIssue[] = []
  const nets = buildNetIndex(placed, wires)
  const { energized } = computeEnergized(placed, nets)
  const byId = nets.byId

  for (const w of wires) {
    const a = byId[w.sourceInstanceId]
    const b = byId[w.targetInstanceId]
    if (!a || !b) continue
    const pa = pinOf(a, w.sourcePinId)
    const pb = pinOf(b, w.targetPinId)
    if (!pa || !pb) continue

    const aLabel = `${a.label}.${pa.name}`
    const bLabel = `${b.label}.${pb.name}`
    const netVa = netDrivingVoltage(
      nets,
      placed,
      w.sourceInstanceId,
      w.sourcePinId,
      energized,
    )
    const netVb = netDrivingVoltage(
      nets,
      placed,
      w.targetInstanceId,
      w.targetPinId,
      energized,
    )

    // Check both directions for voltage (source → load)
    for (const [src, tgt, sL, tL, netV] of [
      [pa, pb, aLabel, bLabel, netVa],
      [pb, pa, bLabel, aLabel, netVb],
    ] as const) {
      const v = checkVoltageMatch(src, tgt, w.id, sL, tL, netV)
      if (v) issues.push(v)
    }

    const pol = checkPolarity(pa, pb, w.id, aLabel, bLabel)
    if (pol) issues.push(pol)
  }

  issues.push(...checkSolarRules(placed, wires))
  issues.push(...checkGpioOvervoltage(placed, wires, nets, energized))
  issues.push(...checkMissingGround(placed, wires))

  const rails = computeRailStatus(placed, wires)
  for (const r of rails) {
    if (r.overloaded) {
      issues.push({
        id: `rail-ovl-${r.rail}`,
        severity: 'error',
        title: `${r.rail} rail overloaded`,
        detail: `Draw ${Math.round(r.drawMa)} mA exceeds supply ${Math.round(r.supplyMa)} mA. Reduce loads or add a bigger supply / second buck.`,
        rail: r.rail,
      })
    } else if (r.supplyMa > 0 && r.drawMa > r.supplyMa * 0.8) {
      issues.push({
        id: `rail-tight-${r.rail}`,
        severity: 'warning',
        title: `${r.rail} rail near capacity`,
        detail: `Using ${Math.round(r.drawMa)} / ${Math.round(r.supplyMa)} mA (${Math.round((r.drawMa / r.supplyMa) * 100)}%). Leave headroom for motor stalls / peaks.`,
        rail: r.rail,
      })
    }
  }

  // Suggested architecture hint when both bucks present
  const hasXl = placed.some((p) => p.defId === 'xl4016-buck')
  const has4015 = placed.some((p) => p.defId === 'buck-4015')
  const hasBat = placed.some((p) => p.defId === 'battery-11v1')
  if (hasBat && hasXl && has4015) {
    issues.push({
      id: 'arch-hint',
      severity: 'info',
      title: 'Recommended power chain',
      detail:
        'Battery/PDB → 12V rail → XL4016 (12V→5V) → Buck 4015 (5V→3.3V). Sensors: 5V devices on 5V rail, 3.3V sensors on 3.3V rail. Common GND everywhere.',
    })
  }

  if (placed.length === 0) {
    issues.push({
      id: 'empty',
      severity: 'info',
      title: 'Canvas is empty',
      detail: 'Add components from your inventory, then drag wires between pins.',
    })
  }

  // Deduplicate by id
  const seen = new Set<string>()
  return issues.filter((i) => {
    if (seen.has(i.id)) return false
    seen.add(i.id)
    return true
  })
}
export function connectionSuggestions(defId: string): string[] {
  const tips: Record<string, string[]> = {
    'esp32-devkit': [
      'Power ESP32 from 5V rail (VIN) or USB; use 3V3 only for light sensors.',
      'I²C: GPIO21=SDA, GPIO22=SCL to SCD4X / VEML7700 / BNO055.',
      'Never connect 5V or 12V to GPIO.',
    ],
    'nova-pm': [
      'Nova PM VCC → 5V rail, GND → common GND.',
      'TX → ESP32 RX (UART). Logic is 3.3V-friendly.',
    ],
    scd4x: ['VDD → 3.3V, GND → GND, SDA/SCL → ESP32 GPIO21/22.'],
    veml7700: ['VDD → 3.3V only (max 3.6V). I²C to ESP32.'],
    bno055: ['VIN → 5V or 3.3V (check breakout). SDA/SCL → ESP32.'],
    acs712: [
      'VCC → 5V. Put IP+/IP− in series with the motor supply wire.',
      'OUT → ESP32 ADC only through a voltage divider.',
    ],
    'xl4016-buck': [
      'IN+ ← 12V/BAT rail, OUT+ → 5V rail. Set voltage with a meter first.',
      'Not a charge controller — do not put this between solar and battery.',
    ],
    'buck-4015': ['IN+ ← 5V rail, OUT+ → 3.3V rail for sensors.'],
    'charge-controller': [
      'Solar+ → Solar IN, Battery → Battery OUT, optional Load → 12V distribution.',
    ],
    'solar-12v': [
      'Must go to Charge Controller Solar IN — never straight to battery or buck.',
    ],
    'battery-11v1': [
      'BAT+ → PDB XT60 or rocker switch → 12V distribution.',
      'Charge only via charge controller.',
    ],
    bts7960: [
      'B+ ← 12V (via PDB), VCC ← 5V logic, RPWM/LPWM ← ESP32 PWM pins.',
      'M+/M− → DC motor. Share GND with ESP32.',
    ],
    'dc-motor': ['Wire only to BTS7960 M+/M− — never to ESP32 GPIO.'],
    servo: [
      'VCC ← stout 5V supply (not ESP32 3V3). Signal ← ESP32 PWM. Common GND.',
    ],
    'pdb-xt60': [
      'XT60 ← battery, Dist+ → motor drivers / 12V rail, optional BEC 5V.',
    ],
  }
  return (
    tips[defId] ?? [
      'Check datasheet voltage before soldering. Always common-ground.',
    ]
  )
}
