import { useEffect, useRef, useMemo } from 'react';
import { X, Server } from 'lucide-react';
import type { Universe, UniverseEvent } from '../types';

export interface Worker {
  id: string;
  hostname: string;
  worker_name: string | null;
  worker_address: string | null;
  max_concurrent_agents: number;
  current_agents: number;
  capabilities: string[];
  status: string;
  last_heartbeat_at: string;
  registered_at: string;
  updated_at: string;
}

interface WorkerDetailModalProps {
  worker: Worker;
  universes: Universe[];
  events: UniverseEvent[];
  onClose: () => void;
}

function parsePort(address: string): string | null {
  try {
    return new URL(address).port || null;
  } catch {
    const match = address.match(/:(\d+)/);
    return match ? match[1] : null;
  }
}

function getStatusColor(status: string) {
  switch (status) {
    case 'online':
      return 'bg-green-500';
    case 'busy':
      return 'bg-yellow-500';
    case 'draining':
      return 'bg-orange-500';
    case 'offline':
      return 'bg-gray-500';
    default:
      return 'bg-gray-500';
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'online':
      return 'bg-green-900/50 text-green-400';
    case 'busy':
      return 'bg-yellow-900/50 text-yellow-400';
    case 'draining':
      return 'bg-orange-900/50 text-orange-400';
    case 'offline':
      return 'bg-gray-700 text-gray-400';
    default:
      return 'bg-gray-700 text-gray-400';
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
    case 'universe_created':
      return 'text-indigo-400';
    case 'universe_stopped':
      return 'text-gray-400';
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
    case 'universe_created':
      return `Universe "${data.name}" created`;
    case 'universe_stopped':
      return `Universe "${data.name}" stopped`;
    default:
      return JSON.stringify(data).slice(0, 100);
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function uptimeString(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

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

function getUniverseStatusBadge(status: string) {
  switch (status) {
    case 'active':
      return 'bg-green-900/50 text-green-400';
    case 'terminated':
      return 'bg-gray-700 text-gray-400';
    case 'error':
      return 'bg-red-900/50 text-red-400';
    default:
      return 'bg-yellow-900/50 text-yellow-400';
  }
}

export function WorkerDetailModal({
  worker,
  universes,
  events,
  onClose,
}: WorkerDetailModalProps) {
  const logEndRef = useRef<HTMLDivElement>(null);

  const workerUniverses = useMemo(
    () => universes.filter((u) => u.worker_id === worker.id),
    [universes, worker.id],
  );

  const filteredEvents = useMemo(
    () => events.filter((e) => e.worker_id === worker.id),
    [events, worker.id],
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
            <Server className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-gray-200">
              {worker.worker_name || worker.hostname}
            </h2>
            <span className="text-xs text-gray-500 font-mono">
              {worker.id.slice(0, 8)}
            </span>
            <span
              className={`px-2 py-0.5 rounded text-xs ${getStatusBadge(worker.status)}`}
            >
              {worker.status}
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

          {/* Right panel: worker details (~35%) */}
          <div className="flex-[35] flex flex-col">
            <div className="px-4 py-2 border-b border-gray-700 text-xs text-gray-500">
              Worker Details
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Info section */}
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${getStatusColor(worker.status)}`}
                  />
                  <span className="text-gray-200 capitalize font-medium">
                    {worker.status}
                  </span>
                </div>

                <div>
                  <span className="text-gray-500 text-xs">ID</span>
                  <div className="text-gray-300 font-mono text-xs break-all">
                    {worker.id}
                  </div>
                </div>

                {worker.worker_address && (
                  <div>
                    <span className="text-gray-500 text-xs">Address</span>
                    <div className="text-gray-300 font-mono text-xs">
                      {worker.worker_address}
                    </div>
                  </div>
                )}

                {worker.worker_address && parsePort(worker.worker_address) && (
                  <div>
                    <span className="text-gray-500 text-xs">Port</span>
                    <div className="text-gray-300 font-mono text-xs">
                      {parsePort(worker.worker_address)}
                    </div>
                  </div>
                )}

                <div>
                  <span className="text-gray-500 text-xs">Agent Capacity</span>
                  <div className="text-gray-300 text-xs">
                    {worker.current_agents} / {worker.max_concurrent_agents} agents
                  </div>
                </div>

                {worker.capabilities.length > 0 && (
                  <div>
                    <span className="text-gray-500 text-xs">Capabilities</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {worker.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="px-1.5 py-0.5 bg-gray-700 rounded text-xs text-gray-400"
                        >
                          {cap}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <span className="text-gray-500 text-xs">Heartbeat</span>
                  <div className="text-gray-300 text-xs">
                    {relativeTime(worker.last_heartbeat_at)}
                  </div>
                </div>

                <div>
                  <span className="text-gray-500 text-xs">Uptime</span>
                  <div className="text-gray-300 text-xs">
                    {uptimeString(worker.registered_at)}
                  </div>
                </div>

                <div>
                  <span className="text-gray-500 text-xs">Registered</span>
                  <div className="text-gray-300 text-xs">
                    {new Date(worker.registered_at).toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Active Universes section */}
              <div>
                <div className="text-xs text-gray-500 mb-2">
                  Active Universes ({workerUniverses.length})
                </div>
                {workerUniverses.length === 0 ? (
                  <div className="text-center py-4 text-gray-600 text-xs">
                    No active universes
                  </div>
                ) : (
                  <div className="space-y-2">
                    {workerUniverses.map((universe) => (
                      <div
                        key={universe.id}
                        className="p-2.5 bg-gray-900 rounded-lg"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm text-gray-200 truncate">
                            {universe.name}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-xs ${getUniverseStatusBadge(universe.status)}`}
                          >
                            {universe.status}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 space-y-1">
                          <div>
                            Agents: {universe.agents.length} | v{universe.state_version}
                          </div>
                          {universe.agents.map((agent) => (
                            <div key={agent.id} className="flex items-center gap-1.5 ml-2">
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${getAgentStatusColor(agent.status)}`}
                              />
                              <span className="text-gray-400">{agent.name}</span>
                              <span className="text-gray-600">
                                T{agent.current_turn} · {agent.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
