"""Rune Witty Pi Scheduler -- writes wake/sleep schedule files.

Controls when the Pi wakes up while parked by writing Witty Pi 4
schedule files. The schedule tells the Witty Pi RTC when to power
on the Pi and how long to keep it running.

Witty Pi 4 schedule format (from UUGear documentation):
  https://www.uugear.com/doc/WittyPi4_UserManual.pdf

  BEGIN <start_datetime>   # YYYY-MM-DD HH:MM:SS (optional)
  END   <end_datetime>     # YYYY-MM-DD HH:MM:SS (optional)
  ON    H0 M0 S30          # Stay on for 30 seconds
  OFF   H2 M0              # Stay off for 2 hours

The schedule loops: ON for 30s, OFF for 2h, ON for 30s, OFF for 2h...
The Pi boots, Rune runs a quick parked check (thermal + battery),
queues any alerts, then shuts down. Total wake time: ~30 seconds.

Safety: schedule files are validated before writing. If validation
fails, no file is written and the Pi stays on its current schedule.
"""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

# Witty Pi schedule file location
# UUGear installs to /opt/wittypi/ (confirmed in session 13 setup)
SCHEDULE_FILE = "/opt/wittypi/schedule.wpi"
WITTYPI_DIR = "/opt/wittypi"


def write_parked_schedule(
    wake_seconds: int = 30,
    sleep_hours: float = 2.0,
) -> bool:
    """Write a parked-mode wake/sleep schedule to Witty Pi.

    The Pi will wake for wake_seconds, then sleep for sleep_hours,
    repeating indefinitely until the car starts (ignition powers Pi
    continuously, overriding the schedule).

    Args:
        wake_seconds: How long to stay on per cycle (default 30s).
            Must be >= 20 (boot + check takes ~15s minimum).
        sleep_hours: How long to stay off between wakes (default 2h).

    Returns:
        True if schedule was written successfully, False on error.
    """
    if wake_seconds < 20:
        logger.error("Wake time too short: %ds (minimum 20s for boot + check)", wake_seconds)
        return False
    if sleep_hours < 0.5:
        logger.error("Sleep time too short: %.1fh (minimum 0.5h)", sleep_hours)
        return False

    # Decompose wake_seconds into M/S (Witty Pi expects S < 60)
    wake_min = wake_seconds // 60
    wake_sec = wake_seconds % 60

    # Convert sleep_hours to hours and minutes
    total_minutes = int(sleep_hours * 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    schedule_content = (
        f"# Rune parked-mode schedule\n"
        f"# Wake every {sleep_hours:.1f}h for {wake_seconds}s to check thermal + battery\n"
        f"ON   H0 M{wake_min} S{wake_sec}\n"
        f"OFF  H{hours} M{minutes}\n"
    )

    try:
        # Write to temp file first, then move (atomic on same filesystem)
        tmp_path = SCHEDULE_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(schedule_content)
        os.replace(tmp_path, SCHEDULE_FILE)

        # Tell Witty Pi daemon to reload the schedule
        _apply_schedule()

        logger.info(
            "Parked schedule written: ON %ds, OFF %dh%dm",
            wake_seconds, hours, minutes,
        )
        return True
    except OSError:
        logger.exception("Failed to write Witty Pi schedule file")
        return False


def clear_schedule() -> bool:
    """Remove the schedule file so Pi stays on continuously.

    Called when the car starts (ignition on) so the Witty Pi
    doesn't try to shut down the Pi while driving.

    Returns:
        True if cleared, False on error.
    """
    try:
        if os.path.exists(SCHEDULE_FILE):
            os.remove(SCHEDULE_FILE)
            _apply_schedule()
            logger.info("Witty Pi schedule cleared (continuous power mode)")
        return True
    except OSError:
        logger.exception("Failed to clear Witty Pi schedule")
        return False


def _apply_schedule() -> None:
    """Run Witty Pi's runScript.sh to apply the current schedule.

    This tells the Witty Pi daemon to read the schedule file and
    program the RTC accordingly.
    """
    run_script = os.path.join(WITTYPI_DIR, "runScript.sh")
    if not os.path.exists(run_script):
        logger.warning("Witty Pi runScript.sh not found at %s", run_script)
        return

    try:
        result = subprocess.run(
            ["sudo", "bash", run_script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.warning(
                "Witty Pi runScript.sh failed (rc=%d): %s",
                result.returncode, result.stderr.strip(),
            )
    except subprocess.TimeoutExpired:
        logger.warning("Witty Pi runScript.sh timed out")
    except Exception:
        logger.exception("Failed to run Witty Pi schedule script")


def emergency_shutdown(reason: str) -> None:
    """Initiate immediate graceful shutdown.

    Flushes DB (via the beforeShutdown.sh hook) and powers off.
    The Witty Pi RTC will wake the Pi on the next scheduled cycle.

    Args:
        reason: Human-readable reason for the shutdown (logged).
    """
    logger.critical("EMERGENCY SHUTDOWN: %s", reason)
    try:
        subprocess.run(
            ["sudo", "shutdown", "-h", "now", f"Rune: {reason}"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        logger.critical("shutdown command failed, forcing halt")
        try:
            subprocess.run(
                ["sudo", "halt", "-f"],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            logger.critical("halt also failed -- hardware power-off required")
