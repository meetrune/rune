import { useEffect, useRef } from "react";
import { useVehicleStore } from "@/stores/vehicleStore";

function RadialGauge({
  label,
  sensorKey,
  min,
  max,
  format,
  unit,
  warnAt,
  critAt,
}: {
  label: string;
  sensorKey: string;
  min: number;
  max: number;
  format?: (v: number) => string;
  unit?: string;
  warnAt?: number;
  critAt?: number;
}) {
  const valueRef = useRef<HTMLDivElement>(null);
  const arcRef = useRef<SVGCircleElement>(null);

  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75; // 270-degree arc

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const reading = state.sensors[sensorKey];
      const val = reading?.v ?? 0;

      if (valueRef.current) {
        valueRef.current.textContent = reading
          ? (format ? format(val) : val.toFixed(0))
          : "--";

        // Color based on thresholds
        if (critAt !== undefined && val >= critAt) {
          valueRef.current.style.color = "var(--rune-critical)";
        } else if (warnAt !== undefined && val >= warnAt) {
          valueRef.current.style.color = "var(--rune-warn)";
        } else {
          valueRef.current.style.color = "var(--rune-text)";
        }
      }

      if (arcRef.current) {
        const pct = Math.min(1, Math.max(0, (val - min) / (max - min)));
        const offset = arcLength * (1 - pct);
        arcRef.current.style.strokeDashoffset = offset.toString();

        // Arc color
        if (critAt !== undefined && val >= critAt) {
          arcRef.current.style.stroke = "var(--rune-critical)";
        } else if (warnAt !== undefined && val >= warnAt) {
          arcRef.current.style.stroke = "var(--rune-warn)";
        } else {
          arcRef.current.style.stroke = "var(--rune-primary)";
        }
      }
    });
    return unsub;
  }, [sensorKey, format, min, max, arcLength, warnAt, critAt]);

  return (
    <div
      style={{
        background: "linear-gradient(145deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.005) 100%)",
        borderRadius: "20px",
        border: "1px solid rgba(255,255,255,0.04)",
        padding: "16px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        minHeight: "140px",
      }}
    >
      {/* SVG gauge arc */}
      <svg
        width="96"
        height="96"
        viewBox="0 0 100 100"
        style={{ transform: "rotate(135deg)" }}
      >
        {/* Background arc */}
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.04)"
          strokeWidth="4"
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeLinecap="round"
        />
        {/* Value arc */}
        <circle
          ref={arcRef}
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="var(--rune-primary)"
          strokeWidth="4"
          strokeDasharray={`${arcLength} ${circumference}`}
          strokeDashoffset={arcLength.toString()}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.3s ease-out, stroke 0.3s" }}
        />
      </svg>

      {/* Value overlay centered on gauge */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -60%)",
          textAlign: "center",
        }}
      >
        <div
          ref={valueRef}
          style={{
            fontFamily: "var(--font-data)",
            fontSize: "28px",
            fontWeight: 600,
            color: "var(--rune-text)",
            lineHeight: 1,
          }}
        >
          --
        </div>
        {unit && (
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "9px",
              color: "var(--rune-text-muted)",
              marginTop: "3px",
              letterSpacing: "0.08em",
            }}
          >
            {unit}
          </div>
        )}
      </div>

      {/* Label at bottom */}
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "10px",
          letterSpacing: "0.12em",
          color: "var(--rune-text-muted)",
          textTransform: "uppercase",
          marginTop: "-4px",
        }}
      >
        {label}
      </span>
    </div>
  );
}

function HeroFuelCard() {
  const mpgRef = useRef<HTMLDivElement>(null);
  const mpgLabelRef = useRef<HTMLDivElement>(null);
  const tripDistRef = useRef<HTMLDivElement>(null);
  const tripCostRef = useRef<HTMLDivElement>(null);
  const tankRef = useRef<HTMLDivElement>(null);
  const tankBarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsub = useVehicleStore.subscribe((state) => {
      const { fuel } = state;
      if (mpgRef.current && mpgLabelRef.current) {
        if (fuel.instant_mpg !== null) {
          mpgRef.current.textContent = fuel.instant_mpg.toFixed(1);
          mpgLabelRef.current.textContent = "MPG";
          // Color
          if (fuel.instant_mpg > 30) {
            mpgRef.current.style.color = "var(--rune-primary)";
          } else if (fuel.instant_mpg > 20) {
            mpgRef.current.style.color = "var(--rune-warn)";
          } else {
            mpgRef.current.style.color = "var(--rune-critical)";
          }
        } else if (fuel.idle_gph !== null) {
          mpgRef.current.textContent = fuel.idle_gph.toFixed(2);
          mpgLabelRef.current.textContent = "GPH IDLE";
          mpgRef.current.style.color = "var(--rune-text-muted)";
        } else {
          mpgRef.current.textContent = "--";
          mpgLabelRef.current.textContent = "MPG";
          mpgRef.current.style.color = "var(--rune-text-muted)";
        }
      }
      if (tripDistRef.current) {
        tripDistRef.current.textContent = fuel.trip_distance_mi.toFixed(1);
      }
      if (tripCostRef.current) {
        tripCostRef.current.textContent = "$" + fuel.trip_cost_usd.toFixed(2);
      }
      if (tankRef.current) {
        tankRef.current.textContent = fuel.tank_pct.toFixed(0) + "%";
      }
      if (tankBarRef.current) {
        tankBarRef.current.style.width = `${Math.min(100, Math.max(0, fuel.tank_pct))}%`;
      }
    });
    return unsub;
  }, []);

  return (
    <div
      style={{
        background: "linear-gradient(160deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.01) 100%)",
        borderRadius: "24px",
        border: "1px solid rgba(255,255,255,0.05)",
        padding: "28px",
        display: "flex",
        flexDirection: "column",
        gap: "20px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Subtle gradient accent */}
      <div
        style={{
          position: "absolute",
          top: "-40px",
          right: "-40px",
          width: "120px",
          height: "120px",
          borderRadius: "50%",
          background: "var(--rune-primary)",
          opacity: 0.03,
          filter: "blur(40px)",
        }}
      />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div
            ref={mpgLabelRef}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "11px",
              letterSpacing: "0.15em",
              color: "var(--rune-text-muted)",
              textTransform: "uppercase",
              marginBottom: "6px",
            }}
          >
            MPG
          </div>
          <div
            ref={mpgRef}
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "64px",
              fontWeight: 700,
              color: "var(--rune-text-muted)",
              lineHeight: 0.9,
              letterSpacing: "-0.02em",
            }}
          >
            --
          </div>
        </div>

        {/* Trip stats */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "8px", paddingTop: "4px" }}>
          <div style={{ textAlign: "right" }}>
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "9px",
                color: "var(--rune-text-muted)",
                opacity: 0.6,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Trip
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
              <span
                ref={tripDistRef}
                style={{
                  fontFamily: "var(--font-data)",
                  fontSize: "22px",
                  fontWeight: 500,
                  color: "var(--rune-text)",
                }}
              >
                0.0
              </span>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "10px",
                  color: "var(--rune-text-muted)",
                }}
              >
                mi
              </span>
            </div>
          </div>
          <div
            ref={tripCostRef}
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "18px",
              fontWeight: 400,
              color: "var(--rune-text-muted)",
            }}
          >
            $0.00
          </div>
        </div>
      </div>

      {/* Tank bar */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "10px",
              color: "var(--rune-text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              opacity: 0.6,
            }}
          >
            Tank
          </span>
          <span
            ref={tankRef}
            style={{
              fontFamily: "var(--font-data)",
              fontSize: "13px",
              fontWeight: 500,
              color: "var(--rune-text-muted)",
            }}
          >
            0%
          </span>
        </div>
        <div
          style={{
            width: "100%",
            height: "4px",
            borderRadius: "2px",
            background: "rgba(255,255,255,0.04)",
            overflow: "hidden",
          }}
        >
          <div
            ref={tankBarRef}
            style={{
              width: "0%",
              height: "100%",
              borderRadius: "2px",
              background: `linear-gradient(90deg, var(--rune-primary), var(--rune-primary))`,
              transition: "width 0.5s ease-out",
              boxShadow: `0 0 8px var(--rune-primary)40`,
            }}
          />
        </div>
      </div>
    </div>
  );
}

export function DashboardScreen() {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "var(--rune-bg)",
        padding: "calc(20px + env(safe-area-inset-top)) 16px 16px",
        overflowY: "auto",
        overflowX: "hidden",
        display: "flex",
        flexDirection: "column",
        gap: "14px",
        scrollbarWidth: "none",
      }}
    >
      {/* Fuel hero */}
      <HeroFuelCard />

      {/* Gauge grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "12px",
        }}
      >
        <RadialGauge label="RPM" sensorKey="RPM" min={0} max={7000} unit="rpm" warnAt={5500} critAt={6500} />
        <RadialGauge label="Speed" sensorKey="SPEED" min={0} max={200} format={(v) => Math.round(v * 0.621371).toString()} unit="mph" />
        <RadialGauge label="Coolant" sensorKey="COOLANT_TEMP" min={-40} max={130} format={(v) => v.toFixed(0)} unit="\u00B0C" warnAt={100} critAt={110} />
        <RadialGauge label="Oil" sensorKey="OIL_TEMP" min={-40} max={150} format={(v) => v.toFixed(0)} unit="\u00B0C" warnAt={120} critAt={140} />
        <RadialGauge label="Throttle" sensorKey="THROTTLE_POS" min={0} max={100} format={(v) => v.toFixed(0)} unit="%" />
        <RadialGauge label="Load" sensorKey="ENGINE_LOAD" min={0} max={100} format={(v) => v.toFixed(0)} unit="%" warnAt={85} critAt={95} />
        <RadialGauge label="Battery" sensorKey="BATTERY_V" min={10} max={16} format={(v) => v.toFixed(1)} unit="V" />
        <RadialGauge label="Catalyst" sensorKey="CATALYST_TEMP" min={0} max={800} format={(v) => v.toFixed(0)} unit="\u00B0C" warnAt={600} critAt={750} />
      </div>
    </div>
  );
}
