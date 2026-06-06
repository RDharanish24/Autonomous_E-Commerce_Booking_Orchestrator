import { useEffect, useRef } from 'react';
import { useStore } from '../store/useStore';

export const useOrchestratorSocket = () => {
  const { clientId, setConnectionStatus, addLog, setFinalDecision } = useStore();
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const connect = () => {
      // Connect to the new FastAPI WebSocket endpoint
      const socketUrl = `ws://localhost:8000/ws/${clientId}`;
      ws.current = new WebSocket(socketUrl);

      ws.current.onopen = () => {
        console.log(`[WS] Connected with ID: ${clientId}`);
        setConnectionStatus(true);
        if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // 1. Add granular status to the Live Activity Feed
          addLog({
            timestamp: new Date().toISOString(),
            status: data.status,
            payload: data.payload,
          });

          // 2. If the AI reached a decision or fallback, set the final decision
          if (data.status === 'Optimal Decision Reached' || data.status === 'Human Review Required') {
             // In fallback, the payload might be {"error": ..., "phase": ...}
             // For success, it is {"decision": {...}}
             setFinalDecision(data.payload.decision || data.payload);
          }
        } catch (err) {
          console.error('[WS] Failed to parse message', err);
        }
      };

      ws.current.onclose = () => {
        console.log('[WS] Disconnected. Reconnecting in 3s...');
        setConnectionStatus(false);
        // Exponential backoff or fixed reconnect logic
        reconnectTimeout.current = setTimeout(connect, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('[WS ERROR]', error);
        ws.current?.close(); // Force onclose to trigger reconnect
      };
    };

    connect();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) ws.current.close();
    };
  }, [clientId, setConnectionStatus, addLog, setFinalDecision]);

  return ws.current;
};
