"""Data collector abstraction layer.

The rest of the app talks to a DataCollector, not directly to the
simulator or OBD connection. When the real hardware arrives, we swap
the source underneath and nothing else changes.

Think of it like a TV remote -- you press "get data" and it works
whether the source is the simulator or the real WiCAN Pro.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from backend.obd_manager.models import VehicleSnapshot
from backend.obd_manager.simulator import AnomalyConfig, HondaAccordSimulator

logger = logging.getLogger(__name__)


class DataCollector(ABC):
    """Abstract base for all data sources."""

    @abstractmethod
    async def start(self) -> None:
        """Start collecting data."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop collecting data."""

    @abstractmethod
    async def get_snapshot(self) -> VehicleSnapshot:
        """Get the current vehicle state."""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Whether the collector is actively running."""


class SimulatedCollector(DataCollector):
    """Collector backed by the Honda Accord simulator.

    Used during development (Mac) and testing. Produces realistic
    sensor data without any hardware.
    """

    def __init__(
        self,
        ambient_temp_c: float = 20.0,
        initial_fuel_pct: float = 75.0,
        anomalies: list[AnomalyConfig] | None = None,
    ) -> None:
        self._sim = HondaAccordSimulator(
            ambient_temp_c=ambient_temp_c,
            initial_fuel_pct=initial_fuel_pct,
            anomalies=anomalies,
        )

    async def start(self) -> None:
        self._sim.start()
        logger.info("SimulatedCollector started")

    async def stop(self) -> None:
        self._sim.stop()
        logger.info("SimulatedCollector stopped")

    async def get_snapshot(self) -> VehicleSnapshot:
        return self._sim.get_snapshot()

    @property
    def is_running(self) -> bool:
        return self._sim.is_running


class OBDCollector(DataCollector):
    """Collector backed by a real OBD-II connection via SafeOBDConnection.

    Placeholder for Week 5 when the WiCAN Pro hardware arrives.
    Will connect to WiCAN Pro at TCP:3333 in ELM327 mode.
    """

    async def start(self) -> None:
        raise NotImplementedError("OBDCollector is a Week 5 placeholder")

    async def stop(self) -> None:
        raise NotImplementedError("OBDCollector is a Week 5 placeholder")

    async def get_snapshot(self) -> VehicleSnapshot:
        raise NotImplementedError("OBDCollector is a Week 5 placeholder")

    @property
    def is_running(self) -> bool:
        return False
