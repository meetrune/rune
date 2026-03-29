"""Rune Cold-Start Warmup Profiler -- track and predict engine warmup times.

Models engine warmup as Newton's law of heating: the coolant temperature
approaches thermostat equilibrium exponentially. The rate depends on
ambient temperature -- colder starts take longer.

Physics basis:
  T(t) = T_eq - (T_eq - T_0) * exp(-k * t)
  where T_eq = thermostat temp (~80C for Honda), T_0 = initial coolant,
  k = heating rate constant (engine-specific).

Source: Incropera & DeWitt, "Fundamentals of Heat and Mass Transfer",
        Chapter 5 -- Transient Conduction (lumped capacitance model).
        The engine block + coolant system acts as a lumped thermal mass
        approaching steady-state thermostat temperature.

Prediction model:
  warmup_min = a * exp(-b * ambient_C) + c
  Fitted via scipy.optimize.curve_fit after accumulating 15+ cold starts.
  This captures the nonlinear relationship: warmup time increases
  exponentially as ambient temperature drops below freezing.

Honda 2026 Accord SE specifics:
  - Thermostat opens at ~80-82C (Honda service manual).
  - Using 80C as warmup target (conservative, ensures thermostat is open).
  - 1.5L L15BE turbo reaches operating temp faster than NA engines
    due to turbo heat contribution, but cold-start enrichment still
    runs until coolant hits ~70-80C.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

from backend.config import RuneSettings
from backend.intelligence.alert_queue import AlertQueue
from backend.intelligence.models import (
    AlertCategory,
    AlertSeverity,
    ColdStartRecord,
    WarmupModel,
)

if TYPE_CHECKING:
    from backend.database.db import RuneDatabase

logger = logging.getLogger(__name__)


class ColdStartProfiler:
    """Tracks engine warmup from cold start to thermostat opening.

    Records each cold-start warmup event (ambient temp -> warmup duration),
    fits an exponential prediction model after enough samples, and flags
    anomalies when warmup takes significantly longer than predicted.
    """

    def __init__(
        self,
        alert_queue: AlertQueue,
        settings: RuneSettings | None = None,
    ) -> None:
        cfg = settings or RuneSettings()
        self._alerts = alert_queue

        # Config
        self._target_c = cfg.coldstart_target_coolant_c
        self._min_samples = cfg.coldstart_min_samples
        self._anomaly_threshold = cfg.coldstart_anomaly_threshold

        # Current warmup tracking state
        self._tracking = False
        self._start_time: float | None = None
        self._start_coolant_c: float | None = None
        self._ambient_c: float | None = None
        self._warmup_reached_at: float | None = None

        # Fitted model (persisted across trips in memory, rebuilt from DB on restart)
        self._model: WarmupModel | None = None

        # In-memory record buffer for model fitting
        self._records: list[ColdStartRecord] = []

    @property
    def model(self) -> WarmupModel | None:
        """Current fitted warmup model, or None if not enough data."""
        return self._model

    @property
    def is_tracking(self) -> bool:
        """Whether we're currently tracking a warmup."""
        return self._tracking

    def on_trip_start(self, coolant_c: float, ambient_c: float) -> None:
        """Begin tracking warmup if coolant is below target.

        Only tracks genuine cold starts -- if coolant is already near
        operating temp (e.g., short stop and restart), skip tracking.
        """
        if coolant_c >= self._target_c:
            logger.debug(
                "Coolant already at %.1fC (target %.1fC), skipping warmup tracking",
                coolant_c, self._target_c,
            )
            self._tracking = False
            return

        self._tracking = True
        self._start_time = time.time()
        self._start_coolant_c = coolant_c
        self._ambient_c = ambient_c
        self._warmup_reached_at = None

        logger.info(
            "Cold start tracking: coolant=%.1fC ambient=%.1fC target=%.1fC",
            coolant_c, ambient_c, self._target_c,
        )

    def on_reading(self, coolant_c: float) -> bool:
        """Process a coolant temperature reading during warmup.

        Args:
            coolant_c: Current coolant temperature in Celsius.

        Returns:
            True if warmup target was just reached on this reading.
            False if still warming up or not tracking.
        """
        if not self._tracking or self._warmup_reached_at is not None:
            return False

        if coolant_c >= self._target_c:
            self._warmup_reached_at = time.time()
            warmup_s = self._warmup_reached_at - (self._start_time or 0)
            logger.info(
                "Warmup complete: %.1fC reached in %.0f seconds (ambient %.1fC)",
                coolant_c, warmup_s, self._ambient_c,
            )
            return True

        return False

    async def on_trip_end(
        self,
        trip_id: int | None,
        db: RuneDatabase,
    ) -> ColdStartRecord | None:
        """Finalize warmup tracking and persist the record.

        Called at trip end. If warmup was tracked and target was reached,
        saves the record to the database and checks for anomalies.

        Returns:
            ColdStartRecord if warmup was tracked, None otherwise.
        """
        if not self._tracking:
            return None

        self._tracking = False

        if self._warmup_reached_at is None:
            # Trip ended before reaching target -- too short to be useful
            logger.debug("Trip ended before warmup target reached, discarding")
            return None

        warmup_seconds = self._warmup_reached_at - (self._start_time or 0)
        if warmup_seconds <= 0:
            logger.warning(
                "Warmup seconds <= 0 (%.2f), discarding cold-start record. "
                "Possible clock issue: reached_at=%.3f start_time=%s",
                warmup_seconds, self._warmup_reached_at, self._start_time,
            )
            return None

        record = ColdStartRecord(
            trip_id=trip_id,
            ambient_temp_c=self._ambient_c or 0.0,
            start_coolant_c=self._start_coolant_c or 0.0,
            target_coolant_c=self._target_c,
            warmup_seconds=warmup_seconds,
        )

        # Persist to database
        try:
            await db.insert_cold_start(
                trip_id=trip_id,
                ambient_temp_c=self._ambient_c,
                start_coolant_c=self._start_coolant_c,
                target_coolant_c=self._target_c,
                warmup_seconds=warmup_seconds,
            )
        except Exception:
            logger.exception("Failed to persist cold-start record")

        # Buffer for model fitting
        self._records.append(record)

        # Check for anomaly against current model
        if self._model is not None and self._ambient_c is not None:
            is_anomaly = self.check_anomaly(warmup_seconds, self._ambient_c)
            if is_anomaly:
                await self._alert_slow_warmup(record)

        return record

    def fit_model(self) -> WarmupModel | None:
        """Fit exponential warmup model from accumulated cold-start records.

        Model: warmup_min = a * exp(-b * ambient_C) + c

        This captures the physics: warmup time increases exponentially
        as ambient temperature decreases. The exp(-b * T) term means
        each degree below zero adds proportionally more warmup time,
        matching real-world behavior where -20C starts take much longer
        than 0C starts.

        Requires scipy.optimize.curve_fit (Levenberg-Marquardt).
        Returns None if fewer than min_samples records are available.
        """
        if len(self._records) < self._min_samples:
            logger.debug(
                "Not enough cold-start samples for model fit: %d/%d",
                len(self._records), self._min_samples,
            )
            return None

        try:
            from scipy.optimize import curve_fit
        except ImportError:
            logger.warning("scipy not available, cannot fit warmup model")
            return None

        ambients = np.array([r.ambient_temp_c for r in self._records])
        warmups_min = np.array([r.warmup_seconds / 60.0 for r in self._records])

        # Model function: warmup_min = a * exp(-b * ambient_C) + c
        def _model_fn(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
            return a * np.exp(-b * x) + c

        # Initial guesses based on typical automotive warmup behavior:
        # ~8 min at 0C, ~4 min at 20C, baseline ~2 min
        p0 = [6.0, 0.05, 2.0]

        try:
            popt, _ = curve_fit(
                _model_fn, ambients, warmups_min,
                p0=p0,
                maxfev=5000,
                bounds=([0, 0, 0], [30, 1, 15]),  # physical constraints
            )
        except (RuntimeError, ValueError):
            logger.warning("curve_fit failed for warmup model")
            return None

        # Compute R-squared for fit quality assessment
        predicted = _model_fn(ambients, *popt)
        ss_res = np.sum((warmups_min - predicted) ** 2)
        ss_tot = np.sum((warmups_min - np.mean(warmups_min)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        self._model = WarmupModel(
            a=float(popt[0]),
            b=float(popt[1]),
            c=float(popt[2]),
            n_samples=len(self._records),
            r_squared=r_squared,
            last_fit_at=time.time(),
        )

        logger.info(
            "Warmup model fitted: a=%.3f b=%.4f c=%.3f R2=%.3f (n=%d)",
            self._model.a, self._model.b, self._model.c,
            r_squared, len(self._records),
        )

        return self._model

    def predict_warmup_minutes(self, ambient_c: float) -> float | None:
        """Predict warmup time in minutes for a given ambient temperature.

        Returns None if no model is fitted yet.
        """
        if self._model is None:
            return None
        return (
            self._model.a * np.exp(-self._model.b * ambient_c) + self._model.c
        )

    def check_anomaly(self, warmup_seconds: float, ambient_c: float) -> bool:
        """Check if a warmup duration is anomalously long.

        Returns True if actual warmup exceeds predicted by more than
        the anomaly threshold (default 1.3x = 30% deviation).

        A 30% threshold balances sensitivity vs false positives:
        - Too tight (10-20%): normal variance from traffic, route,
          and wind chill triggers false alerts.
        - Too loose (50%+): misses genuine thermostat or coolant issues.
        - 30% is a common anomaly detection threshold in predictive
          maintenance literature (ISO 13374-2).
        """
        if self._model is None:
            return False

        predicted_min = (
            self._model.a * np.exp(-self._model.b * ambient_c) + self._model.c
        )
        if predicted_min <= 0:
            return False

        actual_min = warmup_seconds / 60.0
        ratio = actual_min / predicted_min

        if ratio > self._anomaly_threshold:
            logger.warning(
                "Warmup anomaly: actual=%.1f min, predicted=%.1f min, "
                "ratio=%.2f (threshold=%.2f), ambient=%.1fC",
                actual_min, predicted_min, ratio,
                self._anomaly_threshold, ambient_c,
            )
            return True

        return False

    async def _alert_slow_warmup(self, record: ColdStartRecord) -> None:
        """Queue alert for anomalously slow warmup."""
        predicted = self.predict_warmup_minutes(record.ambient_temp_c)
        actual_min = record.warmup_seconds / 60.0

        if predicted is not None:
            msg = (
                f"Took {actual_min:.0f} minutes to warm up today. "
                f"Usually takes about {predicted:.0f} minutes at {record.ambient_temp_c:.0f}C. "
                f"Could be the thermostat, low coolant, or just unusual conditions."
            )
        else:
            msg = (
                f"Took {actual_min:.0f} minutes to warm up today at {record.ambient_temp_c:.0f}C. "
                f"Still learning my warmup pattern -- will flag if this keeps happening."
            )
        await self._alerts.enqueue(
            severity=AlertSeverity.WARNING,
            category=AlertCategory.COLD_START,
            message=msg,
            data={
                "actual_warmup_min": actual_min,
                "predicted_warmup_min": predicted,
                "ambient_c": record.ambient_temp_c,
                "start_coolant_c": record.start_coolant_c,
                "trip_id": record.trip_id,
            },
        )

    async def load_history(self, db: RuneDatabase) -> None:
        """Load historical cold-start records from DB and refit model.

        Called on startup to restore state from previous sessions.
        """
        try:
            rows = await db.get_cold_starts(limit=200)
        except Exception:
            logger.exception("Failed to load cold-start history from DB")
            return

        for row in rows:
            record = ColdStartRecord(
                trip_id=row.get("trip_id"),
                ambient_temp_c=row["ambient_temp_c"],
                start_coolant_c=row.get("start_coolant_c", 0.0),
                target_coolant_c=row.get("target_coolant_c", self._target_c),
                warmup_seconds=row["warmup_seconds"],
                timestamp=row.get("ts", 0) / 1000.0 if row.get("ts") else 0.0,
            )
            self._records.append(record)

        if len(self._records) >= self._min_samples:
            self.fit_model()
            logger.info(
                "Loaded %d cold-start records from DB, model fitted",
                len(self._records),
            )
        else:
            logger.info(
                "Loaded %d cold-start records from DB (need %d for model)",
                len(self._records), self._min_samples,
            )
