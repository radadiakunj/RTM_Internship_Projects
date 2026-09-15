export type PinRole =
  | 'power_in'
  | 'power_out'
  | 'gnd'
  | 'signal'
  | 'data'
  | 'analog'
  | 'pwm'
  | 'motor'

export type RailId = '12V' | '5V' | '3.3V' | 'BAT' | 'SOLAR'

export type ComponentCategory =
  | 'mcu'
  | 'sensor'
  | 'power'
  | 'motor'
  | 'driver'
  | 'passive'
  | 'connector'
  | 'board'
  | 'actuator'
  | 'misc'

export interface PinSpec {
  id: string
  name: string
  role: PinRole
  /** Acceptable input voltage range (for power_in / signal that care) */
  voltageMin?: number
  voltageMax?: number
  /** Nominal output voltage (for power_out) */
  voltageOut?: number
  /** Typical current draw from this pin when used as load (mA) */
  currentDrawMa?: number
  /** Max current this pin can source/sink (mA) */
  currentMaxMa?: number
  /** Which rail this pin belongs to when powered */
  rail?: RailId
  polarity?: 'positive' | 'negative' | 'bipolar' | 'none'
  notes?: string
}

export interface ComponentDef {
  id: string
  name: string
  shortName: string
  category: ComponentCategory
  description: string
  qtyAvailable: number
  pins: PinSpec[]
  /** Continuous current this block can supply (mA) if it is a source */
  supplyCurrentMa?: number
  /** Output rail(s) this power block produces */
  producesRails?: RailId[]
  /** Input rail this power block expects */
  consumesRail?: RailId
  isChargeController?: boolean
  isBuckConverter?: boolean
  color: string
  notes?: string
  /** Stripboard grid (Zero PCB) — rows share copper horizontally */
  boardGrid?: { cols: number; rows: number }
}

export interface PlacedComponent {
  instanceId: string
  defId: string
  label: string
  x: number
  y: number
}

export interface Wire {
  id: string
  sourceInstanceId: string
  sourcePinId: string
  targetInstanceId: string
  targetPinId: string
}

/** Hookup / jumper wire drawn between two holes on a Zero PCB (DIYLC-style) */
export interface BoardJumper {
  id: string
  boardInstanceId: string
  row1: number
  col1: number
  row2: number
  col2: number
  color: string
}

/** Copper-strip break at a hole (DIYLC track cut) */
export interface TrackCut {
  id: string
  boardInstanceId: string
  row: number
  col: number
}

export type BoardTool = 'jumper' | 'cut' | 'erase'

export const JUMPER_COLORS = [
  '#3CCB3C', // bright green (DIYLC hookup wire)
  '#E03131', // red
  '#1E6FD9', // blue
  '#222222', // black
  '#F5C518', // yellow
  '#8E44AD', // purple
  '#F07818', // orange
  '#FFFFFF', // white
] as const

export type ValidationSeverity = 'error' | 'warning' | 'info' | 'ok'

export interface ValidationIssue {
  id: string
  severity: ValidationSeverity
  title: string
  detail: string
  wireId?: string
  instanceIds?: string[]
  rail?: RailId
}

export interface RailStatus {
  rail: RailId
  voltage: number
  supplyMa: number
  drawMa: number
  headroomMa: number
  overloaded: boolean
  sources: string[]
  loads: string[]
  /** This rail's power is being consumed downstream by an energized converter */
  feedsDownstream: boolean
}
