"""Health scoring engine -- where Rune learns to understand what he feels.

Three layers of awareness:
1. Threshold scoring (every tick): Honda-specific ranges, instant alerts
2. Online anomaly detection (every tick): HalfSpaceTrees, learns continuously
3. Trend analysis (every 5 minutes): EWMA-smoothed regression for slow degradation

The scorer runs at 10Hz on the Pi. Sub-millisecond per tick for layers 1+2.
Layer 3 runs on a separate timer.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from backend.health.rules import compute_overall, score_subsystems
from backend.health.thresholds import EWMA_ALPHAS, SUBSYSTEM_WEIGHTS
from backend.obd_manager.models import HealthSnapshot, VehicleSnapshot

logger = logging.getLogger(__name__)


# --- Online HalfSpaceTrees implementation ---
# River ML doesn't compile on Python 3.14, so we implement the core algorithm.
# Based on Tan et al. "Fast Anomaly Detection for Streaming Data" (IJCAI 2011).
# Reference implementation: river/anomaly/hst.py
#
# Key algorithm details (verified against River source):
# - Each node has TWO mass counters: l_mass (current window) and r_mass (reference).
# - On learn: increment l_mass on EVERY node along the root-to-leaf path.
# - Window swap: after window_size samples, copy l_mass -> r_mass, reset l_mass = 0.
# - Scoring: walk root-to-leaf, accumulate r_mass * 2^depth at each node.
# - Early stop if r_mass < size_limit (0.1 * window_size).
# - Normalization: max_score = n_trees * window_size * (2^(height+1) - 1).
# - Final = 1 - (raw / max). 0 = normal, 1 = anomaly.
# - Warm-up guard: return 0.0 until first window pivot completes.


@dataclass
class _HSTNode:
    """A node in the half-space tree (internal or leaf)."""
    feature: int
    split_value: float
    left: _HSTNode | None = None
    right: _HSTNode | None = None
    l_mass: float = 0.0   # current window mass
    r_mass: float = 0.0   # reference window mass


def _build_tree(
    rng: random.Random,
    n_features: int,
    height: int,
    ranges: list[tuple[float, float]],
    depth: int = 0,
) -> _HSTNode:
    """Recursively build a random half-space tree with padded split values."""
    feature = rng.randint(0, n_features - 1)
    a, b = ranges[feature]
    span = b - a
    # 15% padding on each side to avoid degenerate splits at boundaries
    pad = 0.15 * span
    if span > 0:
        split = rng.uniform(a + pad, b - pad)
    else:
        split = a

    node = _HSTNode(feature=feature, split_value=split)

    if depth < height:
        # Narrow the range for children
        left_ranges = list(ranges)
        left_ranges[feature] = (a, split)
        right_ranges = list(ranges)
        right_ranges[feature] = (split, b)

        node.left = _build_tree(rng, n_features, height, left_ranges, depth + 1)
        node.right = _build_tree(rng, n_features, height, right_ranges, depth + 1)

    return node


def _reset_masses(node: _HSTNode | None) -> None:
    """Swap l_mass -> r_mass and reset l_mass for all nodes."""
    if node is None:
        return
    node.r_mass = node.l_mass
    node.l_mass = 0.0
    _reset_masses(node.left)
    _reset_masses(node.right)


class HalfSpaceTrees:
    """Online streaming anomaly detector.

    Builds a forest of random half-space partitions. Normal data
    lands in dense regions (high mass). Anomalies land in sparse
    regions (low mass). Learns continuously from each sample.

    Usage:
        hst = HalfSpaceTrees(n_features=14)
        score = hst.score_and_learn(features)  # 0.0 = normal, 1.0 = anomaly
    """

    def __init__(
        self,
        n_features: int,
        n_trees: int = 25,
        height: int = 6,
        window_size: int = 500,
        seed: int = 42,
    ) -> None:
        self._n_features = n_features
        self._n_trees = n_trees
        self._height = height
        self._window_size = window_size
        self._sample_count = 0
        self._size_limit = 0.1 * window_size
        self._window_pivoted = False

        # Max possible score for normalization
        # Each tree can contribute at most window_size * sum(2^d for d in 0..height)
        # = window_size * (2^(height+1) - 1)
        self._max_score = float(n_trees * window_size * (2 ** (height + 1) - 1))

        # Feature ranges for normalization (learned online)
        self._min_vals = [float("inf")] * n_features
        self._max_vals = [float("-inf")] * n_features

        # Build random trees with initial [0, 1] ranges
        rng = random.Random(seed)
        initial_ranges = [(0.0, 1.0)] * n_features
        self._trees: list[_HSTNode] = []
        for _ in range(n_trees):
            tree = _build_tree(rng, n_features, height, initial_ranges)
            self._trees.append(tree)

    def _normalize(self, features: list[float]) -> list[float]:
        """Normalize features to [0, 1] based on observed min/max."""
        result: list[float] = []
        for i, v in enumerate(features):
            if v < self._min_vals[i]:
                self._min_vals[i] = v
            if v > self._max_vals[i]:
                self._max_vals[i] = v

            span = self._max_vals[i] - self._min_vals[i]
            if span > 0:
                result.append((v - self._min_vals[i]) / span)
            else:
                result.append(0.5)
        return result

    def _learn_path(self, node: _HSTNode | None, normed: list[float]) -> None:
        """Walk root to leaf, incrementing l_mass on every node along the path."""
        if node is None:
            return
        node.l_mass += 1.0
        if node.left is None and node.right is None:
            return  # leaf
        if normed[node.feature] < node.split_value:
            self._learn_path(node.left, normed)
        else:
            self._learn_path(node.right, normed)

    def _score_path(self, node: _HSTNode | None, normed: list[float], depth: int) -> float:
        """Walk root to leaf, accumulating r_mass * 2^depth. Early stop on small mass."""
        if node is None:
            return 0.0

        # Early stop: if reference mass is too small, this region is too sparse to be useful
        if node.r_mass < self._size_limit:
            return 0.0

        score = node.r_mass * (2.0 ** depth)

        if node.left is None and node.right is None:
            return score  # leaf

        if normed[node.feature] < node.split_value:
            return score + self._score_path(node.left, normed, depth + 1)
        else:
            return score + self._score_path(node.right, normed, depth + 1)

    def score_and_learn(self, features: list[float]) -> float:
        """Score a sample and update the model. Returns 0.0 (normal) to 1.0 (anomaly)."""
        self._sample_count += 1
        normed = self._normalize(features)

        # Score BEFORE learning (score uses r_mass, learn updates l_mass)
        raw_score = 0.0
        if self._window_pivoted and self._max_score > 0:
            for tree in self._trees:
                raw_score += self._score_path(tree, normed, depth=0)

        # Learn: update l_mass along the path
        for tree in self._trees:
            self._learn_path(tree, normed)

        # Window swap: after window_size samples, pivot
        if self._sample_count % self._window_size == 0:
            for tree in self._trees:
                _reset_masses(tree)
            self._window_pivoted = True

        # Warm-up guard: return 0.0 until first window pivot
        if not self._window_pivoted:
            return 0.0

        # Normalize: high raw_score = normal (dense), low = anomaly (sparse)
        normalized = 1.0 - (raw_score / self._max_score)
        return max(0.0, min(1.0, normalized))


# --- EWMA for trend pre-filtering ---


class EWMA:
    """Exponentially Weighted Moving Average with bias correction."""

    def __init__(self, alpha: float = 0.1) -> None:
        self._alpha = alpha
        self._value = 0.0
        self._count = 0

    def update(self, value: float) -> float:
        """Update with new value, return smoothed result."""
        self._count += 1
        if self._count == 1:
            self._value = value
        else:
            self._value = self._alpha * value + (1 - self._alpha) * self._value

        # Bias correction for early samples
        correction = 1.0 - (1.0 - self._alpha) ** self._count
        return self._value / correction if correction > 0 else self._value

    @property
    def value(self) -> float:
        if self._count == 0:
            return 0.0
        correction = 1.0 - (1.0 - self._alpha) ** self._count
        return self._value / correction if correction > 0 else self._value


# --- Main Health Scorer ---


SCORED_FEATURES = [
    "rpm", "speed_kph", "coolant_temp_c", "engine_load_pct",
    "throttle_pct", "intake_air_temp_c", "intake_manifold_kpa",
    "maf_gps", "stft_pct", "ltft_pct", "fuel_level_pct",
    "catalyst_temp_c", "oil_temp_c", "battery_voltage",
]


def _snap_to_features(snap: VehicleSnapshot) -> list[float]:
    """Extract feature vector from VehicleSnapshot."""
    return [getattr(snap, f) for f in SCORED_FEATURES]


class HealthScorer:
    """The health scoring engine. Call score() every tick (10Hz).

    Layer 1: Honda threshold scoring (every tick)
    Layer 2: HalfSpaceTrees anomaly detection (every tick)
    Layer 3: Trend analysis via EWMA (ongoing, checked periodically)
    """

    def __init__(
        self,
        n_trees: int = 25,
        tree_height: int = 6,
        window_size: int = 500,
        calibration_samples: int = 3000,  # ~5 minutes at 10Hz for quick start
    ) -> None:
        self._hst = HalfSpaceTrees(
            n_features=len(SCORED_FEATURES),
            n_trees=n_trees,
            height=tree_height,
            window_size=window_size,
        )
        self._calibration_threshold = calibration_samples
        self._sample_count = 0
        self._calibration_complete = False

        # EWMA smoothers with sensor-appropriate alpha values
        self._ewma: dict[str, EWMA] = {
            param: EWMA(alpha=alpha) for param, alpha in EWMA_ALPHAS.items()
        }

        # Last anomaly score for debug/logging
        self._last_anomaly_score = 0.0

        # Anomaly alert tracking
        self._consecutive_anomalies = 0
        self._anomaly_threshold = 0.6  # score above this = anomaly

    @property
    def calibration_complete(self) -> bool:
        return self._calibration_complete

    @property
    def calibration_progress(self) -> float:
        """0.0 to 1.0 calibration progress."""
        return min(1.0, self._sample_count / self._calibration_threshold)

    @property
    def last_anomaly_score(self) -> float:
        return self._last_anomaly_score

    @property
    def sample_count(self) -> int:
        return self._sample_count

    def score(self, snap: VehicleSnapshot) -> HealthSnapshot:
        """Score a VehicleSnapshot. Called every tick (10Hz).

        During calibration (first ~5 min), returns -1 sentinel for all scores
        so the frontend can show "calibrating" instead of fake 100s.
        """
        self._sample_count += 1

        if not self._calibration_complete and self._sample_count >= self._calibration_threshold:
            # Don't complete calibration if data looks like garbage (OBD not connected).
            # Real engine data has RPM > 0 or coolant > ambient. All zeros = no real data.
            has_real_data = snap.rpm > 0 or snap.coolant_temp_c > 10
            if has_real_data:
                self._calibration_complete = True
                logger.info("Health scorer calibration complete after %d samples", self._sample_count)
            else:
                logger.debug("Calibration deferred: data looks like OBD defaults (rpm=%.0f, coolant=%.0f)",
                             snap.rpm, snap.coolant_temp_c)

        # Update EWMA smoothers (always, even during calibration)
        for param, ewma in self._ewma.items():
            value = getattr(snap, param, None)
            if value is not None:
                ewma.update(value)

        # Feed HalfSpaceTrees even during calibration so it warms up
        features = _snap_to_features(snap)
        anomaly_score = self._hst.score_and_learn(features)
        self._last_anomaly_score = anomaly_score

        # During calibration, return -1 sentinel -- the frontend knows to show "--"
        if not self._calibration_complete:
            return HealthSnapshot(
                overall=-1, engine=-1, transmission=-1,
                fuel=-1, cooling=-1, exhaust=-1, electrical=-1,
            )

        # Layer 1: Threshold-based subsystem scoring
        subsystem_scores = score_subsystems(snap)

        # Layer 2: anomaly_score already computed above (before calibration gate)
        # Track consecutive anomalies
        if anomaly_score > self._anomaly_threshold:
            self._consecutive_anomalies += 1
        else:
            self._consecutive_anomalies = 0

        # Blend anomaly score into subsystem scores when significant
        if self._calibration_complete and anomaly_score > self._anomaly_threshold:
            # Find which subsystem is most affected by identifying
            # which parameters deviate most from their EWMA baseline
            worst_subsystem = self._identify_affected_subsystem(snap)
            penalty = (anomaly_score - self._anomaly_threshold) * 50
            subsystem_scores[worst_subsystem] = max(
                0.0, subsystem_scores[worst_subsystem] - penalty
            )

        # Compute overall
        overall = compute_overall(subsystem_scores)

        return HealthSnapshot(
            overall=round(overall, 1),
            engine=round(subsystem_scores.get("engine", 100.0), 1),
            transmission=round(subsystem_scores.get("transmission", 100.0), 1),
            fuel=round(subsystem_scores.get("fuel", 100.0), 1),
            cooling=round(subsystem_scores.get("cooling", 100.0), 1),
            exhaust=round(subsystem_scores.get("exhaust", 100.0), 1),
            electrical=round(subsystem_scores.get("electrical", 100.0), 1),
        )

    def _identify_affected_subsystem(self, snap: VehicleSnapshot) -> str:
        """Identify which subsystem is most anomalous based on EWMA deviation.

        Deviations are normalized by each sensor's normal range width so
        that a 50C catalyst swing (normal variation in a 500C range) doesn't
        outweigh a 0.5V voltage drop (serious in a 3V range).
        """
        max_deviation = 0.0
        worst = "engine"

        # (sensor, subsystem, normal_range_width)
        # range_width = how wide the "normal" band is for this sensor
        checks: list[tuple[str, str, float]] = [
            ("coolant_temp_c", "cooling", 25.0),     # 75-100C = 25C range
            ("ltft_pct", "fuel", 10.0),               # +/-5% = 10% range
            ("battery_voltage", "electrical", 3.0),   # 12.0-15.0V = 3V range
            ("catalyst_temp_c", "exhaust", 500.0),    # 300-800C = 500C range
            ("oil_temp_c", "cooling", 40.0),          # 80-120C = 40C range
        ]

        for param, subsystem, range_width in checks:
            if param not in self._ewma:
                continue
            dev = abs(getattr(snap, param) - self._ewma[param].value)
            # Normalize: deviation as fraction of normal range
            normalized = dev / range_width if range_width > 0 else 0
            if normalized > max_deviation:
                max_deviation = normalized
                worst = subsystem

        return worst

    def get_debug_state(self) -> dict[str, object]:
        """Return scorer internal state for the debug dashboard."""
        return {
            "calibration_complete": self._calibration_complete,
            "calibration_progress": round(self.calibration_progress * 100, 1),
            "sample_count": self._sample_count,
            "last_anomaly_score": round(self._last_anomaly_score, 4),
            "consecutive_anomalies": self._consecutive_anomalies,
            "ewma_values": {k: round(v.value, 2) for k, v in self._ewma.items()},
        }
