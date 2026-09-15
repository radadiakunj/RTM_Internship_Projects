import { create } from 'zustand'
import { CATALOG_BY_ID } from '../data/catalog'
import { computeRailStatus, validateCircuit } from './validation'
import type {
  BoardJumper,
  BoardTool,
  PlacedComponent,
  RailStatus,
  TrackCut,
  ValidationIssue,
  Wire,
} from '../types/circuit'
import { JUMPER_COLORS } from '../types/circuit'

function uid(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

interface HoleRef {
  boardInstanceId: string
  row: number
  col: number
}

interface CircuitState {
  placed: PlacedComponent[]
  wires: Wire[]
  boardJumpers: BoardJumper[]
  trackCuts: TrackCut[]
  boardTool: BoardTool
  jumperColor: string
  pendingHole: HoleRef | null
  selectedInstanceId: string | null
  highlightedWireId: string | null
  issues: ValidationIssue[]
  rails: RailStatus[]
  mode: 'manual' | 'guided' | 'learn'
  theme: 'light' | 'dark'
  setTheme: (theme: 'light' | 'dark') => void
  addComponent: (defId: string, x?: number, y?: number) => string | null
  removeComponent: (instanceId: string) => void
  moveComponent: (instanceId: string, x: number, y: number) => void
  setSelected: (instanceId: string | null) => void
  setHighlightedWire: (wireId: string | null) => void
  addWire: (
    sourceInstanceId: string,
    sourcePinId: string,
    targetInstanceId: string,
    targetPinId: string,
  ) => void
  removeWire: (wireId: string) => void
  setBoardTool: (tool: BoardTool) => void
  setJumperColor: (color: string) => void
  clickBoardHole: (boardInstanceId: string, row: number, col: number) => void
  removeBoardJumper: (id: string) => void
  clearPendingHole: () => void
  clearCanvas: () => void
  setMode: (mode: 'manual' | 'guided' | 'learn') => void
  usedCount: (defId: string) => number
  remainingCount: (defId: string) => number
  revalidate: () => void
}

function refresh(placed: PlacedComponent[], wires: Wire[]) {
  return {
    issues: validateCircuit(placed, wires),
    rails: computeRailStatus(placed, wires),
  }
}

export const useCircuitStore = create<CircuitState>((set, get) => ({
  placed: [],
  wires: [],
  boardJumpers: [],
  trackCuts: [],
  boardTool: 'jumper',
  jumperColor: JUMPER_COLORS[0],
  pendingHole: null,
  selectedInstanceId: null,
  highlightedWireId: null,
  issues: validateCircuit([], []),
  rails: computeRailStatus([], []),
  mode: 'manual',
  theme:
    (localStorage.getItem('benchwire-theme') as 'light' | 'dark' | null) ?? 'light',

  setTheme: (theme) => {
    localStorage.setItem('benchwire-theme', theme)
    document.documentElement.dataset.theme = theme
    set({ theme })
  },

  usedCount: (defId) => get().placed.filter((p) => p.defId === defId).length,

  remainingCount: (defId) => {
    const def = CATALOG_BY_ID[defId]
    if (!def) return 0
    return Math.max(0, def.qtyAvailable - get().usedCount(defId))
  },

  addComponent: (defId, x = 120, y = 120) => {
    const def = CATALOG_BY_ID[defId]
    if (!def) return null
    if (get().remainingCount(defId) <= 0) return null
    const n = get().usedCount(defId) + 1
    const instance: PlacedComponent = {
      instanceId: uid('c'),
      defId,
      label: def.qtyAvailable > 1 ? `${def.shortName} #${n}` : def.shortName,
      x: x + (n - 1) * 24,
      y: y + (n - 1) * 18,
    }
    const placed = [...get().placed, instance]
    set({ placed, selectedInstanceId: instance.instanceId, ...refresh(placed, get().wires) })
    return instance.instanceId
  },

  removeComponent: (instanceId) => {
    const placed = get().placed.filter((p) => p.instanceId !== instanceId)
    const wires = get().wires.filter(
      (w) => w.sourceInstanceId !== instanceId && w.targetInstanceId !== instanceId,
    )
    const boardJumpers = get().boardJumpers.filter((j) => j.boardInstanceId !== instanceId)
    const trackCuts = get().trackCuts.filter((c) => c.boardInstanceId !== instanceId)
    set({
      placed,
      wires,
      boardJumpers,
      trackCuts,
      pendingHole:
        get().pendingHole?.boardInstanceId === instanceId ? null : get().pendingHole,
      selectedInstanceId:
        get().selectedInstanceId === instanceId ? null : get().selectedInstanceId,
      ...refresh(placed, wires),
    })
  },

  moveComponent: (instanceId, x, y) => {
    const placed = get().placed.map((p) =>
      p.instanceId === instanceId ? { ...p, x, y } : p,
    )
    set({ placed })
  },

  setSelected: (instanceId) => set({ selectedInstanceId: instanceId }),
  setHighlightedWire: (wireId) => set({ highlightedWireId: wireId }),

  addWire: (sourceInstanceId, sourcePinId, targetInstanceId, targetPinId) => {
    if (sourceInstanceId === targetInstanceId && sourcePinId === targetPinId) return
    const exists = get().wires.some(
      (w) =>
        (w.sourceInstanceId === sourceInstanceId &&
          w.sourcePinId === sourcePinId &&
          w.targetInstanceId === targetInstanceId &&
          w.targetPinId === targetPinId) ||
        (w.sourceInstanceId === targetInstanceId &&
          w.sourcePinId === targetPinId &&
          w.targetInstanceId === sourceInstanceId &&
          w.targetPinId === sourcePinId),
    )
    if (exists) return
    const wire: Wire = {
      id: uid('w'),
      sourceInstanceId,
      sourcePinId,
      targetInstanceId,
      targetPinId,
    }
    const wires = [...get().wires, wire]
    set({ wires, ...refresh(get().placed, wires) })
  },

  removeWire: (wireId) => {
    const wires = get().wires.filter((w) => w.id !== wireId)
    set({ wires, highlightedWireId: null, ...refresh(get().placed, wires) })
  },

  setBoardTool: (tool) => set({ boardTool: tool, pendingHole: null }),
  setJumperColor: (color) => set({ jumperColor: color }),
  clearPendingHole: () => set({ pendingHole: null }),

  clickBoardHole: (boardInstanceId, row, col) => {
    const tool = get().boardTool

    if (tool === 'erase') {
      const jumpers = get().boardJumpers.filter(
        (j) =>
          !(
            j.boardInstanceId === boardInstanceId &&
            ((j.row1 === row && j.col1 === col) || (j.row2 === row && j.col2 === col))
          ),
      )
      const cuts = get().trackCuts.filter(
        (c) => !(c.boardInstanceId === boardInstanceId && c.row === row && c.col === col),
      )
      set({ boardJumpers: jumpers, trackCuts: cuts, pendingHole: null })
      return
    }

    if (tool === 'cut') {
      const exists = get().trackCuts.some(
        (c) => c.boardInstanceId === boardInstanceId && c.row === row && c.col === col,
      )
      if (exists) {
        set({
          trackCuts: get().trackCuts.filter(
            (c) =>
              !(c.boardInstanceId === boardInstanceId && c.row === row && c.col === col),
          ),
        })
      } else {
        set({
          trackCuts: [
            ...get().trackCuts,
            { id: uid('cut'), boardInstanceId, row, col },
          ],
        })
      }
      return
    }

    // jumper tool
    const pending = get().pendingHole
    if (
      !pending ||
      pending.boardInstanceId !== boardInstanceId
    ) {
      set({ pendingHole: { boardInstanceId, row, col } })
      return
    }

    if (pending.row === row && pending.col === col) {
      set({ pendingHole: null })
      return
    }

    const duplicate = get().boardJumpers.some(
      (j) =>
        j.boardInstanceId === boardInstanceId &&
        ((j.row1 === pending.row &&
          j.col1 === pending.col &&
          j.row2 === row &&
          j.col2 === col) ||
          (j.row1 === row &&
            j.col1 === col &&
            j.row2 === pending.row &&
            j.col2 === pending.col)),
    )
    if (!duplicate) {
      const jumper: BoardJumper = {
        id: uid('j'),
        boardInstanceId,
        row1: pending.row,
        col1: pending.col,
        row2: row,
        col2: col,
        color: get().jumperColor,
      }
      set({ boardJumpers: [...get().boardJumpers, jumper], pendingHole: null })
    } else {
      set({ pendingHole: null })
    }
  },

  removeBoardJumper: (id) => {
    set({ boardJumpers: get().boardJumpers.filter((j) => j.id !== id) })
  },

  clearCanvas: () => {
    set({
      placed: [],
      wires: [],
      boardJumpers: [],
      trackCuts: [],
      pendingHole: null,
      selectedInstanceId: null,
      highlightedWireId: null,
      ...refresh([], []),
    })
  },

  setMode: (mode) => set({ mode }),

  revalidate: () => set(refresh(get().placed, get().wires)),
}))
