import { useState, useEffect, useCallback } from "react";

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

export function useTripHistory() {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    setLoading(true);
    fetch("/api/trips?limit=50")
      .then((r) => r.json())
      .then((data) => {
        setTrips(data.trips ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { trips, loading, refresh };
}
