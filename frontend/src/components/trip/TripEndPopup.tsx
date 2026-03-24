import { useState, useEffect } from "react";

// Auto-popup that appears when a trip ends.
// Slides up from bottom, shows the receipt, auto-dismisses after 8s.

interface TripEndData {
  trip_id: number;
  distance_miles: number;
  fuel_gallons: number;
  fuel_cost_usd: number;
  avg_mpg: number | null;
  duration_minutes: number;
}

// Singleton event bus for trip-end events (set from useVehicleSocket)
let _listener: ((data: TripEndData) => void) | null = null;
export function emitTripEnd(data: TripEndData) { _listener?.(data); }

export function TripEndPopup() {
  const [trip, setTrip] = useState<TripEndData | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    _listener = (data) => {
      setTrip(data);
      setVisible(true);
    };
    return () => { _listener = null; };
  }, []);

  // Auto-dismiss after 8 seconds
  useEffect(() => {
    if (!visible) return;
    const t = setTimeout(() => setVisible(false), 8000);
    return () => clearTimeout(t);
  }, [visible]);

  if (!visible || !trip) return null;

  return (
    <div
      onClick={() => setVisible(false)}
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
        display: "flex", alignItems: "flex-end", justifyContent: "center",
        padding: "0 20px 24px",
        animation: "fade-in 400ms ease",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%", maxWidth: 500, padding: "16px 20px",
          borderRadius: 14, background: "rgba(20,20,20,0.95)",
          border: "1px solid rgba(255,255,255,0.06)",
          animation: "slide-up 400ms cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {/* Rune voice */}
        <div style={{
          fontFamily: "var(--font-ui)", fontSize: 14, color: "rgba(255,255,255,0.4)",
          marginBottom: 12, fontStyle: "italic",
        }}>
          {trip.distance_miles > 5
            ? `That was ${trip.distance_miles.toFixed(1)} miles for $${trip.fuel_cost_usd.toFixed(2)}. ${trip.avg_mpg ? `${trip.avg_mpg.toFixed(0)} MPG average.` : ""}`
            : `Quick run. ${trip.distance_miles.toFixed(1)} miles, $${trip.fuel_cost_usd.toFixed(2)}.`
          }
        </div>

        {/* Stats row */}
        <div style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
          {[
            { label: "DIST", value: `${trip.distance_miles.toFixed(1)} mi` },
            { label: "FUEL", value: `${trip.fuel_gallons.toFixed(2)} gal` },
            { label: "COST", value: `$${trip.fuel_cost_usd.toFixed(2)}` },
            { label: "MPG", value: trip.avg_mpg ? trip.avg_mpg.toFixed(0) : "--" },
            { label: "TIME", value: `${Math.round(trip.duration_minutes)}m` },
          ].map(({ label, value }) => (
            <div key={label} style={{ textAlign: "center", flex: 1 }}>
              <div style={{ fontFamily: "var(--font-data)", fontSize: 20, fontWeight: 700, color: "rgba(255,255,255,0.85)", fontVariantNumeric: "tabular-nums" }}>{value}</div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.2)", marginTop: 2 }}>{label}</div>
            </div>
          ))}
        </div>

        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.1)", textAlign: "center", marginTop: 10 }}>
          tap to dismiss
        </div>
      </div>
    </div>
  );
}
