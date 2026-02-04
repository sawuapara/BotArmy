import { useEffect, useRef, useState, useCallback } from 'react';
import type { WSMessage, OrchestratorState } from '../types';

export function useWebSocket(sessionId: string | null) {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [state, setState] = useState<OrchestratorState | null>(null);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const wsUrl = `ws://localhost:8000/ws/${sessionId}`;
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      setIsConnected(true);
      console.log('WebSocket connected');
    };

    ws.current.onclose = () => {
      setIsConnected(false);
      console.log('WebSocket disconnected');
    };

    ws.current.onmessage = (event) => {
      const message: WSMessage = JSON.parse(event.data);
      setLastMessage(message);

      switch (message.type) {
        case 'initial_state':
          setState(message.state);
          break;
        case 'state_update':
          setState((prev) =>
            prev
              ? {
                  ...prev,
                  current_node: message.node,
                  thought_log: message.thought_log,
                  current_ticket: message.current_ticket,
                }
              : null
          );
          break;
        case 'queue_updated':
          setState((prev) =>
            prev ? { ...prev, ticket_queue: message.queue } : null
          );
          break;
        case 'completed':
          setState(message.state);
          break;
        case 'error':
          setState((prev) =>
            prev ? { ...prev, error: message.error } : null
          );
          break;
      }
    };

    return () => {
      ws.current?.close();
    };
  }, [sessionId]);

  const sendInterrupt = useCallback((reason: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'interrupt', reason }));
    }
  }, []);

  return { isConnected, state, lastMessage, sendInterrupt };
}
