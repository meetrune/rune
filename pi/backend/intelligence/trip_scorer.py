"""Rune Trip Scorer -- scores each trip on efficiency, smoothness, and idle ratio.

Three scoring axes (0-100 each):
1. Efficiency: trip MPG vs personal EWMA baseline (or EPA combined on cold start)
2. Smoothness: penalizes hard acceleration and hard braking events per mile
3. Idle ratio: penalizes time spent idling (RPM > 0, speed = 0)

Composite = 0.5 * efficiency + 0.3 * smoothness + 0.2 * idle_ratio
Weights are efficiency-heavy, aligned with telematics industry practice.

Research sources cited inline at each threshold/formula.
"""

from __future__ import annotations

import logging
from collections import deque

from backend.config import settings
from backend.intelligence.models import TripScore

logger = logging.getLogger(__name__)


class TripScorer:
    """Scores trips on efficiency, smoothness, and idle ratio.

    Call start_trip() before each trip, update() at 10Hz during the trip,
    and score_trip() at trip end to get the final TripScore.
    """

    def __init__(
        self,
        epa_combined_mpg: float = settings.epa_combined_mpg,
        baseline_alpha: float = settings.trip_score_baseline_alpha,
    ) -> None:
        self._epa_combined_mpg = epa_combined_mpg
        self._baseline_alpha = baseline_alpha

        # Personal baseline: EWMA of recent trip MPGs.
        # None until at least one trip is scored.
        self._baseline_mpg: float | None = None

        # Rolling history for diagnostics (not used in EWMA calc, kept for
        # potential future debug/export). Max 20 to bound memory.
        self._mpg_history: deque[float] = deque(maxlen=20)

        # Per-trip accumulators (reset each start_trip)
        self._prev_throttle: float | None = None
        self._hard_accel_count: int = 0
        self._hard_brake_count: int = 0
        self._prev_speed_kph: float | None = None
        self._idle_time: float = 0.0
        self._total_time: float = 0.0

    def start_trip(self) -> None:
        """Reset per-trip accumulators. Call at beginning of each trip."""
        self._prev_throttle = None
        self._hard_accel_count = 0
        self._hard_brake_count = 0
        self._prev_speed_kph = None
        self._idle_time = 0.0
        self._total_time = 0.0

    def update(
        self,
        throttle_pct: float,
        speed_kph: float,
        rpm: float,
        dt_seconds: float,
    ) -> None:
        """Ingest one sensor tick (called at ~10Hz).

        Args:
            throttle_pct: Throttle position 0-100 (PID 0111).
            speed_kph: Vehicle speed in km/h (PID 010D).
            rpm: Engine RPM (PID 010C).
            dt_seconds: Time elapsed since last tick.
        """
        if dt_seconds <= 0:
            return

        self._total_time += dt_seconds

        # --- Idle detection ---
        # Idle = engine running (RPM > 0) but not moving (speed = 0).
        # Source: standard telematics idle definition.
        if rpm > 0 and speed_kph == 0:
            self._idle_time += dt_seconds

        # --- Throttle rate-of-change for hard acceleration ---
        # Threshold: |d(throttle)/dt| > 15 %/sec
        # Source: NHTSA eco-driving research identifies rapid throttle
        # changes above ~15%/sec as aggressive acceleration events.
        if self._prev_throttle is not None:
            throttle_rate = abs(throttle_pct - self._prev_throttle) / dt_seconds
            if throttle_rate > settings.trip_score_hard_accel_threshold:
                self._hard_accel_count += 1
        self._prev_throttle = throttle_pct

        # --- Hard braking detection ---
        # Threshold: speed drop > 11.3 km/h per second (~7 mph/sec)
        # Source: Progressive Snapshot published hard braking threshold.
        if self._prev_speed_kph is not None:
            speed_drop_rate = (self._prev_speed_kph - speed_kph) / dt_seconds
            if speed_drop_rate > settings.trip_score_hard_brake_threshold:
                self._hard_brake_count += 1
        self._prev_speed_kph = speed_kph

    def score_trip(
        self,
        trip_mpg: float,
        trip_distance_miles: float,
    ) -> TripScore:
        """Calculate final trip scores and update the personal baseline.

        Args:
            trip_mpg: Average MPG for the completed trip.
            trip_distance_miles: Total trip distance in miles.

        Returns:
            TripScore with all three axes and composite.
        """
        baseline = self.get_baseline_mpg()

        # --- Efficiency score ---
        # Compare trip MPG to personal baseline (or EPA combined if no baseline).
        # Formula: min(100, 100 * trip_mpg / baseline)
        # Score can reach 100 but not exceed it -- rewarding meeting baseline,
        # not penalizing exceeding it.
        # Source: standard fuel economy benchmarking practice.
        if baseline > 0:
            efficiency = min(100.0, 100.0 * (trip_mpg / baseline))
        else:
            efficiency = 100.0

        # --- Smoothness score ---
        # Penalize hard events (accel + brake) per mile driven.
        # Score: 100 - (hard_events_per_mile * 10), clamped [0, 100].
        # Source: NHTSA eco-driving research thresholds for acceleration;
        # Progressive Snapshot threshold for braking (~7 mph/sec = 11.3 km/h/sec).
        total_hard_events = self._hard_accel_count + self._hard_brake_count
        if trip_distance_miles > 0:
            events_per_mile = total_hard_events / trip_distance_miles
        else:
            events_per_mile = 0.0
        smoothness = max(0.0, min(100.0, 100.0 - (events_per_mile * 10.0)))

        # --- Idle ratio score ---
        # 100 * (1 - idle_time / total_time)
        # Source: standard telematics idle time penalty.
        if self._total_time > 0:
            idle_ratio = 100.0 * (1.0 - self._idle_time / self._total_time)
        else:
            idle_ratio = 100.0
        idle_ratio = max(0.0, min(100.0, idle_ratio))

        # --- Composite ---
        # Weights: 0.5 efficiency + 0.3 smoothness + 0.2 idle_ratio
        # Efficiency-heavy weighting aligned with telematics industry practice.
        composite = (
            settings.trip_score_efficiency_weight * efficiency
            + settings.trip_score_smoothness_weight * smoothness
            + settings.trip_score_idle_weight * idle_ratio
        )
        composite = max(0.0, min(100.0, composite))

        # Update personal baseline EWMA.
        # EWMA: baseline = alpha * trip_mpg + (1 - alpha) * baseline
        # Alpha = 0.15 over last ~20 trips gives recent-weighted average.
        if self._baseline_mpg is None:
            self._baseline_mpg = trip_mpg
        else:
            self._baseline_mpg = (
                self._baseline_alpha * trip_mpg
                + (1.0 - self._baseline_alpha) * self._baseline_mpg
            )
        self._mpg_history.append(trip_mpg)

        score = TripScore(
            efficiency=round(efficiency, 1),
            smoothness=round(smoothness, 1),
            idle_ratio=round(idle_ratio, 1),
            composite=round(composite, 1),
            trip_mpg=round(trip_mpg, 2),
            baseline_mpg=round(baseline, 2),
            hard_accel_count=self._hard_accel_count,
            hard_brake_count=self._hard_brake_count,
        )

        logger.info(
            "trip_scored",
            extra={
                "composite": score.composite,
                "efficiency": score.efficiency,
                "smoothness": score.smoothness,
                "idle_ratio": score.idle_ratio,
                "trip_mpg": score.trip_mpg,
                "baseline_mpg": score.baseline_mpg,
                "hard_accel": score.hard_accel_count,
                "hard_brake": score.hard_brake_count,
            },
        )

        return score

    def get_baseline_mpg(self) -> float:
        """Return current personal baseline MPG.

        Falls back to EPA combined (31 MPG for 2026 Accord SE) if no
        trips have been scored yet.
        """
        if self._baseline_mpg is None:
            return self._epa_combined_mpg
        return self._baseline_mpg
