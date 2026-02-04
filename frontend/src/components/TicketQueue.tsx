import { useMemo } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Bug, Sparkles, HelpCircle, CheckSquare } from 'lucide-react';
import type { TicketInfo } from '../types';

interface TicketQueueProps {
  tickets: TicketInfo[];
  onReorder: (newOrder: string[]) => void;
  currentTicketKey: string | null;
}

function TicketTypeIcon({ type }: { type: string }) {
  switch (type) {
    case 'bug':
      return <Bug className="w-4 h-4 text-red-400" />;
    case 'feature':
      return <Sparkles className="w-4 h-4 text-purple-400" />;
    case 'question':
      return <HelpCircle className="w-4 h-4 text-blue-400" />;
    default:
      return <CheckSquare className="w-4 h-4 text-gray-400" />;
  }
}

function SortableTicket({
  ticket,
  isActive,
}: {
  ticket: TicketInfo;
  isActive: boolean;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: ticket.key });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`
        flex items-center gap-3 p-3 rounded-lg border
        ${isActive
          ? 'bg-green-900/30 border-green-500'
          : 'bg-gray-800 border-gray-700 hover:border-gray-600'
        }
        ${isDragging ? 'shadow-lg' : ''}
      `}
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-gray-500 hover:text-gray-300"
      >
        <GripVertical className="w-5 h-5" />
      </button>

      <TicketTypeIcon type={ticket.ticket_type} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-gray-400">{ticket.key}</span>
          <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">
            {ticket.project}
          </span>
          {isActive && (
            <span className="text-xs px-2 py-0.5 rounded bg-green-600 text-white animate-pulse">
              Active
            </span>
          )}
        </div>
        <p className="text-sm text-gray-200 truncate mt-1">{ticket.summary}</p>
      </div>

      <div className="text-right">
        <div className="text-lg font-bold text-gray-300">
          {ticket.priority_score.toFixed(0)}
        </div>
        <div className="text-xs text-gray-500">score</div>
      </div>
    </div>
  );
}

export function TicketQueue({ tickets, onReorder, currentTicketKey }: TicketQueueProps) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const ticketIds = useMemo(() => tickets.map((t) => t.key), [tickets]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = ticketIds.indexOf(active.id as string);
      const newIndex = ticketIds.indexOf(over.id as string);
      const newOrder = arrayMove(ticketIds, oldIndex, newIndex);
      onReorder(newOrder);
    }
  }

  if (tickets.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No tickets in queue
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={ticketIds} strategy={verticalListSortingStrategy}>
        <div className="space-y-2">
          {tickets.map((ticket) => (
            <SortableTicket
              key={ticket.key}
              ticket={ticket}
              isActive={ticket.key === currentTicketKey}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
