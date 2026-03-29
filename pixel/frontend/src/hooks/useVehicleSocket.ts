import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";
import { emitTripEnd } from "@/components/trip/TripEndPopup";
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
      const state = wsRef.current?.readyState;
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return;

      const ws = new WebSocket(getUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempt.current = 0;
        store.setConnected(true);
        resetHeartbeat();
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string);

          // Trip-end event from backend
          if (data.type === "trip_ended" && data.trip) {
            // Guard against missing fields -- toFixed() on undefined would crash
            const t = data.trip;
            if (typeof t.distance_miles === "number" && typeof t.fuel_gallons === "number") {
              emitTripEnd(t);
            }
            return;
          }

          // Validate message structure before updating store
          // Null d/health/fuel fields would crash downstream components
          if (!data.d || !data.health || !data.fuel || typeof data.t !== "number") return;

          const msg = data as VehicleMessage;
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
