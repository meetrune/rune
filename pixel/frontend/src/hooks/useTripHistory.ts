import { useState, useEffect, useCallback, useRef } from "react";

export interface TripStats {
  idle_seconds: number;
  idle_fuel_gal: number;
  warmup_seconds: number;
  warmup_fuel_gal: number;
  max_mpg: number | null;
  min_mpg: number | null;
  stft_spikes: number;
  max_stft: number;
  peak_load_pct: number;
  peak_rpm: number;
  avg_speed_mph: number;
}

export interface Trip {
  trip_id: number;
  start_time: number;  // Unix ms
  end_time: number | null;
  distance_miles: number;
  fuel_gallons: number;
  fuel_cost_usd: number;
  avg_mpg: number | null;
  eco_score: number | null;
  trip_stats: TripStats | null;
}

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 5000;

export function useTripHistory() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const retryCount = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout>>(null);

  const refresh = useCallback((signal?: AbortSignal) => {
    setLoading(true);
    setError(false);
    fetch("/api/trips?limit=50", signal ? { signal } : undefined)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        setTrips(data.trips ?? []);
        setLoading(false);
        retryCount.current = 0;
      })
      .catch((err) => {
        if (err.name === "AbortError") return;
        setLoading(false);
        setError(true);
        // Auto-retry up to MAX_RETRIES
        if (retryCount.current < MAX_RETRIES) {
          retryCount.current++;
          retryTimer.current = setTimeout(refresh, RETRY_DELAY_MS);
        }
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal);
    return () => {
      controller.abort();
      if (retryTimer.current) clearTimeout(retryTimer.current);
    };
  }, [refresh]);

  return { trips, loading, error, refresh };
}
