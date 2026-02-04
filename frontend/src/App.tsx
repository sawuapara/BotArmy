import { useState, useCallback } from 'react';
import { Play, Pause, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { useWebSocket } from './hooks/useWebSocket';
import { TicketQueue } from './components/TicketQueue';
import { ThoughtLog } from './components/ThoughtLog';
import { ActiveTicket } from './components/ActiveTicket';
import { RevenueStatus } from './components/RevenueStatus';
import { RevenueWidget } from './components/RevenueWidget';
import type { Session } from './types';

const API_BASE = 'http://localhost:8000';

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { isConnected, state, sendInterrupt } = useWebSocket(session?.session_id ?? null);

  const createSession = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to create session');
      const data = await res.json();
      setSession(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const startSession = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/sessions/${session.session_id}/start`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Failed to start session');
      setSession((prev) => (prev ? { ...prev, status: 'running' } : null));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [session]);

  const pauseSession = useCallback(async () => {
    if (!session) return;
    try {
      await fetch(`${API_BASE}/sessions/${session.session_id}/pause`, {
        method: 'POST',
      });
      setSession((prev) => (prev ? { ...prev, status: 'paused' } : null));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }, [session]);

  const handleReorder = useCallback(
    async (newOrder: string[]) => {
      if (!session) return;
      try {
        await fetch(`${API_BASE}/sessions/${session.session_id}/queue/reorder`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ticket_keys: newOrder }),
        });
      } catch (e) {
        console.error('Failed to reorder:', e);
      }
    },
    [session]
  );

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">
              Orchestrator Dashboard
            </h1>
            <p className="text-sm text-gray-400">
              MecanoLabs / MecanoConsulting Work Prioritization
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* Connection status */}
            <div className="flex items-center gap-2 text-sm">
              {isConnected ? (
                <>
                  <Wifi className="w-4 h-4 text-green-400" />
                  <span className="text-green-400">Connected</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-gray-500" />
                  <span className="text-gray-500">Disconnected</span>
                </>
              )}
            </div>

            {/* Session controls */}
            {!session ? (
              <button
                onClick={createSession}
                disabled={isLoading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-white font-medium disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                New Session
              </button>
            ) : session.status === 'running' ? (
              <button
                onClick={pauseSession}
                className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-500 rounded-lg text-white font-medium"
              >
                <Pause className="w-4 h-4" />
                Pause
              </button>
            ) : (
              <button
                onClick={startSession}
                disabled={isLoading}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-white font-medium disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                {session.status === 'created' ? 'Start' : 'Resume'}
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-300">
            {error}
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="p-6">
        <div className="grid grid-cols-12 gap-6">
          {/* Left column: Revenue + Queue */}
          <div className="col-span-4 space-y-6">
            {/* Comprehensive Revenue Widget */}
            <RevenueWidget />

            {/* Original simple revenue status (from orchestrator state) */}
            <RevenueStatus
              status={state?.revenue_status ?? null}
              workType={state?.work_type ?? null}
            />

            <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
              <h3 className="font-semibold text-gray-200 mb-4">Ticket Queue</h3>
              <TicketQueue
                tickets={state?.ticket_queue ?? []}
                onReorder={handleReorder}
                currentTicketKey={state?.current_ticket?.key ?? null}
              />
            </div>
          </div>

          {/* Middle column: Active Ticket */}
          <div className="col-span-5 space-y-6">
            <ActiveTicket
              ticket={state?.current_ticket ?? null}
              workerState={state?.worker_state ?? null}
            />

            {/* Session info */}
            {session && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-gray-400">Session:</span>
                    <span className="ml-2 font-mono text-gray-200">
                      {session.session_id.slice(0, 8)}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Status:</span>
                    <span
                      className={`ml-2 ${
                        session.status === 'running'
                          ? 'text-green-400'
                          : session.status === 'paused'
                          ? 'text-yellow-400'
                          : 'text-gray-300'
                      }`}
                    >
                      {session.status}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Node:</span>
                    <span className="ml-2 font-mono text-blue-400">
                      {state?.current_node ?? '-'}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right column: Thought log */}
          <div className="col-span-3 h-[calc(100vh-180px)]">
            <ThoughtLog thoughts={state?.thought_log ?? []} />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
