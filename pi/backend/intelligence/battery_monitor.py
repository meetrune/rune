"""Rune Battery Monitor -- track 12V battery health via Witty Pi 4 Vin readings.

Uses Witty Pi 4's Vin pin to read the car battery voltage. Classifies
state of charge using Interstate Battery's published SOC chart for
standard 12V SLI lead-acid batteries:

  >= 12.6V resting = FULL  (100% SOC)
  12.4-12.6V       = GOOD  (75% SOC)
  12.2-12.4V       = FAIR  (50% SOC)
  12.0-12.2V       = LOW   (25% SOC)
  < 12.0V          = CRITICAL
  > 13.5V engine on = CHARGING (alternator output)

Source: Interstate Batteries State of Charge chart
        (interstate-batteriescom/support/ask-the-expert/
         ask-the-expert-battery-charge-and-state)

Key design decisions:
- Only resting voltage (engine off 30+ min) is used for SOC classification.
  Under-load or surface-charge voltages are unreliable for SOC estimation.
  Source: Battery University BU-903 "How to Measure State of Charge"
- EWMA smoothing (alpha=0.1) on resting voltage filters transient noise
  from accessory loads while preserving real degradation trends.
- Drain rate threshold of 0.005V/hr for healthy lead-acid parasitic draw.
  Source: SAE J1211 "Recommended Environmental Practices for Electronic
  Equipment Design" -- typical automotive parasitic draw is 25-50mA,
  which on a ~60Ah battery produces <0.005V/hr voltage drop.
"""

from __future__ import annotations

import logging
import time

from backend.config import RuneSettings
from backend.intelligence.alert_queue import AlertQueue
from backend.intelligence.models import (
    AlertCategory,
    AlertSeverity,
    BatteryReading,
    BatteryState,
    BatteryTrend,
)

logger = logging.getLogger(__name__)

# Minimum time after engine off before voltage is considered "resting"
# Surface charge dissipation takes 15-30 min for lead-acid batteries.
# Source: Battery Council International (BCI) testing procedures.
# Using 30 min to be conservative.
_RESTING_DELAY_MIN = 30.0

# Normal parasitic drain rate for lead-acid automotive batteries.
# Source: SAE J1211 -- typical 25-50mA draw on 60Ah battery.
_NORMAL_DRAIN_V_PER_HOUR = 0.005


def _classify_resting(voltage: float) -> BatteryState:
    """Classify battery SOC from resting voltage.

    Interstate Battery State of Charge chart thresholds for 12V SLI
    lead-acid at ~25C (77F). Temperature compensation is NOT applied
    here -- Interstate's chart assumes room temp. Real-world deviation
    at extreme temps is ~0.01V/C, which is within our EWMA smoothing.
    """
    if voltage >= 12.6:
        return BatteryState.FULL
    if voltage >= 12.4:
        return BatteryState.GOOD
    if voltage >= 12.2:
        return BatteryState.FAIR
    if voltage >= 12.0:
        return BatteryState.LOW
    return BatteryState.CRITICAL


class BatteryMonitor:
    """Tracks 12V battery health from Witty Pi 4 Vin voltage readings.

    Accepts raw voltage + engine state, maintains EWMA-smoothed resting
    voltage, computes drain rate while parked, and queues alerts for
    low resting voltage or weak alternator charging.
    """

    def __init__(
        self,
        alert_queue: AlertQueue,
        settings: RuneSettings | None = None,
    ) -> None:
        cfg = settings or RuneSettings()
        self._alerts = alert_queue

        # Configurable thresholds
        self._warn_v = cfg.battery_resting_warn_v
        self._critical_v = cfg.battery_resting_critical_v
        self._charging_min_v = cfg.battery_charging_min_v
        self._ewma_alpha = cfg.battery_ewma_alpha

        # Trend state
        self._trend = BatteryTrend()

        # Track when engine last stopped for resting delay
        self._last_engine_off_at: float | None = None
        self._prev_engine_running: bool | None = None

        # For drain rate calculation: (timestamp, voltage) of last resting reading
        self._last_resting_reading: tuple[float, float] | None = None

        # Reading history for diagnostics (bounded)
        self._history: list[BatteryReading] = []
        self._max_history = 200

    @property
    def trend(self) -> BatteryTrend:
        """Current battery health trend."""
        return self._trend

    @property
    def history(self) -> list[BatteryReading]:
        """Recent voltage readings."""
        return self._history

    async def update(self, vin_voltage: float, engine_running: bool) -> BatteryReading:
        """Process a new voltage reading from Witty Pi 4.

        Args:
            vin_voltage: Raw Vin voltage from Witty Pi 4 (typically 10-15V).
            engine_running: Whether the engine is currently running.

        Returns:
            BatteryReading with classified state.
        """
        now = time.time()

        # Detect engine-off transition for resting timer
        if self._prev_engine_running is True and not engine_running:
            self._last_engine_off_at = now
            logger.debug("Engine stopped, starting resting voltage timer")
        self._prev_engine_running = engine_running

        # Determine minutes since engine off
        minutes_since_off: float | None = None
        if not engine_running and self._last_engine_off_at is not None:
            minutes_since_off = (now - self._last_engine_off_at) / 60.0

        # Classify state
        if engine_running and vin_voltage > self._charging_min_v:
            state = BatteryState.CHARGING
        elif engine_running:
            # Engine running but voltage below charging threshold -- weak alternator
            state = BatteryState.WEAK_CHARGING
            await self._alert_weak_charging(vin_voltage)
        elif minutes_since_off is not None and minutes_since_off >= _RESTING_DELAY_MIN:
            # True resting voltage -- surface charge has dissipated
            state = _classify_resting(vin_voltage)
            self._update_resting_ewma(vin_voltage, now)
        else:
            # Engine off but not long enough for reliable SOC reading
            state = BatteryState.UNKNOWN

        # Update charging EWMA when engine is running
        if engine_running:
            self._update_charging_ewma(vin_voltage)

        reading = BatteryReading(
            timestamp=now,
            voltage=vin_voltage,
            engine_running=engine_running,
            minutes_since_trip_end=minutes_since_off,
            state=state,
        )

        self._history.append(reading)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        self._trend.state = state
        self._trend.samples += 1

        return reading

    def _update_resting_ewma(self, voltage: float, now: float) -> None:
        """Update EWMA on resting voltage and compute drain rate.

        EWMA: V_new = alpha * V_raw + (1 - alpha) * V_old
        This filters transient noise from accessory loads (dome light,
        radio memory) while preserving real degradation trends.
        """
        alpha = self._ewma_alpha
        prev = self._trend.resting_voltage_ewma
        self._trend.resting_voltage_ewma = alpha * voltage + (1 - alpha) * prev

        # Drain rate: V/hour between consecutive resting readings
        if self._last_resting_reading is not None:
            prev_time, prev_voltage = self._last_resting_reading
            dt_hours = (now - prev_time) / 3600.0
            if dt_hours > 0.1:  # need at least ~6 min between samples
                drain = (prev_voltage - voltage) / dt_hours
                self._trend.drain_rate_v_per_hour = max(0.0, drain)

        self._last_resting_reading = (now, voltage)

        logger.debug(
            "Resting EWMA updated: %.3fV (raw %.3fV, drain %.5fV/hr)",
            self._trend.resting_voltage_ewma, voltage,
            self._trend.drain_rate_v_per_hour,
        )

    def _update_charging_ewma(self, voltage: float) -> None:
        """Track alternator output voltage with EWMA."""
        alpha = self._ewma_alpha
        prev = self._trend.charging_voltage_ewma
        self._trend.charging_voltage_ewma = alpha * voltage + (1 - alpha) * prev

    async def _alert_weak_charging(self, voltage: float) -> None:
        """Alert if charging voltage is below healthy alternator output.

        A healthy alternator produces 13.5-14.8V. Below 13.5V suggests
        a failing alternator, loose belt, or corroded connections.
        Source: Bosch automotive electrical systems handbook.
        """
        msg = (
            f"Charging voltage is low at {voltage:.1f}V. "
            f"Healthy alternator output is 13.5-14.8V. "
            f"Could be the alternator, belt, or a bad connection."
        )
        await self._alerts.enqueue(
            severity=AlertSeverity.WARNING,
            category=AlertCategory.BATTERY,
            message=msg,
            data={"charging_voltage": voltage, "min_expected": self._charging_min_v},
        )

    async def check_resting_alerts(self) -> None:
        """Flush any pending resting voltage alerts.

        Called periodically (e.g., after each parked wake cycle) rather
        than on every reading, to avoid alert spam during rapid sampling.
        """
        ewma = self._trend.resting_voltage_ewma
        drain = self._trend.drain_rate_v_per_hour

        if ewma < self._critical_v:
            msg = (
                f"Resting voltage is {ewma:.2f}V -- that's critical. "
                f"Below 12.0V means roughly 25% charge or less. "
                f"Worth getting the battery tested soon."
            )
            await self._alerts.enqueue(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.BATTERY,
                message=msg,
                data={
                    "resting_voltage_ewma": ewma,
                    "drain_rate_v_per_hour": drain,
                    "state": BatteryState.CRITICAL.value,
                },
            )
        elif ewma < self._warn_v:
            msg = (
                f"Resting voltage has been sitting at {ewma:.2f}V. "
                f"That's about 50% charge. Not urgent, but worth keeping an eye on."
            )
            await self._alerts.enqueue(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.BATTERY,
                message=msg,
                data={
                    "resting_voltage_ewma": ewma,
                    "drain_rate_v_per_hour": drain,
                    "state": BatteryState.FAIR.value,
                },
            )

        # Excessive drain rate alert
        if drain > _NORMAL_DRAIN_V_PER_HOUR * 3:
            msg = (
                f"Battery draining at {drain:.4f}V/hr while parked. "
                f"Normal is under {_NORMAL_DRAIN_V_PER_HOUR}V/hr. "
                f"Something might be drawing power when it shouldn't be."
            )
            await self._alerts.enqueue(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.BATTERY,
                message=msg,
                data={
                    "drain_rate_v_per_hour": drain,
                    "normal_max": _NORMAL_DRAIN_V_PER_HOUR,
                },
            )
