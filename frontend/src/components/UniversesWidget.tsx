import { useState, useEffect, useRef, useMemo } from 'react';
import { Globe } from 'lucide-react';
import { API_BASE } from '../lib/config';
import { useUniverseStream } from '../hooks/useUniverseStream';
import { UniverseModal } from './UniverseModal';
import type { Universe } from '../types';

function getStatusColor(status: string) {
  switch (status) {
    case 'active':
      return 'bg-green-500';
    case 'initializing':
      return 'bg-yellow-500';
    case 'suspended':
      return 'bg-orange-500';
    case 'terminated':
      return 'bg-gray-500';
    case 'error':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
}

export function UniversesWidget() {
  const { universes: streamUniverses, events, isConnected } = useUniverseStream();
  const [fallbackUniverses, setFallbackUniverses] = useState<Universe[]>([]);
  const [selectedUniverse, setSelectedUniverse] = useState<Universe | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Use stream data when connected, fallback to polling otherwise
  const universes = isConnected ? streamUniverses : fallbackUniverses;

  const activeUniverses = useMemo(
    () => universes.filter((u) => u.status !== 'terminated'),
    [universes]
  );

  // Polling fallback when WS disconnects
  useEffect(() => {
    if (isConnected) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    async function fetchUniverses() {
      try {
        const res = await fetch(`${API_BASE}/api/universes`);
        if (!res.ok) return;
        const data = await res.json();
        setFallbackUniverses(data);
      } catch {
        // Silently fail
      }
    }

    fetchUniverses();
    intervalRef.current = setInterval(fetchUniverses, 10000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isConnected]);

  // Keep selected universe in sync with live data
  useEffect(() => {
    if (selectedUniverse) {
      const updated = universes.find((u) => u.id === selectedUniverse.id);
      if (updated) setSelectedUniverse(updated);
    }
  }, [universes, selectedUniverse?.id]);

  return (
    <>
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-200 flex items-center gap-2">
            <Globe className="w-5 h-5 text-indigo-400" />
            Universes
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">
              {activeUniverses.length}
            </span>
            {!isConnected && (
              <span className="w-2 h-2 rounded-full bg-yellow-500" title="WS disconnected, polling" />
            )}
            {isConnected && (
              <span className="w-2 h-2 rounded-full bg-green-500" title="Live" />
            )}
          </div>
        </div>

        {universes.length === 0 ? (
          <div className="text-center py-6 text-gray-500">
            <p>No universes running</p>
            <p className="mt-1 text-xs text-gray-600">
              Launch one via the worker's <code className="bg-gray-900 px-1 rounded">/launch</code> endpoint
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {universes.map((universe) => (
              <button
                key={universe.id}
                onClick={() => setSelectedUniverse(universe)}
                className="w-full text-left p-3 bg-gray-900 rounded-lg hover:bg-gray-850 hover:ring-1 hover:ring-indigo-500/30 transition-all"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`w-2 h-2 rounded-full ${getStatusColor(universe.status)}`}
                  />
                  <span className="text-sm text-gray-200 truncate">
                    {universe.name}
                  </span>
                </div>
                <div className="ml-4 flex items-center gap-3 text-xs text-gray-500">
                  <span>
                    {universe.agents.length} agent{universe.agents.length !== 1 ? 's' : ''}
                  </span>
                  <span>v{universe.state_version}</span>
                  <span>{universe.status}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedUniverse && (
        <UniverseModal
          universe={selectedUniverse}
          events={events}
          onClose={() => setSelectedUniverse(null)}
        />
      )}
    </>
  );
}
