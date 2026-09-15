import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type OnConnect,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { CATALOG_BY_ID } from '../../data/catalog'
import { useCircuitStore } from '../../lib/store'
import { ComponentNode, type CircuitNodeData } from './ComponentNode'
import { ZeroPcbNode } from './ZeroPcbNode'
import './CircuitCanvas.css'

const nodeTypes = { component: ComponentNode, zeroPcb: ZeroPcbNode }

export function CircuitCanvas() {
  const placed = useCircuitStore((s) => s.placed)
  const wires = useCircuitStore((s) => s.wires)
  const issues = useCircuitStore((s) => s.issues)
  const highlightedWireId = useCircuitStore((s) => s.highlightedWireId)
  const selectedInstanceId = useCircuitStore((s) => s.selectedInstanceId)
  const addWire = useCircuitStore((s) => s.addWire)
  const moveComponent = useCircuitStore((s) => s.moveComponent)
  const setSelected = useCircuitStore((s) => s.setSelected)
  const removeWire = useCircuitStore((s) => s.removeWire)
  const removeComponent = useCircuitStore((s) => s.removeComponent)

  const errorWireIds = useMemo(() => {
    const set = new Set<string>()
    for (const i of issues) {
      if ((i.severity === 'error' || i.severity === 'warning') && i.wireId) {
        set.add(i.wireId)
      }
    }
    return set
  }, [issues])

  const initialNodes: Node[] = useMemo(
    () =>
      placed.map((p) => {
        const def = CATALOG_BY_ID[p.defId]
        const isBoard = def?.category === 'board' && !!def.boardGrid
        return {
          id: p.instanceId,
          type: isBoard ? 'zeroPcb' : 'component',
          position: { x: p.x, y: p.y },
          data: {
            instanceId: p.instanceId,
            defId: p.defId,
            label: p.label,
          } satisfies CircuitNodeData,
          selected: p.instanceId === selectedInstanceId,
        }
      }),
    [placed, selectedInstanceId],
  )

  const theme = useCircuitStore((s) => s.theme)
  const dark = theme === 'dark'
  const [cutMode, setCutMode] = useState(false)

  const initialEdges: Edge[] = useMemo(
    () =>
      wires.map((w) => {
        const bad = errorWireIds.has(w.id)
        const hi = highlightedWireId === w.id
        return {
          id: w.id,
          source: w.sourceInstanceId,
          sourceHandle: w.sourcePinId,
          target: w.targetInstanceId,
          targetHandle: w.targetPinId,
          animated: hi || bad,
          label: cutMode && hi ? '✂ cut' : undefined,
          labelStyle: { fontSize: 11, fontWeight: 700, fill: dark ? '#ff7b87' : '#c1121f' },
          labelBgStyle: {
            fill: dark ? '#1a222c' : '#fffdf8',
            stroke: dark ? '#ff7b87' : '#c1121f',
          },
          style: {
            stroke:
              cutMode && hi
                ? dark
                  ? '#FF7B87'
                  : '#C1121F'
                : bad
                  ? dark
                    ? '#FF7B87'
                    : '#C1121F'
                  : hi
                    ? '#C17F3E'
                    : dark
                      ? '#9DB8D8'
                      : '#1D3557',
            strokeWidth: hi || bad ? 3 : 2,
            strokeDasharray: cutMode && hi ? '6 4' : undefined,
          },
        }
      }),
    [wires, errorWireIds, highlightedWireId, dark, cutMode],
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useEffect(() => {
    setNodes(initialNodes)
  }, [initialNodes, setNodes])

  useEffect(() => {
    setEdges(initialEdges)
  }, [initialEdges, setEdges])

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return
      if (!connection.sourceHandle || !connection.targetHandle) return
      addWire(
        connection.source,
        connection.sourceHandle,
        connection.target,
        connection.targetHandle,
      )
    },
    [addWire],
  )

  const onNodeDragStop = useCallback(
    (_e: MouseEvent | TouchEvent, node: Node) => {
      moveComponent(node.id, node.position.x, node.position.y)
    },
    [moveComponent],
  )

  const onNodeClick = useCallback(
    (_e: React.MouseEvent, node: Node) => {
      setSelected(node.id)
    },
    [setSelected],
  )

  const onPaneClick = useCallback(() => setSelected(null), [setSelected])

  const onEdgesDelete = useCallback(
    (deleted: Edge[]) => {
      for (const e of deleted) removeWire(e.id)
    },
    [removeWire],
  )

  const setHighlightedWire = useCircuitStore((s) => s.setHighlightedWire)

  const onEdgeClick = useCallback(
    (e: React.MouseEvent, edge: Edge) => {
      if (cutMode) {
        e.stopPropagation()
        removeWire(edge.id)
      }
    },
    [cutMode, removeWire],
  )

  const onEdgeMouseEnter = useCallback(
    (_e: React.MouseEvent, edge: Edge) => setHighlightedWire(edge.id),
    [setHighlightedWire],
  )

  const onEdgeMouseLeave = useCallback(
    () => setHighlightedWire(null),
    [setHighlightedWire],
  )

  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      for (const n of deleted) removeComponent(n.id)
    },
    [removeComponent],
  )

  return (
    <div className={`circuit-canvas ${cutMode ? 'cut-mode' : ''}`}>
      <div className="circuit-canvas__toolbar">
        <button
          type="button"
          className={`cut-toggle ${cutMode ? 'active' : ''}`}
          onClick={() => setCutMode((v) => !v)}
          title="Toggle wire cutter: click any wire to cut it"
        >
          ✂ {cutMode ? 'Cutting… click a wire' : 'Cut wire'}
        </button>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onEdgesDelete={onEdgesDelete}
        onNodesDelete={onNodesDelete}
        onEdgeClick={onEdgeClick}
        onEdgeMouseEnter={onEdgeMouseEnter}
        onEdgeMouseLeave={onEdgeMouseLeave}
        edgesFocusable
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        deleteKeyCode={['Backspace', 'Delete']}
        connectionLineStyle={{ stroke: '#C17F3E', strokeWidth: 2 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1.2}
          color={dark ? '#3c4c5e' : '#9aabbc'}
        />
        <Controls />
        <MiniMap
          nodeColor={dark ? '#33414f' : '#dce5ee'}
          maskColor={dark ? 'rgba(16, 21, 28, 0.72)' : 'rgba(232, 238, 242, 0.7)'}
          style={{ background: dark ? '#1a222c' : '#fffdf8' }}
        />
      </ReactFlow>
      <div className="circuit-canvas__hint">
        {cutMode
          ? 'Wire cutter active — click any wire to cut it. Click ✂ again to exit.'
          : 'Drag pin → pin to wire. Click a wire + Delete, or use ✂ Cut wire. Validation updates live.'}
      </div>
    </div>
  )
}
