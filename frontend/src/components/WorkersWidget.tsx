import { useState, useEffect, useRef, useMemo } from 'react';
import { Server, RefreshCw, Maximize2, X, Search } from 'lucide-react';
import { API_BASE } from '../lib/config';
import { useUniverseStream } from '../hooks/useUniverseStream';
import { WorkerDetailModal } from './WorkerDetailModal';

interface Worker {
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

function WorkerCard({
  worker,
  dimmed,
  onClick,
}: {
  worker: Worker;
  dimmed?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      className={`p-3 bg-gray-900 rounded-lg ${dimmed ? 'opacity-50' : ''} ${onClick ? 'cursor-pointer hover:bg-gray-800 transition-colors' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className={`w-2 h-2 rounded-full ${getStatusColor(worker.status)}`}
        />
        <span className="text-sm text-gray-200 truncate">
          {worker.worker_name || worker.hostname}
        </span>
        <span className="text-xs text-gray-500">{worker.hostname}</span>
        <span className="text-xs text-gray-500 capitalize">{worker.status}</span>
      </div>

      <div className="ml-4 text-xs text-gray-500 font-mono mb-1">
        {worker.id.slice(0, 12)}...
      </div>

      {worker.capabilities.length > 0 && (
        <div className="ml-4 flex flex-wrap gap-1 mb-1">
          {worker.capabilities.map((cap) => (
            <span
              key={cap}
              className="px-1.5 py-0.5 bg-gray-700 rounded text-xs text-gray-400"
            >
              {cap}
            </span>
          ))}
        </div>
      )}

      <div className="ml-4 flex items-center gap-3 text-xs text-gray-500">
        <span>
          Agents: {worker.current_agents}/{worker.max_concurrent_agents}
        </span>
        <span>Heartbeat: {relativeTime(worker.last_heartbeat_at)}</span>
        <span>Up: {uptimeString(worker.registered_at)}</span>
      </div>
    </div>
  );
}

export function WorkersWidget() {
  const [allWorkers, setAllWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showOnlyActive, setShowOnlyActive] = useState(true);
  const [selectedWorker, setSelectedWorker] = useState<Worker | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { universes, events } = useUniverseStream();

  const activeWorkers = useMemo(
    () => allWorkers.filter((w) => w.status !== 'offline'),
    [allWorkers],
  );

  const modalWorkers = useMemo(() => {
    let filtered = showOnlyActive
      ? allWorkers.filter((w) => w.status !== 'offline')
      : allWorkers;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (w) =>
          (w.worker_name && w.worker_name.toLowerCase().includes(q)) ||
          w.hostname.toLowerCase().includes(q) ||
          w.id.toLowerCase().includes(q),
      );
    }

    return filtered;
  }, [allWorkers, showOnlyActive, searchQuery]);

  useEffect(() => {
    fetchWorkers();
    intervalRef.current = setInterval(fetchWorkers, 10000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (!showModal) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setShowModal(false);
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showModal]);

  async function fetchWorkers() {
    try {
      const res = await fetch(`${API_BASE}/api/workers`);
      if (!res.ok) throw new Error('Failed to fetch workers');
      const data = await res.json();
      setAllWorkers(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-200 flex items-center gap-2">
            <Server className="w-5 h-5 text-purple-400" />
            Workers
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{activeWorkers.length}</span>
            <button
              onClick={() => setShowModal(true)}
              className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
              title="Expand"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
            <button
              onClick={fetchWorkers}
              className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-3 p-2 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
            {error}
          </div>
        )}

        {loading && allWorkers.length === 0 ? (
          <div className="text-center py-4 text-gray-500">Loading...</div>
        ) : activeWorkers.length === 0 ? (
          <div className="text-center py-6 text-gray-500">
            <p>No workers connected</p>
            <p className="mt-1 text-xs text-gray-600">
              Run <code className="bg-gray-900 px-1 rounded">python -m src.worker</code> to start one
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {activeWorkers.map((worker) => (
              <WorkerCard
                key={worker.id}
                worker={worker}
                onClick={() => setSelectedWorker(worker)}
              />
            ))}
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowModal(false)} />
          <div className="relative bg-gray-800 rounded-lg border border-gray-700 w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
                <Server className="w-5 h-5 text-purple-400" />
                Workers
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Controls */}
            <div className="p-4 border-b border-gray-700 space-y-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search by name, hostname, or ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-purple-500"
                  autoFocus
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showOnlyActive}
                  onChange={(e) => setShowOnlyActive(e.target.checked)}
                  className="rounded border-gray-600 bg-gray-900 text-purple-500 focus:ring-purple-500"
                />
                Only show active workers
              </label>
            </div>

            {/* Worker list */}
            <div className="p-4 overflow-y-auto flex-1 space-y-2">
              {modalWorkers.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  {searchQuery.trim() ? 'No workers match your search' : 'No workers found'}
                </div>
              ) : (
                modalWorkers.map((worker) => (
                  <WorkerCard
                    key={worker.id}
                    worker={worker}
                    dimmed={worker.status === 'offline'}
                    onClick={() => setSelectedWorker(worker)}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {selectedWorker && (
        <WorkerDetailModal
          worker={selectedWorker}
          universes={universes}
          events={events}
          onClose={() => setSelectedWorker(null)}
        />
      )}
    </>
  );
}
