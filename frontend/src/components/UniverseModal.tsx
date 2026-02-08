import { useEffect, useRef, useMemo } from 'react';
import { X } from 'lucide-react';
import type { Universe, UniverseEvent } from '../types';

function getAgentStatusColor(status: string) {
  switch (status) {
    case 'running':
      return 'bg-green-500';
    case 'completed':
      return 'bg-blue-500';
    case 'error':
      return 'bg-red-500';
    case 'paused':
      return 'bg-yellow-500';
    default:
      return 'bg-gray-500';
  }
}

function getEventColor(type: string) {
  switch (type) {
    case 'tool_call':
      return 'text-blue-400';
    case 'tool_result':
      return 'text-cyan-400';
    case 'llm_response':
      return 'text-purple-400';
    case 'turn_start':
      return 'text-yellow-400';
    case 'turn_end':
      return 'text-green-400';
    case 'agent_done':
      return 'text-green-300';
    case 'agent_error':
      return 'text-red-400';
    case 'agent_started':
      return 'text-emerald-400';
    default:
      return 'text-gray-400';
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return '';
  }
}

function summarizeEvent(event: UniverseEvent): string {
  const data = event.data;
  switch (event.type) {
    case 'tool_call':
      return `${data.tool}(${JSON.stringify(data.input || {}).slice(0, 80)})`;
    case 'tool_result':
      return `${data.tool} -> ${String(data.result || '').slice(0, 80)}`;
    case 'llm_response':
      return String(data.text || '').slice(0, 120);
    case 'turn_start':
      return `Turn ${data.turn}/${data.max_turns}`;
    case 'turn_end':
      return `Turn ${data.turn} done (v${data.state_version})`;
    case 'agent_done':
      return `Completed after turn ${data.final_turn}`;
    case 'agent_error':
      return String(data.error || 'Unknown error');
    case 'agent_started':
      return `Role: ${data.role}, Model: ${data.model || 'default'}`;
    default:
      return JSON.stringify(data).slice(0, 100);
  }
}

interface UniverseModalProps {
  universe: Universe;
  events: UniverseEvent[];
  onClose: () => void;
}

export function UniverseModal({ universe, events, onClose }: UniverseModalProps) {
  const logEndRef = useRef<HTMLDivElement>(null);

  const filteredEvents = useMemo(
    () => events.filter((e) => e.universe_id === universe.id),
    [events, universe.id]
  );

  const displayAgents = useMemo(
    () => universe.agents.slice(-10),
    [universe.agents]
  );

  const liveCount = useMemo(
    () => universe.agents.filter((a) => a.status === 'running').length,
    [universe.agents]
  );

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [filteredEvents.length]);

  // Escape key to close
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-800 rounded-lg border border-gray-700 w-[70vw] h-[70vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-gray-200">
              {universe.name}
            </h2>
            <span className="text-xs text-gray-500 font-mono">
              {universe.id.slice(0, 8)}
            </span>
            <span
              className={`px-2 py-0.5 rounded text-xs ${
                universe.status === 'active'
                  ? 'bg-green-900/50 text-green-400'
                  : universe.status === 'terminated'
                  ? 'bg-gray-700 text-gray-400'
                  : universe.status === 'error'
                  ? 'bg-red-900/50 text-red-400'
                  : 'bg-yellow-900/50 text-yellow-400'
              }`}
            >
              {universe.status}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body: two panels */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left panel: streaming events (~65%) */}
          <div className="flex-[65] flex flex-col border-r border-gray-700">
            <div className="px-4 py-2 border-b border-gray-700 text-xs text-gray-500">
              Events ({filteredEvents.length})
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-xs">
              {filteredEvents.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No events yet...
                </div>
              ) : (
                filteredEvents.map((event, i) => (
                  <div key={i} className="flex gap-2 leading-5">
                    <span className="text-gray-600 shrink-0">
                      {formatTime(event.timestamp)}
                    </span>
                    {event.agent_name && (
                      <span className="text-gray-400 shrink-0">
                        [{event.agent_name}]
                      </span>
                    )}
                    <span className={`shrink-0 ${getEventColor(event.type)}`}>
                      {event.type}
                    </span>
                    <span className="text-gray-300 truncate">
                      {summarizeEvent(event)}
                    </span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          {/* Right panel: agents (~35%) */}
          <div className="flex-[35] flex flex-col">
            <div className="px-4 py-2 border-b border-gray-700 text-xs text-gray-500">
              Agents ({universe.agents.length})
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {displayAgents.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No agents yet...
                </div>
              ) : (
                displayAgents.map((agent) => (
                  <div
                    key={agent.id}
                    className="p-3 bg-gray-900 rounded-lg"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`w-2 h-2 rounded-full ${getAgentStatusColor(
                          agent.status
                        )}`}
                      />
                      <span className="text-sm text-gray-200">
                        {agent.name}
                      </span>
                      <span className="text-xs text-gray-500">
                        {agent.role}
                      </span>
                    </div>
                    <div className="ml-4 flex items-center gap-3 text-xs text-gray-500">
                      <span>Turn: {agent.current_turn}</span>
                      <span>{agent.status}</span>
                      {agent.model && (
                        <span className="text-gray-600 truncate">
                          {agent.model}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Live counter */}
            <div className="px-4 py-3 border-t border-gray-700">
              <div className="flex items-center gap-2 text-sm">
                {liveCount > 0 && (
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                )}
                <span className="text-gray-400">
                  Live: {liveCount} agent{liveCount !== 1 ? 's' : ''}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
