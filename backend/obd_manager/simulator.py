"""Honda Accord 2026 SE OBD-II Simulator.

Generates realistic sensor data for the 1.5T CVT engine, including:
- Exponential coolant warmup curve (tau=180s, like a real L15BE)
- RPM settling from cold-start high idle to normal idle
- Correlated sensors (RPM/MAF/load, coolant/oil lag, CVT ratio)
- Configurable anomaly injection for testing health scoring

This is the stunt double -- it behaves like Rune so we can build and
test everything before the real WiCAN Pro hardware arrives.
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from backend.obd_manager.models import VehicleSnapshot, maf_to_fuel_rate_lph

logger = logging.getLogger(__name__)


class DrivingPhase(Enum):
    """What Rune is doing right now."""
    COLD_START = "cold_start"
    IDLE = "idle"
    CITY = "city"
    HIGHWAY = "highway"
    ACCELERATION = "acceleration"
    DECELERATION = "deceleration"


@dataclass
class AnomalyConfig:
    """Configuration for a simulated fault.

    type: what kind of fault
    start_time: seconds after simulator start to begin the anomaly
    severity: 0.0 (barely noticeable) to 1.0 (full failure)
    duration: how long the anomaly lasts in seconds (0 = permanent)
    """
    type: Literal["coolant_spike", "fuel_trim_drift", "voltage_drop", "rpm_instability", "catalyst_degradation"]
    start_time: float
    severity: float = 0.5
    duration: float = 0.0  # 0 = permanent once started


@dataclass
class SimulatorState:
    """Internal state that evolves over time."""
    # Time tracking
    start_time: float = 0.0
    elapsed: float = 0.0

    # Engine
    rpm: float = 0.0
    target_rpm: float = 700.0

    # Thermal (all start at ambient)
    ambient_temp_c: float = 20.0
    coolant_temp_c: float = 20.0
    oil_temp_c: float = 20.0
    catalyst_temp_c: float = 20.0
    cvt_fluid_temp_c: float = 20.0

    # Drivetrain
    speed_kph: float = 0.0
    target_speed_kph: float = 0.0
    engine_load_pct: float = 20.0
    throttle_pct: float = 0.0

    # Air/fuel
    maf_gps: float = 2.0  # idle MAF ~2-3 g/s for 1.5T
    intake_air_temp_c: float = 20.0
    intake_manifold_kpa: float = 30.0  # vacuum at idle ~30 kPa
    stft_pct: float = 0.0
    ltft_pct: float = 0.0

    # Electrical
    battery_voltage: float = 14.2

    # Fuel
    fuel_level_pct: float = 75.0

    # Phase management
    phase: DrivingPhase = DrivingPhase.COLD_START
    phase_start_time: float = 0.0
    phase_duration: float = 0.0

    # Scenario sequencing
    scenario_index: int = 0


# Honda Accord 1.5T engine constants
IDLE_RPM = 700.0
COLD_START_RPM = 1100.0
RPM_SETTLE_TAU = 30.0  # seconds for RPM to settle from cold start
COOLANT_WARMUP_TAU = 180.0  # seconds for coolant to reach operating temp
COOLANT_OPERATING_C = 90.0
OIL_LAG_SECONDS = 60.0  # oil temp lags coolant by ~60s
CATALYST_WARMUP_TAU = 120.0  # catalyst heats faster than coolant
CATALYST_OPERATING_C = 400.0  # normal catalyst operating temp

# CVT ratio range (Honda CVT)
CVT_RATIO_LOW = 2.5  # low speed / high torque
CVT_RATIO_HIGH = 0.6  # highway cruising

# MAF baseline at idle for 1.5T
IDLE_MAF_GPS = 2.5


class HondaAccordSimulator:
    """Simulates realistic OBD-II data for the 2026 Honda Accord SE.

    Usage:
        sim = HondaAccordSimulator()
        sim.start()
        snapshot = sim.get_snapshot()  # returns VehicleSnapshot
    """

    def __init__(
        self,
        ambient_temp_c: float = 20.0,
        initial_fuel_pct: float = 75.0,
        anomalies: list[AnomalyConfig] | None = None,
        scenario: list[tuple[DrivingPhase, float]] | None = None,
    ) -> None:
        self._state = SimulatorState(
            ambient_temp_c=ambient_temp_c,
            coolant_temp_c=ambient_temp_c,
            oil_temp_c=ambient_temp_c,
            catalyst_temp_c=ambient_temp_c,
            cvt_fluid_temp_c=ambient_temp_c,
            intake_air_temp_c=ambient_temp_c,
            fuel_level_pct=initial_fuel_pct,
        )
        self._anomalies = anomalies or []
        self._running = False
        self._last_update: float = 0.0

        # Default scenario: cold start -> idle -> city -> highway -> idle
        self._scenario = scenario or [
            (DrivingPhase.COLD_START, 60.0),
            (DrivingPhase.IDLE, 30.0),
            (DrivingPhase.CITY, 120.0),
            (DrivingPhase.HIGHWAY, 120.0),
            (DrivingPhase.CITY, 60.0),
            (DrivingPhase.IDLE, 30.0),
        ]

    def start(self) -> None:
        """Start the simulator clock."""
        now = time.monotonic()
        self._state.start_time = now
        self._state.phase_start_time = now
        self._last_update = now
        self._state.rpm = COLD_START_RPM
        self._state.phase = DrivingPhase.COLD_START
        self._state.phase_duration = self._scenario[0][1] if self._scenario else 60.0
        self._state.scenario_index = 0
        self._running = True
        logger.info("Simulator started: ambient=%.1fC, fuel=%.0f%%",
                     self._state.ambient_temp_c, self._state.fuel_level_pct)

    def stop(self) -> None:
        """Stop the simulator."""
        self._running = False
        logger.info("Simulator stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def phase(self) -> DrivingPhase:
        return self._state.phase

    def get_snapshot(self) -> VehicleSnapshot:
        """Get current vehicle state as a validated Pydantic model."""
        if not self._running:
            raise RuntimeError("Simulator not started. Call start() first.")

        now = time.monotonic()
        dt = now - self._last_update
        self._last_update = now
        self._state.elapsed = now - self._state.start_time

        self._advance_scenario(now)
        self._update_driving(dt)
        self._update_thermal(dt)
        self._update_electrical(dt)
        self._update_fuel(dt)
        self._apply_anomalies()
        self._add_noise()

        s = self._state
        return VehicleSnapshot(
            timestamp=time.time(),
            rpm=max(0, s.rpm),
            speed_kph=max(0, s.speed_kph),
            coolant_temp_c=s.coolant_temp_c,
            engine_load_pct=_clamp(s.engine_load_pct, 0, 100),
            throttle_pct=_clamp(s.throttle_pct, 0, 100),
            intake_air_temp_c=s.intake_air_temp_c,
            intake_manifold_kpa=_clamp(s.intake_manifold_kpa, 0, 255),
            maf_gps=max(0, s.maf_gps),
            stft_pct=_clamp(s.stft_pct, -100, 99.2),
            ltft_pct=_clamp(s.ltft_pct, -100, 99.2),
            fuel_level_pct=_clamp(s.fuel_level_pct, 0, 100),
            catalyst_temp_c=max(-40, s.catalyst_temp_c),
            oil_temp_c=_clamp(s.oil_temp_c, -40, 215),
            battery_voltage=_clamp(s.battery_voltage, 0, 65),
            cvt_fluid_temp_c=_clamp(s.cvt_fluid_temp_c, -40, 215),
        )

    def _advance_scenario(self, now: float) -> None:
        """Move to next driving phase when current one expires."""
        s = self._state
        phase_elapsed = now - s.phase_start_time

        if phase_elapsed >= s.phase_duration and s.scenario_index < len(self._scenario) - 1:
            s.scenario_index += 1
            new_phase, new_duration = self._scenario[s.scenario_index]
            s.phase = new_phase
            s.phase_start_time = now
            s.phase_duration = new_duration
            logger.debug("Phase transition: %s (%.0fs)", new_phase.value, new_duration)

    def _update_driving(self, dt: float) -> None:
        """Update RPM, speed, throttle, load based on current phase."""
        s = self._state
        phase_elapsed = time.monotonic() - s.phase_start_time

        if s.phase == DrivingPhase.COLD_START:
            # RPM settles from cold-start high idle to normal idle
            decay = math.exp(-phase_elapsed / RPM_SETTLE_TAU)
            s.target_rpm = IDLE_RPM + (COLD_START_RPM - IDLE_RPM) * decay
            s.target_speed_kph = 0
            s.throttle_pct = 0
            s.engine_load_pct = 20 + 5 * decay  # slightly higher load during warmup

        elif s.phase == DrivingPhase.IDLE:
            s.target_rpm = IDLE_RPM
            s.target_speed_kph = 0
            s.throttle_pct = 0
            s.engine_load_pct = 20

        elif s.phase == DrivingPhase.CITY:
            # Simulate stop-and-go with a sine wave pattern
            cycle = math.sin(phase_elapsed * 0.1) * 0.5 + 0.5  # 0-1 over ~63s cycle
            s.target_speed_kph = cycle * 50  # 0-50 kph
            s.throttle_pct = cycle * 35
            s.engine_load_pct = 20 + cycle * 40  # 20-60%

            # CVT maps speed to RPM
            cvt_ratio = CVT_RATIO_LOW - (CVT_RATIO_LOW - CVT_RATIO_HIGH) * (s.target_speed_kph / 120)
            if s.target_speed_kph > 2:
                s.target_rpm = s.target_speed_kph * cvt_ratio * 15  # rough mapping
                s.target_rpm = _clamp(s.target_rpm, IDLE_RPM, 4000)
            else:
                s.target_rpm = IDLE_RPM

        elif s.phase == DrivingPhase.HIGHWAY:
            s.target_speed_kph = 105  # ~65 mph
            s.throttle_pct = 18  # light throttle at cruise
            s.engine_load_pct = 30
            s.target_rpm = 2000  # CVT keeps RPM low at highway

        elif s.phase == DrivingPhase.ACCELERATION:
            s.target_speed_kph = min(s.speed_kph + 30, 120)
            s.throttle_pct = 70
            s.engine_load_pct = 80
            s.target_rpm = 4500

        elif s.phase == DrivingPhase.DECELERATION:
            s.target_speed_kph = max(s.speed_kph - 30, 0)
            s.throttle_pct = 0
            s.engine_load_pct = 10
            s.target_rpm = max(IDLE_RPM, s.rpm - 500)

        # Smooth transitions (exponential approach)
        alpha = min(1.0, dt * 2.0)  # ~0.5s time constant
        s.rpm += (s.target_rpm - s.rpm) * alpha
        s.speed_kph += (s.target_speed_kph - s.speed_kph) * alpha

        # MAF correlates with RPM and load
        # At idle: ~2.5 g/s. At 4000 RPM full load: ~50 g/s
        rpm_factor = s.rpm / 1000.0
        load_factor = s.engine_load_pct / 100.0
        s.maf_gps = IDLE_MAF_GPS + rpm_factor * load_factor * 12

        # Manifold pressure tracks load (vacuum at idle ~30, atm at WOT ~100)
        s.intake_manifold_kpa = 30 + (s.engine_load_pct / 100) * 70

    def _update_thermal(self, dt: float) -> None:
        """Update temperature sensors with realistic thermal dynamics."""
        s = self._state

        # Coolant: exponential approach to operating temp
        coolant_target = COOLANT_OPERATING_C
        # Slight increase under heavy load
        if s.engine_load_pct > 50:
            coolant_target += (s.engine_load_pct - 50) * 0.1

        alpha_coolant = 1 - math.exp(-dt / COOLANT_WARMUP_TAU)
        s.coolant_temp_c += (coolant_target - s.coolant_temp_c) * alpha_coolant

        # Oil temp: lags coolant
        oil_target = s.coolant_temp_c - 2  # oil runs slightly cooler
        alpha_oil = 1 - math.exp(-dt / (COOLANT_WARMUP_TAU + OIL_LAG_SECONDS))
        s.oil_temp_c += (oil_target - s.oil_temp_c) * alpha_oil

        # Catalyst: heats up faster, runs much hotter
        cat_target = CATALYST_OPERATING_C + s.engine_load_pct * 2
        alpha_cat = 1 - math.exp(-dt / CATALYST_WARMUP_TAU)
        s.catalyst_temp_c += (cat_target - s.catalyst_temp_c) * alpha_cat

        # CVT fluid: tracks between coolant and oil
        cvt_target = (s.coolant_temp_c + s.oil_temp_c) / 2 + 5
        alpha_cvt = 1 - math.exp(-dt / 200)
        s.cvt_fluid_temp_c += (cvt_target - s.cvt_fluid_temp_c) * alpha_cvt

        # Intake air temp: ambient + heat soak from engine bay
        intake_target = s.ambient_temp_c + (s.coolant_temp_c - s.ambient_temp_c) * 0.15
        s.intake_air_temp_c += (intake_target - s.intake_air_temp_c) * 0.1 * dt

    def _update_electrical(self, dt: float) -> None:
        """Update battery voltage based on load."""
        s = self._state
        # Alternator output: 14.0-14.5V normally
        # Dips under heavy electrical load, recovers quickly
        base_voltage = 14.2
        load_dip = s.engine_load_pct * 0.005  # slight dip under load
        target = base_voltage - load_dip
        s.battery_voltage += (target - s.battery_voltage) * min(1.0, dt * 5)

    def _update_fuel(self, dt: float) -> None:
        """Update fuel level based on consumption."""
        s = self._state
        fuel_rate_lph = maf_to_fuel_rate_lph(s.maf_gps)
        fuel_consumed_liters = fuel_rate_lph * (dt / 3600)
        tank_liters = 14.8 * 3.78541  # 14.8 gallons in liters
        pct_consumed = (fuel_consumed_liters / tank_liters) * 100
        s.fuel_level_pct = max(0, s.fuel_level_pct - pct_consumed)

    def _apply_anomalies(self) -> None:
        """Apply configured anomalies based on elapsed time."""
        s = self._state
        for anomaly in self._anomalies:
            if s.elapsed < anomaly.start_time:
                continue
            if anomaly.duration > 0 and s.elapsed > anomaly.start_time + anomaly.duration:
                continue

            progress = (s.elapsed - anomaly.start_time)
            if anomaly.duration > 0:
                progress = min(progress / anomaly.duration, 1.0)
            else:
                progress = min(progress / 60.0, 1.0)  # ramp over 60s for permanent

            severity = anomaly.severity * progress

            if anomaly.type == "coolant_spike":
                s.coolant_temp_c += severity * 25  # up to +25C

            elif anomaly.type == "fuel_trim_drift":
                s.ltft_pct += severity * 20  # LTFT drifts up to +20%
                s.stft_pct += severity * 5   # STFT compensates slightly

            elif anomaly.type == "voltage_drop":
                s.battery_voltage -= severity * 2.0  # drops up to 2V

            elif anomaly.type == "rpm_instability":
                # Add sinusoidal RPM wobble
                wobble = math.sin(s.elapsed * 3) * severity * 150
                s.rpm += wobble

            elif anomaly.type == "catalyst_degradation":
                s.catalyst_temp_c -= severity * 100  # efficiency drop

    def _add_noise(self) -> None:
        """Add small random noise to make data look realistic."""
        s = self._state
        s.rpm += random.gauss(0, 3)
        s.speed_kph += random.gauss(0, 0.2)
        s.coolant_temp_c += random.gauss(0, 0.3)
        s.oil_temp_c += random.gauss(0, 0.3)
        s.battery_voltage += random.gauss(0, 0.02)
        s.maf_gps += random.gauss(0, 0.1)
        s.stft_pct += random.gauss(0, 0.3)
        s.intake_manifold_kpa += random.gauss(0, 0.5)
        s.engine_load_pct += random.gauss(0, 0.5)


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))
