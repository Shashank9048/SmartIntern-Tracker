'use client'

import { useState, useEffect } from 'react'
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  pointerWithin,
  rectIntersection,
  closestCorners,
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Building2, MapPin, GripVertical, Trash2 } from 'lucide-react'
import { TrackedJobEntry, TrackedJobStatus } from '@/types'

// ─────────────────────────────────────────────────────────────────────────────
// Column config
// ─────────────────────────────────────────────────────────────────────────────

const COLUMNS: { id: TrackedJobStatus; label: string; colour: string; dotColour: string }[] = [
  { id: 'wishlist',  label: 'Wishlist',  colour: 'border-blue-500/20 bg-blue-500/5',    dotColour: 'bg-blue-400' },
  { id: 'applied',   label: 'Applied',   colour: 'border-amber-500/20 bg-amber-500/5',   dotColour: 'bg-amber-400' },
  { id: 'oa',        label: 'OA',        colour: 'border-purple-500/20 bg-purple-500/5', dotColour: 'bg-purple-400' },
  { id: 'interview', label: 'Interview', colour: 'border-cyan-500/20 bg-cyan-500/5',     dotColour: 'bg-cyan-400' },
  { id: 'offer',     label: 'Offer',     colour: 'border-emerald-500/20 bg-emerald-500/5', dotColour: 'bg-emerald-400' },
  { id: 'rejected',  label: 'Rejected',  colour: 'border-rose-500/20 bg-rose-500/5',    dotColour: 'bg-rose-400' },
]

// ─────────────────────────────────────────────────────────────────────────────
// KanbanCard — a single draggable card
// ─────────────────────────────────────────────────────────────────────────────

interface KanbanCardProps {
  item: TrackedJobEntry
  onDelete: (id: string) => void
  isDragOverlay?: boolean
}

function KanbanCard({ item, onDelete, isDragOverlay = false }: KanbanCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item._id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }



  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`glass rounded-xl p-3 flex flex-col gap-2 border border-white/10 select-none
        ${isDragOverlay ? 'shadow-2xl shadow-black/40 scale-105 rotate-1 border-white/20' : 'hover:border-white/20'}
        transition-colors duration-150`}
    >
      {/* Drag handle + title row */}
      <div className="flex items-start gap-2">
        <button
          {...attributes}
          {...listeners}
          className="mt-0.5 text-white/20 hover:text-white/50 transition-colors shrink-0 cursor-grab active:cursor-grabbing"
          aria-label="Drag to reorder"
        >
          <GripVertical className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <p
            className="text-sm font-semibold truncate text-white leading-tight"
            style={{ fontFamily: "'Space Grotesk', sans-serif" }}
          >
            {item.job.title}
          </p>
          <div className="flex items-center gap-1 mt-0.5">
            <Building2 className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-xs text-muted-foreground truncate">{item.job.company}</span>
          </div>
        </div>

      </div>

      {/* Location */}
      <div className="flex items-center gap-1 text-xs text-muted-foreground pl-6">
        <MapPin className="w-3 h-3 shrink-0" />
        <span className="truncate">{item.job.location}</span>
      </div>

      {/* Delete */}
      <div className="flex justify-end pl-6">
        <button
          onClick={() => onDelete(item._id)}
          className="text-white/20 hover:text-rose-400 transition-colors"
          aria-label={`Remove ${item.job.title} from tracker`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// KanbanColumn — a droppable column
// ─────────────────────────────────────────────────────────────────────────────

interface KanbanColumnProps {
  col: typeof COLUMNS[0]
  items: TrackedJobEntry[]
  onDelete: (id: string) => void
}

function KanbanColumn({ col, items, onDelete }: KanbanColumnProps) {
  const { setNodeRef, isOver } = useDroppable({
    id: col.id,
  })

  return (
    <div
      ref={setNodeRef}
      className={`flex-1 min-w-[230px] max-w-[280px] rounded-xl border p-3 flex flex-col gap-2 ${col.colour} ${
        isOver ? 'ring-2 ring-amber-400/50 bg-white/[0.08]' : ''
      } transition-all duration-200`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 pb-2 border-b border-white/10">
        <span className={`w-2 h-2 rounded-full shrink-0 ${col.dotColour}`} />
        <h3 className="text-xs font-semibold text-white uppercase tracking-wider flex-1">
          {col.label}
        </h3>
        <span className="text-xs bg-white/10 px-1.5 py-0.5 rounded-full text-muted-foreground font-mono">
          {items.length}
        </span>
      </div>

      {/* Cards */}
      <SortableContext
        items={items.map((i) => i._id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex flex-col gap-2 flex-1 min-h-[120px]">
          {items.map((item) => (
            <KanbanCard key={item._id} item={item} onDelete={onDelete} />
          ))}
          {items.length === 0 && (
            <div className="flex-1 flex items-center justify-center border border-dashed border-white/10 rounded-lg py-6">
              <p
                className="text-xs text-white/30 font-mono"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Drop here
              </p>
            </div>
          )}
        </div>
      </SortableContext>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// KanbanBoard — main export
// ─────────────────────────────────────────────────────────────────────────────

interface KanbanBoardProps {
  items: TrackedJobEntry[]
  onStatusChange: (id: string, newStatus: TrackedJobStatus) => Promise<void>
  onDelete: (id: string) => Promise<void>
}

export function KanbanBoard({ items, onStatusChange, onDelete }: KanbanBoardProps) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const [localItems, setLocalItems] = useState<TrackedJobEntry[]>(items)

  // Keep local state in sync whenever items prop changes
  useEffect(() => {
    setLocalItems(items)
  }, [items])

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  )

  const activeItem = localItems.find((i) => i._id === activeId) ?? null

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id))
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event
    if (!over) return

    const activeItemId = String(active.id)
    const overId = String(over.id)

    // Check if over a column id directly or another card
    const targetColumn = COLUMNS.find((c) => c.id === overId)
    let newStatus: TrackedJobStatus | null = null

    if (targetColumn) {
      newStatus = targetColumn.id
    } else {
      // Dragging over another card — find which column that card is in
      const overItem = localItems.find((i) => i._id === overId)
      if (overItem) newStatus = overItem.status
    }

    if (!newStatus) return

    setLocalItems((prev) =>
      prev.map((item) =>
        item._id === activeItemId ? { ...item, status: newStatus! } : item
      )
    )
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    setActiveId(null)

    if (!over) {
      setLocalItems(items)
      return
    }

    const activeItemId = String(active.id)
    const overId = String(over.id)

    const targetColumn = COLUMNS.find((c) => c.id === overId)
    let newStatus: TrackedJobStatus | null = null

    if (targetColumn) {
      newStatus = targetColumn.id
    } else {
      const overItem = localItems.find((i) => i._id === overId)
      if (overItem) newStatus = overItem.status
    }

    if (!newStatus) {
      setLocalItems(items)
      return
    }

    const original = items.find((i) => i._id === activeItemId)
    if (!original) return

    // Apply update to local state
    setLocalItems((prev) =>
      prev.map((item) =>
        item._id === activeItemId ? { ...item, status: newStatus! } : item
      )
    )

    if (original.status !== newStatus) {
      try {
        await onStatusChange(activeItemId, newStatus)
      } catch {
        setLocalItems(items)
      }
    }
  }

  async function handleDelete(id: string) {
    // Optimistic remove — save snapshot first so we can roll back on failure,
    // matching the same pattern handleDragEnd uses for status changes.
    const snapshot = localItems
    setLocalItems((prev) => prev.filter((i) => i._id !== id))
    try {
      await onDelete(id)
    } catch {
      // API call failed — restore the item so the user knows deletion didn't happen
      setLocalItems(snapshot)
    }
  }

  const columnedItems = (colId: TrackedJobStatus) =>
    localItems.filter((i) => i.status === colId)

  // Custom collision detection: pointerWithin first, fallback to rectIntersection
  const customCollisionDetection = (args: any) => {
    const pointerCollisions = pointerWithin(args)
    if (pointerCollisions.length > 0) return pointerCollisions
    return rectIntersection(args)
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={customCollisionDetection}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div
        className="flex gap-3 overflow-x-auto pb-4"
        style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.1) transparent' }}
      >
        {COLUMNS.map((col) => (
          <KanbanColumn
            key={col.id}
            col={col}
            items={columnedItems(col.id)}
            onDelete={handleDelete}
          />
        ))}
      </div>

      {/* Drag overlay — ghost card that follows the cursor */}
      <DragOverlay>
        {activeItem ? (
          <KanbanCard item={activeItem} onDelete={() => {}} isDragOverlay />
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}
