import { useEffect, useRef, useState, useCallback } from 'react';
import type { UniverseEvent, LLMCallDetail } from '../types';
import { API_BASE } from '../lib/config';

export interface AgentInfo {
  model: string | null;
  role: string;
  name: string;
  tools: unknown[] | null;
  currentTurn: number;
  maxTurns: number;
  llmCallCount: number;
  totalInputTokens: number;
  totalOutputTokens: number;
}

export interface DoneSnapshot {
  events: UniverseEvent[];
  lastResponse: string;
  agentInfo: AgentInfo;
  error: string | null;
  llmCalls: LLMCallDetail[];
}

interface UseAgentStreamReturn {
  events: UniverseEvent[];
  isConnected: boolean;
  lastResponse: string;
  isDone: boolean;
  error: string | null;
  agentInfo: AgentInfo;
  llmCalls: LLMCallDetail[];
  /** Populated from refs at the moment isDone becomes true — always consistent */
  doneSnapshot: DoneSnapshot | null;
}

const INITIAL_AGENT_INFO: AgentInfo = {
  model: null,
  role: '',
  name: '',
  tools: null,
  currentTurn: 0,
  maxTurns: 0,
  llmCallCount: 0,
  totalInputTokens: 0,
  totalOutputTokens: 0,
};

/**
 * WebSocket hook scoped to a single universe.
 * Connects once on mount to ws://localhost:{port}/ws/universes, stays connected permanently.
 * Filters events for the given universeId via a ref-based handler so universeId changes
 * don't require reconnecting.
 *
 * Also polls /api/universes when universeId changes to catch the case where the agent
 * already completed/errored before the stream handler was set up (the snapshot arrives
 * on WS connect, which happens before any universeId is set).
 */
export function useAgentStream(universeId: string | null): UseAgentStreamReturn {
  const ws = useRef<WebSocket | null>(null);
  const messageHandlerRef = useRef<((data: Record<string, unknown>) => void) | null>(null);
  const closedRef = useRef(false);
  const [isConnected, setIsConnected] = useState(false);
  const [events, setEvents] = useState<UniverseEvent[]>([]);
  const [lastResponse, setLastResponse] = useState('');
  const [isDone, setIsDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentInfo, setAgentInfo] = useState<AgentInfo>(INITIAL_AGENT_INFO);
  const [doneSnapshot, setDoneSnapshot] = useState<DoneSnapshot | null>(null);
  const [llmCalls, setLlmCalls] = useState<LLMCallDetail[]>([]);
  const llmCallCountRef = useRef(0);
  const pollStartRef = useRef(Date.now());
  // Mirror critical data in refs so done snapshot captures consistent values
  const eventsRef = useRef<UniverseEvent[]>([]);
  const lastResponseRef = useRef('');
  const agentInfoRef = useRef<AgentInfo>(INITIAL_AGENT_INFO);
  const errorRef = useRef<string | null>(null);
  const llmCallsRef = useRef<LLMCallDetail[]>([]);

  // Capture a consistent snapshot from refs, then set isDone
  const finalize = useCallback((err?: string) => {
    if (err) errorRef.current = err;
    setDoneSnapshot({
      events: eventsRef.current,
      lastResponse: lastResponseRef.current,
      agentInfo: agentInfoRef.current,
      error: errorRef.current,
      llmCalls: llmCallsRef.current,
    });
    setIsDone(true);
  }, []);

  // Single persistent WebSocket — connect once on mount, auto-reconnect on close
  useEffect(() => {
    const port = import.meta.env.VITE_API_PORT || '8000';
    const wsUrl = `ws://localhost:${port}/ws/universes`;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    closedRef.current = false;

    function connect() {
      if (closedRef.current) return;
      const socket = new WebSocket(wsUrl);
      ws.current = socket;

      socket.onopen = () => {
        setIsConnected(true);
      };

      socket.onclose = () => {
        setIsConnected(false);
        // Only auto-reconnect if not intentionally closed
        if (!closedRef.current) {
          reconnectTimer = setTimeout(connect, 5000);
        }
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        messageHandlerRef.current?.(data);
      };
    }

    connect();

    return () => {
      closedRef.current = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws.current?.close();
    };
  }, []);

  // Reset state when universeId changes — must fire before handler/poll effects
  useEffect(() => {
    setEvents([]);
    setLastResponse('');
    setIsDone(false);
    setError(null);
    setAgentInfo(INITIAL_AGENT_INFO);
    setDoneSnapshot(null);
    setLlmCalls([]);
    llmCallCountRef.current = 0;
    pollStartRef.current = Date.now();
    eventsRef.current = [];
    lastResponseRef.current = '';
    agentInfoRef.current = INITIAL_AGENT_INFO;
    errorRef.current = null;
    llmCallsRef.current = [];
  }, [universeId]);

  // Message handler updates when universeId changes (via ref)
  // Processes streaming events filtered by universeId
  useEffect(() => {
    messageHandlerRef.current = (data: Record<string, unknown>) => {
      if (!universeId) return;

      // Snapshots are handled by the REST poll below — skip here
      if (data.type === 'snapshot') return;

      // Ignore events for other universes
      if (data.universe_id !== universeId) return;

      const universeEvent = data as unknown as UniverseEvent;
      eventsRef.current = [...eventsRef.current, universeEvent];
      setEvents(eventsRef.current);

      switch (universeEvent.type) {
        case 'agent_started': {
          const updated = {
            ...agentInfoRef.current,
            model: (universeEvent.data.model as string) || null,
            role: (universeEvent.data.role as string) || '',
            name: universeEvent.agent_name || '',
            tools: (universeEvent.data.tools as unknown[]) || null,
          };
          agentInfoRef.current = updated;
          setAgentInfo(updated);
          break;
        }

        case 'turn_start': {
          const updated = {
            ...agentInfoRef.current,
            currentTurn: (universeEvent.data.turn as number) || 0,
            maxTurns: (universeEvent.data.max_turns as number) || agentInfoRef.current.maxTurns,
          };
          agentInfoRef.current = updated;
          setAgentInfo(updated);
          break;
        }

        case 'llm_response': {
          const text = (universeEvent.data.text as string) || '';
          const usage = universeEvent.data.usage as Record<string, number> | undefined;
          lastResponseRef.current = text;
          setLastResponse(text);
          llmCallCountRef.current += 1;
          const updated = {
            ...agentInfoRef.current,
            llmCallCount: agentInfoRef.current.llmCallCount + 1,
            totalInputTokens: agentInfoRef.current.totalInputTokens + (usage?.input_tokens || 0),
            totalOutputTokens: agentInfoRef.current.totalOutputTokens + (usage?.output_tokens || 0),
          };
          agentInfoRef.current = updated;
          setAgentInfo(updated);
          break;
        }

        case 'iteration_detail': {
          const d = universeEvent.data;
          const call: LLMCallDetail = {
            id: crypto.randomUUID(),
            turnNumber: (d.turn_number as number) || 1,
            iterationNumber: (d.iteration as number) || 0,
            systemPrompt: (d.system_prompt as string) || '',
            messagesSent: (d.messages_sent as Array<{ role: string; content: unknown }>) || [],
            toolsAvailable: (d.tools_available as unknown[]) || null,
            model: (d.model as string) || '',
            maxTokens: (d.max_tokens as number) || 4096,
            responseContent: (d.response_content as unknown[]) || [],
            stopReason: (d.stop_reason as string) || '',
            inputTokens: ((d.usage as Record<string, number>)?.input_tokens) || 0,
            outputTokens: ((d.usage as Record<string, number>)?.output_tokens) || 0,
            toolCalls: (d.tool_calls as Array<{ name: string; input: unknown; result: unknown }>) || [],
            startedAt: (d.started_at as string) || '',
            durationMs: (d.duration_ms as number) || 0,
          };
          llmCallsRef.current = [...llmCallsRef.current, call];
          setLlmCalls(llmCallsRef.current);
          break;
        }

        case 'agent_done':
          finalize();
          break;

        case 'agent_error': {
          const errMsg = (universeEvent.data.error as string) || 'Agent error';
          setError(errMsg);
          finalize(errMsg);
          break;
        }
      }
    };
  }, [universeId, finalize]);

  // REST poll: when universeId changes, poll /api/universes to catch already-completed agents.
  // The WS snapshot arrives on connect (before universeId is set), so we can't rely on it.
  // Poll every 2s while the agent hasn't finished, to detect completion even if WS events were missed.
  useEffect(() => {
    if (!universeId) return;

    let cancelled = false;
    pollStartRef.current = Date.now();

    async function poll() {
      try {
        const res = await fetch(`${API_BASE}/api/universes`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const universes = await res.json() as Array<{
          id: string;
          agents?: Array<{ status: string; name?: string; model?: string | null; role?: string; current_turn?: number; error?: string }>;
        }>;
        if (cancelled) return;

        const universe = universes.find((u) => u.id === universeId);
        if (!universe) return;

        const agent = universe.agents?.[0];
        if (!agent) return;

        // Populate agent info from REST data
        setAgentInfo((prev) => ({
          ...prev,
          name: agent.name || prev.name,
          model: agent.model ?? prev.model,
          role: agent.role || prev.role,
          currentTurn: agent.current_turn ?? prev.currentTurn,
        }));

        if (agent.status === 'completed') {
          const elapsed = Date.now() - pollStartRef.current;
          if (llmCallCountRef.current > 0 || elapsed > 10_000) {
            // WS events have arrived (or safety timeout exceeded) — safe to finalize
            finalize();
            return; // stop polling
          }
          // REST sees 'completed' but WS events haven't arrived yet — re-poll shortly
          if (!cancelled) {
            pollTimer = setTimeout(poll, 500);
          }
          return;
        } else if (agent.status === 'error') {
          const errMsg = agent.error || 'Agent error';
          setError(errMsg);
          finalize(errMsg);
          return; // stop polling
        }
      } catch {
        // Network error — ignore, will retry
      }

      // Poll again in 2s if still active
      if (!cancelled) {
        pollTimer = setTimeout(poll, 2000);
      }
    }

    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    // Initial poll after a short delay (give WS events a chance to arrive first)
    pollTimer = setTimeout(poll, 500);

    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [universeId, finalize]);

  return { events, isConnected, lastResponse, isDone, error, agentInfo, llmCalls, doneSnapshot };
}
