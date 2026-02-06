import { useState, useEffect, useRef } from 'react';
import { Server, RefreshCw } from 'lucide-react';
import { API_BASE } from '../lib/config';

interface Worker {
  id: string;
  hostname: string;
  worker_name: string | null;
  worker_address: string | null;
  max_concurrent_jobs: number;
  current_jobs: number;
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

export function WorkersWidget() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchWorkers();
    intervalRef.current = setInterval(fetchWorkers, 10000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  async function fetchWorkers() {
    try {
      const res = await fetch(`${API_BASE}/api/workers`);
      if (!res.ok) throw new Error('Failed to fetch workers');
      const data = await res.json();
      setWorkers(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-200 flex items-center gap-2">
          <Server className="w-5 h-5 text-purple-400" />
          Workers
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{workers.length}</span>
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

      {loading && workers.length === 0 ? (
        <div className="text-center py-4 text-gray-500">Loading...</div>
      ) : workers.length === 0 ? (
        <div className="text-center py-6 text-gray-500">
          <p>No workers connected</p>
          <p className="mt-1 text-xs text-gray-600">
            Run <code className="bg-gray-900 px-1 rounded">python -m src.worker</code> to start one
          </p>
        </div>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {workers.map((worker) => (
            <div
              key={worker.id}
              className="p-3 bg-gray-900 rounded-lg"
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`w-2 h-2 rounded-full ${getStatusColor(worker.status)}`}
                />
                <span className="text-sm text-gray-200 truncate">
                  {worker.worker_name || worker.hostname}
                </span>
                <span className="text-xs text-gray-500">{worker.hostname}</span>
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
                  Jobs: {worker.current_jobs}/{worker.max_concurrent_jobs}
                </span>
                <span>Heartbeat: {relativeTime(worker.last_heartbeat_at)}</span>
                <span>Up: {uptimeString(worker.registered_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
