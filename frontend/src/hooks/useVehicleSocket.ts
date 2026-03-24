import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import type { VehicleMessage } from "@/types/vehicle";

const MAX_BACKOFF_MS = 8000;
const HEARTBEAT_TIMEOUT_MS = 3000;

export function useVehicleSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(null);
  const heartbeatTimer = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    const store = useVehicleStore.getState();

    function getUrl(): string {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${location.host}/ws/vehicle-data`;
    }

    function resetHeartbeat() {
      if (heartbeatTimer.current) clearTimeout(heartbeatTimer.current);
      heartbeatTimer.current = setTimeout(() => {
        useVehicleStore.getState().setConnected(false);
      }, HEARTBEAT_TIMEOUT_MS);
    }

    function connect() {
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const ws = new WebSocket(getUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempt.current = 0;
        store.setConnected(true);
        resetHeartbeat();
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(event.data as string) as VehicleMessage;
          useVehicleStore.getState().updateFromMessage(msg);
          resetHeartbeat();
        } catch {
          // Malformed message, skip
        }
      };

      ws.onclose = () => {
        store.setConnected(false);
        if (heartbeatTimer.current) clearTimeout(heartbeatTimer.current);
        scheduleReconnect();
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    function scheduleReconnect() {
      const baseDelay = Math.min(
        1000 * Math.pow(2, reconnectAttempt.current),
        MAX_BACKOFF_MS,
      );
      // Add jitter: 0-500ms
      const jitter = Math.random() * 500;
      const delay = baseDelay + jitter;

      reconnectAttempt.current++;
      reconnectTimer.current = setTimeout(connect, delay);
    }

    connect();

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (heartbeatTimer.current) clearTimeout(heartbeatTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, []);
}
