import { useEffect, useRef, useState } from 'react';
import type { Universe, UniverseEvent } from '../types';

const MAX_EVENTS = 200;

export function useUniverseStream() {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [universes, setUniverses] = useState<Universe[]>([]);
  const [events, setEvents] = useState<UniverseEvent[]>([]);

  useEffect(() => {
    const port = import.meta.env.VITE_API_PORT || '8000';
    const wsUrl = `ws://localhost:${port}/ws/universes`;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      const socket = new WebSocket(wsUrl);
      ws.current = socket;

      socket.onopen = () => {
        setIsConnected(true);
      };

      socket.onclose = () => {
        setIsConnected(false);
        // Auto-reconnect after 5s
        reconnectTimer = setTimeout(connect, 5000);
      };

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'snapshot') {
          // Initial snapshot of all universes
          setUniverses(data.universes || []);
          return;
        }

        // It's a streaming event — update universes and add to event log
        const universeEvent = data as UniverseEvent;

        setEvents((prev) => {
          const next = [...prev, universeEvent];
          return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
        });

        // Update universe state from events
        setUniverses((prev) => {
          const updated = [...prev];

          if (universeEvent.type === 'universe_created') {
            const exists = updated.find((u) => u.id === universeEvent.universe_id);
            if (!exists) {
              updated.push({
                id: universeEvent.universe_id,
                name: (universeEvent.data.name as string) || '',
                dimension_id: (universeEvent.data.dimension_id as string) || null,
                status: 'active',
                worker_id: universeEvent.worker_id || '',
                agents: [],
                state_version: 0,
                created_at: universeEvent.timestamp,
              });
            }
          } else if (universeEvent.type === 'universe_stopped') {
            const u = updated.find((u) => u.id === universeEvent.universe_id);
            if (u) u.status = 'terminated';
          } else if (universeEvent.type === 'agent_started') {
            const u = updated.find((u) => u.id === universeEvent.universe_id);
            if (u) {
              const existing = u.agents.find((a) => a.id === universeEvent.agent_id);
              if (!existing) {
                u.agents.push({
                  id: universeEvent.agent_id || '',
                  name: universeEvent.agent_name || '',
                  role: (universeEvent.data.role as string) || '',
                  model: (universeEvent.data.model as string) || null,
                  status: 'running',
                  current_turn: 0,
                });
              }
            }
          } else if (
            universeEvent.type === 'agent_done' ||
            universeEvent.type === 'agent_error'
          ) {
            const u = updated.find((u) => u.id === universeEvent.universe_id);
            if (u) {
              const agent = u.agents.find((a) => a.id === universeEvent.agent_id);
              if (agent) {
                agent.status =
                  universeEvent.type === 'agent_done' ? 'completed' : 'error';
              }
            }
          } else if (universeEvent.type === 'turn_start') {
            const u = updated.find((u) => u.id === universeEvent.universe_id);
            if (u) {
              const agent = u.agents.find((a) => a.id === universeEvent.agent_id);
              if (agent) {
                agent.current_turn = (universeEvent.data.turn as number) || 0;
              }
            }
          } else if (universeEvent.type === 'turn_end') {
            const u = updated.find((u) => u.id === universeEvent.universe_id);
            if (u) {
              u.state_version =
                (universeEvent.data.state_version as number) || u.state_version;
            }
          }

          return updated;
        });
      };
    }

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws.current?.close();
    };
  }, []);

  return { universes, events, isConnected };
}
