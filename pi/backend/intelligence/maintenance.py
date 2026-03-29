"""Rune Maintenance Tracker -- miles-based maintenance intelligence.

Tracks maintenance intervals for the 2026 Honda Accord SE (1.5T CVT)
and alerts when service is approaching. Intervals come from the Honda
owner's manual maintenance schedule with condition-based adjustments
using real sensor data.

Interval sources (2026 Honda Accord SE Owner's Manual, Honda Part No.
00X31-22A-0000):
  - Oil change: 7,500 mi normal, or when Maintenance Minder indicates.
    Honda Maintenance Minder uses oil life algorithm based on RPM, speed,
    and temperature. We approximate with a fixed interval + temperature
    adjustment.
  - Air filter: 15,000 mi (inspect at 15k, replace as needed -- we track
    the inspection/replacement cycle).
  - Cabin air filter: 15,000 mi.
  - CVT fluid: 30,000 mi for normal driving. Honda recommends 25,000 mi
    for "severe" conditions (frequent towing, mountainous terrain, or
    sustained high-temp operation).
  - Spark plugs: 60,000 mi (iridium long-life).
  - Coolant: 60,000 mi first change (Honda Type 2 blue coolant is
    long-life), then 30,000 mi subsequent.
  - Brake fluid: 36,000 mi (Honda recommends 3-year interval; we convert
    to miles using ~12k mi/year average).
  - Tire rotation: 7,500 mi (aligned with oil change interval for
    convenience).

Condition-based adjustments:
  - Oil change shortened to 5,000 mi if average oil temperature
    consistently exceeds 110C. Source: SAE J300 viscosity standards note
    accelerated thermal breakdown of 0W-20 oils above 110C sustained.
    Honda 0W-20 (SN/SP grade) starts losing shear stability at these
    temps.
  - CVT fluid shortened to 25,000 mi if average CVT fluid temperature
    exceeds 90C. Source: Honda service technical bulletin on CVT fluid
    degradation; JATCO CVT7 service manual notes accelerated oxidation
    above 90C sustained.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.config import settings
from backend.database.db import RuneDatabase
from backend.intelligence.alert_queue import AlertQueue
from backend.intelligence.models import (
    AlertCategory,
    AlertSeverity,
    MaintenanceItem,
    MaintenanceRecord,
    MaintenanceStatus,
)

logger = logging.getLogger(__name__)

# Oil thermal breakdown threshold (SAE J300, Honda 0W-20 spec)
_OIL_TEMP_HOT_C: float = 110.0

# CVT fluid oxidation threshold (Honda TSB, JATCO CVT7 service manual)
_CVT_TEMP_HOT_C: float = 90.0


class MaintenanceTracker:
    """Miles-based maintenance tracking with condition-based adjustments.

    Reads maintenance history from the DB, compares against Honda-specified
    intervals (adjusted by sensor data), and queues alerts when service is
    approaching. All intervals are configurable via RuneSettings.
    """

    def __init__(self) -> None:
        # Track coolant change count to handle first vs subsequent intervals
        # This is loaded from DB on first check
        self._coolant_change_count: int | None = None

    async def check_maintenance(
        self,
        current_odometer_miles: float,
        db: RuneDatabase,
        alert_queue: AlertQueue,
        avg_oil_temp_c: float | None = None,
        avg_cvt_temp_c: float | None = None,
    ) -> list[MaintenanceStatus]:
        """Check all maintenance items against current odometer.

        Fetches the latest maintenance record for each item from the DB,
        calculates the next due mileage (with condition-based adjustments),
        and queues alerts for items due within 500 miles.

        Args:
            current_odometer_miles: Current vehicle odometer reading.
            db: Database handle for maintenance history queries.
            alert_queue: Alert queue for upcoming-maintenance alerts.
            avg_oil_temp_c: Rolling average oil temperature. If above 110C,
                oil change interval is shortened (SAE J300 thermal limits).
            avg_cvt_temp_c: Rolling average CVT fluid temperature. If above
                90C, CVT fluid interval is shortened (Honda TSB).

        Returns:
            List of MaintenanceStatus for all tracked items.
        """
        statuses: list[MaintenanceStatus] = []

        # Load coolant change count if not yet cached
        if self._coolant_change_count is None:
            await self._load_coolant_count(db)

        for item in MaintenanceItem:
            interval, adjusted, reason = self._get_interval(
                item, avg_oil_temp_c, avg_cvt_temp_c
            )

            # Fetch last maintenance record from DB
            record = await db.get_latest_maintenance(item.value)

            if record is not None:
                last_done_miles = record["odometer_miles"]
                last_done_at = record["done_at"]
                next_due_miles = last_done_miles + interval
            else:
                # No history: assume due at current odometer + interval
                # (first-time setup: the owner should mark_done for all
                # items at the odometer reading when Rune is installed)
                last_done_miles = None
                last_done_at = None
                next_due_miles = current_odometer_miles + interval

            miles_remaining = next_due_miles - current_odometer_miles

            status = MaintenanceStatus(
                item=item,
                last_done_miles=last_done_miles,
                last_done_at=last_done_at,
                next_due_miles=next_due_miles,
                miles_remaining=miles_remaining,
                interval_miles=interval,
                adjusted=adjusted,
                adjustment_reason=reason,
            )
            statuses.append(status)

            # Alert if due within the configured lookahead (default 500 mi)
            if miles_remaining <= settings.maint_alert_ahead_mi:
                await self._queue_maintenance_alert(
                    item, miles_remaining, interval, adjusted, reason, alert_queue
                )

        logger.info(
            "Maintenance check complete: odometer=%.0f items=%d approaching=%d",
            current_odometer_miles,
            len(statuses),
            sum(1 for s in statuses if s.miles_remaining <= settings.maint_alert_ahead_mi),
        )

        return statuses

    async def mark_done(
        self,
        item: MaintenanceItem,
        odometer_miles: float,
        db: RuneDatabase,
        notes: str = "",
    ) -> MaintenanceRecord:
        """Record a completed maintenance event.

        Inserts a new row in maintenance_log and returns the record.
        For coolant changes, increments the internal counter so subsequent
        intervals are correctly shortened (60k first, 30k after).

        Args:
            item: Which maintenance item was completed.
            odometer_miles: Odometer reading at time of service.
            db: Database handle.
            notes: Optional free-text notes (shop name, parts used, etc.)

        Returns:
            The recorded MaintenanceRecord.
        """
        # Calculate next due mileage using current interval
        interval, _, _ = self._get_interval(item, None, None)
        next_due_miles = odometer_miles + interval

        record_id = await db.insert_maintenance(
            item=item.value,
            odometer_miles=odometer_miles,
            next_due_miles=next_due_miles,
            notes=notes,
        )

        # Track coolant changes for first/subsequent interval logic
        if item == MaintenanceItem.COOLANT:
            if self._coolant_change_count is not None:
                self._coolant_change_count += 1
            else:
                self._coolant_change_count = 1

        record = MaintenanceRecord(
            id=record_id,
            item=item,
            done_at=time.time(),
            odometer_miles=odometer_miles,
            next_due_miles=next_due_miles,
            notes=notes,
        )

        logger.info(
            "Maintenance recorded: item=%s odometer=%.0f next_due=%.0f notes=%s",
            item.value,
            odometer_miles,
            next_due_miles,
            notes or "(none)",
        )

        return record

    def get_intervals(self) -> dict[str, float]:
        """Return all maintenance intervals (miles) using current settings.

        Does not account for condition-based adjustments since those depend
        on sensor averages. Returns the standard intervals.
        """
        return {
            MaintenanceItem.OIL_CHANGE.value: settings.maint_oil_change_mi,
            MaintenanceItem.AIR_FILTER.value: settings.maint_air_filter_mi,
            MaintenanceItem.CABIN_FILTER.value: settings.maint_cabin_filter_mi,
            MaintenanceItem.CVT_FLUID.value: settings.maint_cvt_fluid_mi,
            MaintenanceItem.SPARK_PLUGS.value: settings.maint_spark_plugs_mi,
            MaintenanceItem.COOLANT.value: self._get_coolant_interval(),
            MaintenanceItem.BRAKE_FLUID.value: settings.maint_brake_fluid_mi,
            MaintenanceItem.TIRE_ROTATION.value: settings.maint_tire_rotation_mi,
        }

    def _get_interval(
        self,
        item: MaintenanceItem,
        avg_oil_temp_c: float | None,
        avg_cvt_temp_c: float | None,
    ) -> tuple[float, bool, str]:
        """Get the effective interval for a maintenance item.

        Returns (interval_miles, adjusted, reason).
        Condition-based adjustments reduce intervals when sensor data
        indicates accelerated wear.
        """
        if item == MaintenanceItem.OIL_CHANGE:
            # SAE J300: 0W-20 oils experience accelerated thermal breakdown
            # above 110C sustained. Honda 0W-20 (API SP) loses shear
            # stability at these temperatures, reducing film strength.
            if avg_oil_temp_c is not None and avg_oil_temp_c > _OIL_TEMP_HOT_C:
                return (
                    settings.maint_oil_change_hot_mi,
                    True,
                    f"Oil temp avg {avg_oil_temp_c:.0f}C > {_OIL_TEMP_HOT_C:.0f}C threshold",
                )
            return (settings.maint_oil_change_mi, False, "")

        if item == MaintenanceItem.AIR_FILTER:
            return (settings.maint_air_filter_mi, False, "")

        if item == MaintenanceItem.CABIN_FILTER:
            return (settings.maint_cabin_filter_mi, False, "")

        if item == MaintenanceItem.CVT_FLUID:
            # Honda TSB + JATCO CVT7 service manual: CVT fluid (HMMF)
            # oxidation rate increases significantly above 90C sustained.
            # Oxidized fluid loses friction coefficient control, causing
            # belt slip and pressure fluctuations.
            if avg_cvt_temp_c is not None and avg_cvt_temp_c > _CVT_TEMP_HOT_C:
                return (
                    settings.maint_cvt_fluid_hot_mi,
                    True,
                    f"CVT temp avg {avg_cvt_temp_c:.0f}C > {_CVT_TEMP_HOT_C:.0f}C threshold",
                )
            return (settings.maint_cvt_fluid_mi, False, "")

        if item == MaintenanceItem.SPARK_PLUGS:
            return (settings.maint_spark_plugs_mi, False, "")

        if item == MaintenanceItem.COOLANT:
            return (self._get_coolant_interval(), False, "")

        if item == MaintenanceItem.BRAKE_FLUID:
            return (settings.maint_brake_fluid_mi, False, "")

        if item == MaintenanceItem.TIRE_ROTATION:
            return (settings.maint_tire_rotation_mi, False, "")

        # Unreachable for exhaustive MaintenanceItem enum, but satisfy mypy
        return (settings.maint_oil_change_mi, False, "")

    def _get_coolant_interval(self) -> float:
        """Get coolant change interval (first change is longer).

        Honda Type 2 blue coolant (long-life ethylene glycol) lasts
        60,000 miles on first fill. Subsequent changes at 30,000 miles
        because the system is no longer factory-sealed and picks up
        contaminants faster.
        """
        if self._coolant_change_count is not None and self._coolant_change_count > 0:
            return settings.maint_coolant_subsequent_mi
        return settings.maint_coolant_first_mi

    async def _load_coolant_count(self, db: RuneDatabase) -> None:
        """Load coolant change count from DB to determine interval."""
        records = await db.get_all_maintenance()
        coolant_count = sum(
            1 for r in records if r["item"] == MaintenanceItem.COOLANT.value
        )
        self._coolant_change_count = coolant_count
        logger.debug("Loaded coolant change count from DB: %d", coolant_count)

    async def _queue_maintenance_alert(
        self,
        item: MaintenanceItem,
        miles_remaining: float,
        interval: float,
        adjusted: bool,
        reason: str,
        alert_queue: AlertQueue,
    ) -> None:
        """Queue an alert for approaching maintenance.

        Uses Rune's voice: first person, direct, not dramatic.
        """
        # Human-readable item names for Rune's voice
        item_names: dict[str, str] = {
            MaintenanceItem.OIL_CHANGE.value: "oil change",
            MaintenanceItem.AIR_FILTER.value: "air filter",
            MaintenanceItem.CABIN_FILTER.value: "cabin air filter",
            MaintenanceItem.CVT_FLUID.value: "CVT fluid change",
            MaintenanceItem.SPARK_PLUGS.value: "spark plugs",
            MaintenanceItem.COOLANT.value: "coolant change",
            MaintenanceItem.BRAKE_FLUID.value: "brake fluid change",
            MaintenanceItem.TIRE_ROTATION.value: "tire rotation",
        }

        name = item_names.get(item.value, item.value)

        if miles_remaining <= 0:
            message = f"I'm past due for a {name}. Worth scheduling soon."
        else:
            message = (
                f"I'll need a {name} in about {miles_remaining:.0f} miles. "
                "Worth keeping in mind."
            )

        if adjusted:
            message += f" Interval shortened -- {reason}."

        severity = (
            AlertSeverity.WARNING if miles_remaining <= 0
            else AlertSeverity.INFO
        )

        await alert_queue.enqueue(
            severity=severity,
            category=AlertCategory.MAINTENANCE,
            message=message,
            data={
                "item": item.value,
                "miles_remaining": miles_remaining,
                "interval_miles": interval,
                "adjusted": adjusted,
                "adjustment_reason": reason,
            },
        )
