'use client'

import { useState } from 'react'
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Building2, MapPin, GripVertical, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
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

  const scoreColour =
    item.match_score_at_save >= 85
      ? 'text-amber-400'
      : item.match_score_at_save >= 70
      ? 'text-amber-300'
      : item.match_score_at_save >= 50
      ? 'text-amber-200/70'
      : 'text-white/40'

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
        {/* Score badge */}
        <span
          className={`font-mono text-base font-bold tabular-nums shrink-0 ${scoreColour}`}
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {item.match_score_at_save}%
        </span>
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
  return (
    <div
      className={`flex-1 min-w-[230px] max-w-[280px] rounded-xl border p-3 flex flex-col gap-2 ${col.colour}`}
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
        <div className="flex flex-col gap-2 flex-1 min-h-[80px]">
          {items.map((item) => (
            <KanbanCard key={item._id} item={item} onDelete={onDelete} />
          ))}
          {items.length === 0 && (
            <div className="flex-1 flex items-center justify-center">
              <p
                className="text-xs text-white/20 font-mono"
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

  // Keep local state in sync when parent updates (initial fetch)
  // We use local state for optimistic drag updates
  const currentItems = localItems.length ? localItems : items

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    })
  )

  const activeItem = currentItems.find((i) => i._id === activeId) ?? null

  function findColumnForItem(id: string): TrackedJobStatus | null {
    const item = currentItems.find((i) => i._id === id)
    return item?.status ?? null
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id))
  }

  function handleDragOver(event: DragOverEvent) {
    const { active, over } = event
    if (!over) return

    const activeItemId = String(active.id)
    const overId = String(over.id)

    // Check if over a column id or another card
    const targetColumn = COLUMNS.find((c) => c.id === overId)
    let newStatus: TrackedJobStatus | null = null

    if (targetColumn) {
      newStatus = targetColumn.id
    } else {
      // Dragging over another card — find which column that card is in
      const overItem = currentItems.find((i) => i._id === overId)
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
      // Revert local state if dropped nowhere
      setLocalItems(items)
      return
    }

    const activeItemId = String(active.id)
    const overId = String(over.id)

    // Find target column
    const targetColumn = COLUMNS.find((c) => c.id === overId)
    let newStatus: TrackedJobStatus | null = null

    if (targetColumn) {
      newStatus = targetColumn.id
    } else {
      const overItem = currentItems.find((i) => i._id === overId)
      if (overItem) newStatus = overItem.status
    }

    if (!newStatus) {
      setLocalItems(items)
      return
    }

    const original = items.find((i) => i._id === activeItemId)
    if (!original || original.status === newStatus) return

    // Commit optimistic update
    setLocalItems((prev) =>
      prev.map((item) =>
        item._id === activeItemId ? { ...item, status: newStatus! } : item
      )
    )

    try {
      await onStatusChange(activeItemId, newStatus)
    } catch {
      // Revert on failure
      setLocalItems(items)
    }
  }

  function handleDelete(id: string) {
    setLocalItems((prev) => prev.filter((i) => i._id !== id))
    onDelete(id)
  }

  const columnedItems = (colId: TrackedJobStatus) =>
    currentItems.filter((i) => i.status === colId)

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
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
