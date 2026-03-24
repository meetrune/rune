import { useState } from "react";
import { useTripHistory, type Trip } from "@/hooks/useTripHistory";
import { useSettingsStore } from "@/stores/settingsStore";

const MONO = "'JetBrains Mono', 'SF Mono', monospace";

function formatDate(ms: number): string {
  const diffDays = Math.floor((Date.now() - ms) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return new Date(ms).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function dur(startMs: number, endMs: number | null): string {
  if (!endMs) return "--";
  const m = Math.round((endMs - startMs) / 60000);
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h${m % 60 > 0 ? ` ${m % 60}m` : ""}`;
}

function mpgColor(mpg: number | null): string {
  if (!mpg) return "rgba(255,255,255,0.15)";
  if (mpg >= 33) return "#4ade80";
  if (mpg >= 28) return "#c9952a";
  if (mpg >= 22) return "#f59e0b";
  return "#ef4444";
}

// Big arc gauge
function BigArc({ mpg }: { mpg: number | null }) {
  const r = 52, cx = 60, cy = 60, sz = 120;
  const circ = 2 * Math.PI * r, arc = circ * 0.75;
  const pct = mpg != null ? Math.min(mpg / 50, 1) : 0;
  const color = mpgColor(mpg);
  return (
    <div style={{ position: "relative", width: sz, height: sz, flexShrink: 0 }}>
      <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="6"
          strokeDasharray={`${arc} ${circ}`} strokeLinecap="round" transform={`rotate(135 ${cx} ${cy})`} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${arc} ${circ}`} strokeDashoffset={arc - pct * arc} strokeLinecap="round"
          transform={`rotate(135 ${cx} ${cy})`} style={{ transition: "all 600ms ease", filter: `drop-shadow(0 0 10px ${color}30)` }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontFamily: MONO, fontSize: 42, fontWeight: 700, color, lineHeight: 1 }}>{mpg != null ? Math.round(mpg) : "--"}</span>
        <span style={{ fontSize: 14, color: "rgba(255,255,255,0.4)", marginTop: 2 }}>MPG</span>
      </div>
    </div>
  );
}

// MPG range bar: visual min---[avg]---max
function MpgRangeBar({ min, max, avg }: { min: number; max: number; avg: number }) {
  const lo = Math.max(min - 4, 0), hi = max + 4;
  const range = hi - lo || 1;
  const minPct = ((min - lo) / range) * 100;
  const maxPct = ((max - lo) / range) * 100;
  const avgPct = ((avg - lo) / range) * 100;

  return (
    <div style={{ padding: "12px 0 8px" }}>
      <div style={{ fontSize: 14, color: "rgba(255,255,255,0.45)", marginBottom: 10 }}>MPG range during trip</div>
      {/* Numbers above the bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6, padding: "0 4px" }}>
        <div>
          <span style={{ fontFamily: MONO, fontSize: 18, fontWeight: 700, color: "#ef4444" }}>{min}</span>
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.3)", marginLeft: 4 }}>worst</span>
        </div>
        <div style={{ textAlign: "center" }}>
          <span style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600, color: "#c9952a" }}>{Math.round(avg)}</span>
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.3)", marginLeft: 4 }}>avg</span>
        </div>
        <div>
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.3)", marginRight: 4 }}>best</span>
          <span style={{ fontFamily: MONO, fontSize: 18, fontWeight: 700, color: "#4ade80" }}>{max}</span>
        </div>
      </div>
      {/* Gradient bar */}
      <div style={{ position: "relative", height: 10, background: "rgba(255,255,255,0.03)", borderRadius: 5 }}>
        <div style={{
          position: "absolute", top: 1, bottom: 1, borderRadius: 4,
          left: `${minPct}%`, width: `${Math.max(maxPct - minPct, 2)}%`,
          background: "linear-gradient(90deg, #ef4444, #f59e0b, #4ade80)",
          opacity: 0.5,
        }} />
        <div style={{
          position: "absolute", top: -3, width: 3, height: 16, borderRadius: 2,
          background: "#c9952a", left: `${avgPct}%`,
          boxShadow: "0 0 6px rgba(201,149,42,0.4)",
        }} />
      </div>
    </div>
  );
}

// Time split donut: driving vs idle
function TimeSplitRing({ drivingSec, idleSec }: { drivingSec: number; idleSec: number }) {
  const total = drivingSec + idleSec || 1;
  const drivePct = drivingSec / total;
  const r = 24, cx = 28, cy = 28, circ = 2 * Math.PI * r;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
      <svg width={56} height={56} viewBox="0 0 56 56" style={{ flexShrink: 0 }}>
        {/* Idle arc (amber) */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(245,158,11,0.3)" strokeWidth="5"
          strokeDasharray={`${circ} ${circ}`} transform={`rotate(-90 ${cx} ${cy})`} />
        {/* Driving arc (green) on top */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#4ade80" strokeWidth="5"
          strokeDasharray={`${drivePct * circ} ${circ}`} strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`} style={{ transition: "all 400ms" }} />
      </svg>
      <div style={{ flex: 1, display: "flex", gap: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#4ade80" }} />
            <span style={{ fontSize: 15, color: "rgba(255,255,255,0.5)" }}>Moving</span>
          </div>
          <span style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, color: "#4ade80" }}>
            {Math.round(drivingSec / 60)}m
          </span>
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} />
            <span style={{ fontSize: 15, color: "rgba(255,255,255,0.5)" }}>Idle</span>
          </div>
          <span style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, color: "#f59e0b" }}>
            {Math.round(idleSec / 60)}m
          </span>
        </div>
      </div>
    </div>
  );
}

// Horizontal bar chart item
function BarMetric({ label, value, unit, pct, color }: {
  label: string; value: string; unit?: string; pct: number; color: string;
}) {
  return (
    <div style={{ padding: "6px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
        <span style={{ fontSize: 15, color: "rgba(255,255,255,0.5)" }}>{label}</span>
        <span style={{ fontFamily: MONO, fontSize: 20, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
          {value}{unit && <span style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", marginLeft: 3 }}>{unit}</span>}
        </span>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: "rgba(255,255,255,0.03)" }}>
        <div style={{
          height: "100%", borderRadius: 4, background: color, opacity: 0.5,
          width: `${Math.min(pct * 100, 100)}%`, transition: "width 500ms ease",
        }} />
      </div>
    </div>
  );
}

function SectionLabel({ text }: { text: string }) {
  return (
    <div style={{
      fontSize: 14, fontFamily: MONO, fontWeight: 600, color: "rgba(255,255,255,0.25)",
      letterSpacing: "0.06em", padding: "14px 0 8px",
      borderTop: "1px solid rgba(255,255,255,0.04)", marginTop: 4,
    }}>{text}</div>
  );
}

function TripDetail({ trip, avgMpg, avgCostPerMi }: { trip: Trip; avgMpg: number; avgCostPerMi: number }) {
  const s = trip.trip_stats;
  const gp = useSettingsStore((st) => st.gasPricePerGallon);
  const costPerMi = trip.distance_miles > 0 ? trip.fuel_cost_usd / trip.distance_miles : 0;
  const co2Kg = trip.fuel_gallons * 8.89;
  const durationSec = trip.end_time ? (trip.end_time - trip.start_time) / 1000 : 0;
  const drivingSec = s ? Math.max(0, durationSec - s.idle_seconds) : durationSec;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, animation: "fade-in 300ms ease" }}>
      {/* Hero: gauge + big numbers */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <BigArc mpg={trip.avg_mpg} />
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
          {[
            { l: "DISTANCE", v: trip.distance_miles.toFixed(1), u: "mi" },
            { l: "COST", v: `$${trip.fuel_cost_usd.toFixed(2)}`, c: "#c9952a" },
            { l: "FUEL", v: trip.fuel_gallons.toFixed(2), u: "gal" },
            { l: "DURATION", v: dur(trip.start_time, trip.end_time) },
          ].map(({ l, v, u, c }) => (
            <div key={l}>
              <div style={{ fontSize: 14, color: "rgba(255,255,255,0.4)" }}>{l}</div>
              <div style={{ fontFamily: MONO, fontSize: 24, fontWeight: 700, color: c ?? "rgba(255,255,255,0.8)", fontVariantNumeric: "tabular-nums" }}>
                {v}{u && <span style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", marginLeft: 2 }}>{u}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Rune voice */}
      <div style={{ fontSize: 15, color: "rgba(255,255,255,0.4)", fontFamily: "var(--font-ui)", fontStyle: "italic", padding: "4px 0" }}>
        {trip.avg_mpg != null && trip.avg_mpg > avgMpg + 2
          ? `${(trip.avg_mpg - avgMpg).toFixed(0)} MPG above your average. Efficient run.`
          : trip.avg_mpg != null && trip.avg_mpg < avgMpg - 3
          ? `Below average by ${(avgMpg - trip.avg_mpg).toFixed(0)} MPG. Probably stop-and-go.`
          : trip.avg_mpg != null
          ? `Typical run for you.`
          : `No fuel data for this trip.`}
      </div>

      {/* MPG RANGE -- gradient bar visualization */}
      {s && s.max_mpg !== null && s.min_mpg !== null && (
        <MpgRangeBar min={s.min_mpg} max={s.max_mpg} avg={trip.avg_mpg ?? 28} />
      )}

      {/* TIME SPLIT -- donut chart */}
      {s && durationSec > 0 && (
        <>
          <SectionLabel text="TIME SPLIT" />
          <TimeSplitRing drivingSec={drivingSec} idleSec={s.idle_seconds} />
          {s.idle_fuel_gal > 0.005 && (
            <div style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", padding: "4px 0" }}>
              Idling burned ${(s.idle_fuel_gal * gp).toFixed(2)} sitting still
            </div>
          )}
        </>
      )}

      {/* ENGINE -- bar charts */}
      {s && (
        <>
          <SectionLabel text="ENGINE" />
          <BarMetric label="Peak load" value={`${Math.round(s.peak_load_pct)}`} unit="%" pct={s.peak_load_pct / 100}
            color={s.peak_load_pct < 70 ? "#60a5fa" : "#f59e0b"} />
          <BarMetric label="Peak RPM" value={Math.round(s.peak_rpm).toLocaleString()} pct={s.peak_rpm / 6500}
            color={s.peak_rpm < 4000 ? "#60a5fa" : "#f59e0b"} />
          <BarMetric label="Fuel trim stress" value={`${s.max_stft.toFixed(1)}`} unit="%" pct={s.max_stft / 25}
            color={s.max_stft < 5 ? "#4ade80" : s.max_stft < 10 ? "#c9952a" : "#ef4444"} />
        </>
      )}

      {/* COST + ENVIRONMENT */}
      <SectionLabel text="COST + IMPACT" />
      <BarMetric label="Cost per mile" value={`$${costPerMi.toFixed(2)}`} pct={costPerMi / 0.25}
        color={costPerMi < avgCostPerMi ? "#4ade80" : "#c9952a"} />
      <BarMetric label="CO2 produced" value={co2Kg.toFixed(1)} unit="kg" pct={co2Kg / 10}
        color="rgba(255,255,255,0.4)" />
    </div>
  );
}

export function TripSummaryScreen() {
  const { trips, loading } = useTripHistory();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = trips.find((t) => t.trip_id === selectedId);

  const ct = trips.filter((t) => t.end_time && t.avg_mpg);
  const avgMpg = ct.length > 0 ? ct.reduce((s, t) => s + (t.avg_mpg ?? 0), 0) / ct.length : 28;
  const avgCpm = ct.length > 0 ? ct.reduce((s, t) => s + (t.distance_miles > 0 ? t.fuel_cost_usd / t.distance_miles : 0), 0) / ct.length : 0.12;

  return (
    <div style={{ width: "100%", height: "100%", background: "#000", display: "flex", overflow: "hidden" }}>
      {/* Left: trip list */}
      <div style={{
        width: "26%", minWidth: 150, display: "flex", flexDirection: "column",
        borderRight: "1px solid rgba(255,255,255,0.04)",
      }}>
        <div style={{ padding: "10px 14px 6px" }}>
          <span style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.4)", letterSpacing: "0.06em" }}>TRIPS</span>
        </div>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && <div style={{ color: "rgba(255,255,255,0.2)", fontSize: 16, padding: 30, textAlign: "center" }}>Loading...</div>}
          {!loading && trips.length === 0 && <div style={{ color: "rgba(255,255,255,0.2)", fontSize: 16, padding: 30, textAlign: "center" }}>No trips yet.</div>}
          {trips.map((trip) => {
            const active = trip.trip_id === selectedId;
            const color = mpgColor(trip.avg_mpg);
            return (
              <button
                key={trip.trip_id}
                onClick={() => setSelectedId(active ? null : trip.trip_id)}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  width: "100%", padding: "10px 12px",
                  background: active ? `${color}08` : "transparent",
                  border: "none", borderBottom: "1px solid rgba(255,255,255,0.03)",
                  borderLeft: active ? `3px solid ${color}` : "3px solid transparent",
                  cursor: "pointer", textAlign: "left",
                  minHeight: 60, WebkitTapHighlightColor: "transparent", transition: "all 200ms",
                }}
              >
                <div>
                  <div style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600, color: active ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.45)" }}>
                    {formatDate(trip.start_time)}
                  </div>
                  <div style={{ fontSize: 14, color: "rgba(255,255,255,0.35)", marginTop: 2 }}>
                    {trip.distance_miles.toFixed(1)}mi · ${trip.fuel_cost_usd.toFixed(2)}
                  </div>
                </div>
                <div style={{ fontFamily: MONO, fontSize: 26, fontWeight: 700, color, lineHeight: 1 }}>
                  {trip.avg_mpg != null ? Math.round(trip.avg_mpg) : "--"}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Right: scrollable visual detail */}
      <div style={{ flex: 1, padding: "8px 16px", overflowY: "auto" }}>
        {selected ? (
          <TripDetail trip={selected} avgMpg={avgMpg} avgCostPerMi={avgCpm} />
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "rgba(255,255,255,0.06)", fontSize: 16 }}>
            Tap a trip
          </div>
        )}
      </div>
    </div>
  );
}
