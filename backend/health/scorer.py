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
import math
import random
import time
from dataclasses import dataclass, field

from backend.health.rules import compute_overall, score_subsystems
from backend.health.thresholds import SUBSYSTEM_WEIGHTS
from backend.obd_manager.models import HealthSnapshot, VehicleSnapshot

logger = logging.getLogger(__name__)


# --- Online HalfSpaceTrees implementation ---
# River ML doesn't compile on Python 3.14, so we implement the core algorithm.
# Based on Tan et al. "Fast Anomaly Detection for Streaming Data" (IJCAI 2011).
# O(1) per sample, constant memory, no retraining needed.


@dataclass
class _HalfSpaceNode:
    """A single split node in a half-space tree."""
    feature: int        # which feature to split on
    split_value: float  # threshold value
    left_count: float   # count on left side (with decay)
    right_count: float  # count on right side (with decay)


class HalfSpaceTrees:
    """Online streaming anomaly detector.

    Builds a forest of random half-space partitions. Normal data
    lands in dense regions (high counts). Anomalies land in sparse
    regions (low counts). Learns continuously from each sample.

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

        # Feature ranges for normalization (learned online)
        self._min_vals = [float("inf")] * n_features
        self._max_vals = [float("-inf")] * n_features

        # Build random trees
        rng = random.Random(seed)
        self._trees: list[list[_HalfSpaceNode]] = []
        for _ in range(n_trees):
            tree: list[_HalfSpaceNode] = []
            for _ in range(2 ** height - 1):  # full binary tree nodes
                feat = rng.randint(0, n_features - 1)
                split = rng.random()  # split in [0, 1] after normalization
                tree.append(_HalfSpaceNode(feat, split, 0.0, 0.0))
            self._trees.append(tree)

    def _normalize(self, features: list[float]) -> list[float]:
        """Normalize features to [0, 1] based on observed min/max."""
        result = []
        for i, v in enumerate(features):
            # Update ranges
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

    def _traverse(self, tree: list[_HalfSpaceNode], normed: list[float]) -> int:
        """Traverse tree to find leaf index. Returns node index."""
        idx = 0
        for _ in range(self._height - 1):
            node = tree[idx]
            if normed[node.feature] < node.split_value:
                idx = 2 * idx + 1  # left child
            else:
                idx = 2 * idx + 2  # right child
            if idx >= len(tree):
                break
        return min(idx, len(tree) - 1)

    def score_and_learn(self, features: list[float]) -> float:
        """Score a sample and update the model. Returns 0.0 (normal) to 1.0 (anomaly)."""
        self._sample_count += 1
        normed = self._normalize(features)

        total_score = 0.0
        decay = 2 ** (-1.0 / self._window_size)  # exponential decay factor

        for tree in self._trees:
            leaf_idx = self._traverse(tree, normed)
            node = tree[leaf_idx]

            # Score based on count at this leaf (lower count = more anomalous)
            if normed[node.feature] < node.split_value:
                count = node.left_count
            else:
                count = node.right_count

            # Anomaly score for this tree: inverse of density
            # Add 1 to avoid division by zero
            tree_score = 1.0 / (count + 1)
            total_score += tree_score

            # Update counts with exponential decay (windowed learning)
            for n in tree:
                n.left_count *= decay
                n.right_count *= decay

            # Increment the leaf this sample landed in
            if normed[node.feature] < node.split_value:
                node.left_count += 1
            else:
                node.right_count += 1

        # Normalize score to [0, 1]
        avg_score = total_score / self._n_trees
        # Sigmoid-like normalization: map to [0, 1]
        # Score of ~1.0 when count is 0 (never seen), ~0.0 when count is high
        normalized = min(1.0, avg_score * math.sqrt(self._sample_count / max(self._window_size, 1)))

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

        # EWMA smoothers for key parameters (trend pre-filtering)
        self._ewma: dict[str, EWMA] = {
            "coolant_temp_c": EWMA(alpha=0.05),
            "ltft_pct": EWMA(alpha=0.05),
            "battery_voltage": EWMA(alpha=0.05),
            "catalyst_temp_c": EWMA(alpha=0.05),
            "oil_temp_c": EWMA(alpha=0.05),
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
        """Score a VehicleSnapshot. Called every tick (10Hz)."""
        self._sample_count += 1

        if not self._calibration_complete and self._sample_count >= self._calibration_threshold:
            self._calibration_complete = True
            logger.info("Health scorer calibration complete after %d samples", self._sample_count)

        # Update EWMA smoothers
        for param, ewma in self._ewma.items():
            value = getattr(snap, param, None)
            if value is not None:
                ewma.update(value)

        # Layer 1: Threshold-based subsystem scoring
        subsystem_scores = score_subsystems(snap)

        # Layer 2: Online anomaly detection
        features = _snap_to_features(snap)
        anomaly_score = self._hst.score_and_learn(features)
        self._last_anomaly_score = anomaly_score

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
        """Identify which subsystem is most anomalous based on EWMA deviation."""
        max_deviation = 0.0
        worst = "engine"

        # Check coolant deviation -> cooling
        if "coolant_temp_c" in self._ewma:
            dev = abs(snap.coolant_temp_c - self._ewma["coolant_temp_c"].value)
            if dev > max_deviation:
                max_deviation = dev
                worst = "cooling"

        # Check LTFT deviation -> fuel
        if "ltft_pct" in self._ewma:
            dev = abs(snap.ltft_pct - self._ewma["ltft_pct"].value)
            # Scale fuel trim deviation higher (5% LTFT drift is more serious than 5C coolant)
            if dev * 3 > max_deviation:
                max_deviation = dev * 3
                worst = "fuel"

        # Check voltage deviation -> electrical
        if "battery_voltage" in self._ewma:
            dev = abs(snap.battery_voltage - self._ewma["battery_voltage"].value)
            # Scale voltage deviation (0.5V drop is very significant)
            if dev * 10 > max_deviation:
                max_deviation = dev * 10
                worst = "electrical"

        # Check catalyst deviation -> exhaust
        if "catalyst_temp_c" in self._ewma:
            dev = abs(snap.catalyst_temp_c - self._ewma["catalyst_temp_c"].value)
            if dev > max_deviation:
                max_deviation = dev
                worst = "exhaust"

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
