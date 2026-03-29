"""Rune Thermal Guardian -- parked thermal protection via Witty Pi wake cycles.

When parked, the Witty Pi 4 RTC wakes the Pi periodically to check
armrest temperature (BME280 sensor), CPU temperature, and battery voltage.
If conditions are dangerous, alerts are queued and the wake interval is
adjusted to conserve battery while maintaining safety monitoring.

Temperature thresholds are derived from two sources:

1. Interior temperature research:
   - NHTSA study "Heatstroke Deaths of Children in Vehicles" (DOT HS 811 632,
     2012): car interiors reach 60C (140F) within 1 hour in direct sun at 35C
     ambient. Enclosed armrest compartment runs hotter than cabin average.
   - Stanford University study (McLaren, Null, Quinn, 2005, Pediatrics
     115(4):e413-e419): interior temperatures rise ~3.4F/5min in first 30min,
     reaching 40F above ambient within 60min. Dashboard surfaces exceed 70C.
   - For an armrest enclosure (partially insulated, lower airflow), we use
     45C as "warm" onset, 60C as "hot" (electronics at risk), and 70C as
     "extreme" (sustained exposure degrades batteries and solder joints).

2. BCM2711 (Pi 4B SoC) thermal limits:
   - Broadcom BCM2711 datasheet: thermal throttling begins at 80C,
     emergency shutdown at 85C.
   - Raspberry Pi Foundation documentation (raspberrypi.com/documentation):
     "The firmware will progressively throttle back the ARM cores and GPU
     once the SoC reaches 80C."
   - We use CPU temp as secondary check: if CPU is already at 75C+ just
     from wake-up, the enclosure is critically hot.

Wake cycle strategy:
  - NORMAL (<45C): wake every 2 hours -- standard battery drain monitoring
  - WARM (45-60C): wake every 2 hours with explicit logging
  - HOT (60-70C): queue WARNING alert, recommend staying off (electronics risk)
  - EXTREME (>70C): queue CRITICAL alert, extend to 4-hour wake cycle to
    minimize Pi runtime in dangerous heat
"""

from __future__ import annotations

import logging
import time

from backend.config import settings
from backend.intelligence.alert_queue import AlertQueue
from backend.intelligence.models import (
    AlertCategory,
    AlertSeverity,
    ParkedCheckResult,
    ParkedThermalState,
)

logger = logging.getLogger(__name__)

# BCM2711 thermal limits (Broadcom datasheet + Raspberry Pi Foundation docs)
_CPU_THROTTLE_C: float = 80.0
_CPU_SHUTDOWN_C: float = 85.0
_CPU_WARM_THRESHOLD_C: float = 75.0  # if CPU hits this on wake, enclosure is very hot


class ThermalGuardian:
    """Parked thermal protection for the Pi inside the armrest enclosure.

    Called by the Witty Pi wake script. Evaluates armrest temp (BME280),
    CPU temp (vcgencmd / /sys/class/thermal), and battery voltage.
    Queues alerts and adjusts wake interval accordingly.
    """

    def __init__(self) -> None:
        self._state: ParkedThermalState = ParkedThermalState.NORMAL
        self._last_check_ts: float | None = None
        self._check_count: int = 0
        self._should_shutdown: bool = False

    async def check_parked_state(
        self,
        armrest_temp_c: float | None,
        cpu_temp_c: float | None,
        vin_voltage: float | None,
        alert_queue: AlertQueue,
    ) -> ParkedCheckResult:
        """Evaluate parked thermal and battery conditions.

        Called once per Witty Pi wake cycle. Determines thermal state from
        armrest temperature (primary) or CPU temperature (fallback), queues
        alerts if thresholds are exceeded, and returns the recommended
        next wake interval.

        Args:
            armrest_temp_c: BME280 reading from inside the armrest. None if
                sensor unavailable.
            cpu_temp_c: SoC temperature from /sys/class/thermal/thermal_zone0.
                None if read failed.
            vin_voltage: 12V battery voltage from OBD PID 0142 or Witty Pi
                ADC. None if unavailable.
            alert_queue: Alert queue for queuing thermal/battery warnings.

        Returns:
            ParkedCheckResult with thermal state and next wake interval.
        """
        now = time.time()
        self._last_check_ts = now
        self._check_count += 1

        # Determine thermal state from armrest temp (primary signal)
        thermal_state = self._classify_temp(armrest_temp_c, cpu_temp_c)
        self._state = thermal_state

        alerts_queued = 0

        # Effective temp for alert messages (could be proxy from CPU)
        effective_temp = armrest_temp_c
        if effective_temp is None and cpu_temp_c is not None:
            effective_temp = cpu_temp_c - 15.0
        temp_str = f"{effective_temp:.0f}" if effective_temp is not None else "unknown"

        # Queue alerts for dangerous states
        if thermal_state == ParkedThermalState.HOT:
            alert_id = await alert_queue.enqueue(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.THERMAL,
                message=(
                    f"Armrest enclosure is hot ({temp_str}C). "
                    "Electronics at risk. I'm staying off to protect myself."
                ),
                data={
                    "armrest_temp_c": armrest_temp_c,
                    "cpu_temp_c": cpu_temp_c,
                    "effective_temp_c": effective_temp,
                    "state": thermal_state.value,
                },
            )
            if alert_id is not None:
                alerts_queued += 1

        elif thermal_state == ParkedThermalState.EXTREME:
            # NHTSA/Stanford studies: interior surfaces exceed 70C in direct
            # sun. At this point, sustained heat degrades Li-ion cells,
            # SD card solder joints, and electrolytic capacitors.
            alert_id = await alert_queue.enqueue(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.THERMAL,
                message=(
                    f"Armrest enclosure is dangerously hot ({temp_str}C). "
                    "Extending wake interval to reduce heat generation."
                ),
                data={
                    "armrest_temp_c": armrest_temp_c,
                    "cpu_temp_c": cpu_temp_c,
                    "effective_temp_c": effective_temp,
                    "state": thermal_state.value,
                },
            )
            if alert_id is not None:
                alerts_queued += 1

        # Emergency shutdown: if CPU is at or above shutdown threshold,
        # or effective armrest temp exceeds 80C, shut down immediately.
        # The Pi running adds 3-5W of heat -- staying on makes it worse.
        should_emergency_shutdown = False
        if cpu_temp_c is not None and cpu_temp_c >= _CPU_SHUTDOWN_C:
            logger.critical(
                "PARKED EMERGENCY SHUTDOWN: CPU=%.1fC >= %.1fC shutdown threshold",
                cpu_temp_c, _CPU_SHUTDOWN_C,
            )
            should_emergency_shutdown = True
        if effective_temp is not None and effective_temp >= 80.0:
            logger.critical(
                "PARKED EMERGENCY SHUTDOWN: enclosure=%.1fC >= 80C",
                effective_temp,
            )
            should_emergency_shutdown = True

        if should_emergency_shutdown:
            await alert_queue.enqueue(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.THERMAL,
                message=(
                    f"Emergency shutdown -- enclosure at {temp_str}C. "
                    "Too hot to stay on. I'll check again in 4 hours."
                ),
                data={
                    "armrest_temp_c": armrest_temp_c,
                    "cpu_temp_c": cpu_temp_c,
                    "effective_temp_c": effective_temp,
                    "action": "emergency_shutdown",
                },
            )
            self._should_shutdown = True

        # CPU-specific alert: if CPU is near throttle point on wake-up,
        # the enclosure has inadequate cooling
        if cpu_temp_c is not None and cpu_temp_c >= _CPU_WARM_THRESHOLD_C:
            alert_id = await alert_queue.enqueue(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.SYSTEM,
                message=(
                    f"CPU temperature is {cpu_temp_c:.0f}C on wake-up. "
                    f"Throttling starts at {_CPU_THROTTLE_C:.0f}C. "
                    "Enclosure ventilation may be blocked."
                ),
                data={
                    "cpu_temp_c": cpu_temp_c,
                    "throttle_at": _CPU_THROTTLE_C,
                    "shutdown_at": _CPU_SHUTDOWN_C,
                },
            )
            if alert_id is not None:
                alerts_queued += 1

        # Battery check: delegate voltage evaluation if available
        if vin_voltage is not None:
            alerts_queued += await self._check_battery_voltage(
                vin_voltage, alert_queue
            )

        next_wake = self.get_recommended_wake_hours()

        logger.info(
            "Parked thermal check: state=%s armrest=%.1fC cpu=%.1fC voltage=%s "
            "next_wake=%.1fh alerts_queued=%d",
            thermal_state.value,
            armrest_temp_c if armrest_temp_c is not None else -999,
            cpu_temp_c if cpu_temp_c is not None else -999,
            f"{vin_voltage:.2f}V" if vin_voltage is not None else "N/A",
            next_wake,
            alerts_queued,
        )

        return ParkedCheckResult(
            timestamp=now,
            armrest_temp_c=armrest_temp_c,
            cpu_temp_c=cpu_temp_c,
            vin_voltage=vin_voltage,
            thermal_state=thermal_state,
            next_wake_hours=next_wake,
            alerts_queued=alerts_queued,
        )

    def get_recommended_wake_hours(self) -> float:
        """Return the recommended Witty Pi wake interval in hours.

        NORMAL/WARM/HOT: 2-hour cycle (standard monitoring).
        EXTREME: 4-hour cycle to minimize Pi runtime in dangerous heat.
        Running the Pi adds ~3-5W of heat to the enclosure, so reducing
        wake frequency in extreme heat is both battery- and thermal-friendly.
        """
        if self._state == ParkedThermalState.EXTREME:
            return settings.thermal_extreme_wake_hours
        return settings.thermal_normal_wake_hours

    def get_state(self) -> ParkedThermalState:
        """Return the current parked thermal state."""
        return self._state

    @property
    def should_shutdown(self) -> bool:
        """True if emergency shutdown was triggered by extreme heat."""
        return self._should_shutdown

    def _classify_temp(
        self,
        armrest_temp_c: float | None,
        cpu_temp_c: float | None,
    ) -> ParkedThermalState:
        """Classify thermal state from sensor readings.

        Priority: armrest BME280 > CPU temp (as proxy).
        If both are None, assume NORMAL (no data = no alarm).
        """
        # Use armrest temp as primary signal
        temp = armrest_temp_c

        # Fallback: if armrest sensor is missing, use CPU temp as proxy.
        # CPU idles ~15-20C above ambient in the enclosure, so a CPU
        # reading of 75C implies enclosure around 55-60C.
        if temp is None and cpu_temp_c is not None:
            # Conservative estimate: assume enclosure is CPU - 15C
            # This is a rough proxy -- BME280 is the authoritative source.
            temp = cpu_temp_c - 15.0
            logger.debug(
                "No armrest temp available. Using CPU proxy: cpu=%.1fC -> estimated=%.1fC",
                cpu_temp_c,
                temp,
            )

        if temp is None:
            return ParkedThermalState.NORMAL

        if temp >= settings.thermal_extreme_c:
            return ParkedThermalState.EXTREME
        if temp >= settings.thermal_hot_c:
            return ParkedThermalState.HOT
        if temp >= settings.thermal_warm_c:
            return ParkedThermalState.WARM
        return ParkedThermalState.NORMAL

    async def _check_battery_voltage(
        self,
        voltage: float,
        alert_queue: AlertQueue,
    ) -> int:
        """Evaluate parked battery voltage and queue alerts if needed.

        While parked (engine off), the battery should hold above 12.2V
        (50% SOC per Interstate Battery State of Charge chart).
        Below 12.0V (25% SOC) is critical -- the car may not start.

        Uses settings thresholds which align with the BatteryMonitor
        feature for consistency.

        Returns:
            Number of alerts successfully queued (0 or 1).
        """
        if voltage < settings.battery_resting_critical_v:
            alert_id = await alert_queue.enqueue(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.BATTERY,
                message=(
                    f"Battery is at {voltage:.1f}V while parked. "
                    "Below 12.0V -- I might not start. Worth checking."
                ),
                data={"voltage": voltage, "threshold": settings.battery_resting_critical_v},
            )
            return 1 if alert_id is not None else 0

        if voltage < settings.battery_resting_warn_v:
            alert_id = await alert_queue.enqueue(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.BATTERY,
                message=(
                    f"Battery is at {voltage:.1f}V while parked. "
                    "That's about 50% charge. Keep an eye on it."
                ),
                data={"voltage": voltage, "threshold": settings.battery_resting_warn_v},
            )
            return 1 if alert_id is not None else 0

        return 0
