"""System information reader for the Rune diagnostics dashboard.

Reads CPU, RAM, disk, temperature, and uptime using only stdlib.
Linux path (/proc, /sys) is production (Pi). macOS path is for dev.

No psutil dependency -- the Pi has limited RAM and every package matters.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import subprocess
import sys
import time

logger = logging.getLogger(__name__)

_IS_LINUX = platform.system() == "Linux"
_IS_MAC = platform.system() == "Darwin"


# --- CPU Usage (requires two samples with a delay) ---

def _read_proc_stat() -> tuple[int, int]:
    """Read /proc/stat, return (idle_ticks, total_ticks)."""
    with open("/proc/stat") as f:
        line = f.readline()
    # "cpu  user nice system idle iowait irq softirq steal guest guest_nice"
    values = [int(x) for x in line.split()[1:]]
    idle = values[3] + values[4]  # idle + iowait
    total = sum(values)
    return idle, total


async def _get_cpu_percent(interval: float = 0.15) -> float:
    """Get CPU usage percentage.

    Linux: samples /proc/stat twice with asyncio.sleep between.
    macOS: uses os.getloadavg() normalized by CPU count (no kern.cp_time
    on Darwin -- that's FreeBSD-only).
    """
    import asyncio

    if _IS_LINUX:
        idle1, total1 = _read_proc_stat()
        await asyncio.sleep(interval)
        idle2, total2 = _read_proc_stat()
        total_delta = total2 - total1
        if total_delta == 0:
            return 0.0
        return round((1.0 - (idle2 - idle1) / total_delta) * 100, 1)

    if _IS_MAC:
        # os.getloadavg() returns 1/5/15 min load averages (Unix standard)
        # Normalize by CPU count to get approximate utilization percentage
        try:
            load_1min = os.getloadavg()[0]
            ncpu = os.cpu_count() or 1
            # Load average can exceed 100% (runnable threads > cores)
            return round(min(load_1min / ncpu * 100, 100.0), 1)
        except OSError:
            return 0.0

    return 0.0


# --- RAM Usage ---

def _get_ram_linux() -> dict[str, float]:
    """Read /proc/meminfo. Uses MemAvailable (not MemFree) for accuracy."""
    info: dict[str, int] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val = int(parts[1].split()[0])  # value in kB
                info[key] = val

    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", info.get("MemFree", 0))
    used = total - available
    return {
        "total_mb": round(total / 1024, 1),
        "used_mb": round(used / 1024, 1),
        "available_mb": round(available / 1024, 1),
        "percent": round(used / total * 100, 1) if total > 0 else 0.0,
    }


def _get_ram_mac() -> dict[str, float]:
    """Read vm_stat + sysctl hw.memsize for macOS RAM usage."""
    try:
        out = subprocess.check_output(["vm_stat"], text=True, timeout=5)
        total_bytes = int(subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"], text=True, timeout=5,
        ).strip())
    except (subprocess.SubprocessError, ValueError):
        return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0.0}

    # Parse page size from first line
    page_match = re.search(r"page size of (\d+) bytes", out)
    page_size = int(page_match.group(1)) if page_match else 4096

    stats: dict[str, int] = {}
    for line in out.splitlines()[1:]:
        m = re.match(r"(.+):\s+(\d+)", line)
        if m:
            stats[m.group(1).strip()] = int(m.group(2))

    wired = stats.get("Pages wired down", 0) * page_size
    active = stats.get("Pages active", 0) * page_size
    compressed = stats.get("Pages occupied by compressor", 0) * page_size
    used = wired + active + compressed

    return {
        "total_mb": round(total_bytes / 1024 / 1024, 1),
        "used_mb": round(used / 1024 / 1024, 1),
        "available_mb": round((total_bytes - used) / 1024 / 1024, 1),
        "percent": round(used / total_bytes * 100, 1) if total_bytes > 0 else 0.0,
    }


def _get_ram() -> dict[str, float]:
    if _IS_LINUX:
        return _get_ram_linux()
    if _IS_MAC:
        return _get_ram_mac()
    return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0.0}


# --- Disk Usage ---

def _get_disk(path: str = "/") -> dict[str, float]:
    """Disk usage via os.statvfs(). Cross-platform, no dependencies.

    Uses f_bavail (blocks available to non-root) not f_bfree,
    matching what `df` reports.
    """
    try:
        st = os.statvfs(path)
    except OSError:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0.0}

    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - free
    return {
        "total_gb": round(total / 1024**3, 2),
        "used_gb": round(used / 1024**3, 2),
        "free_gb": round(free / 1024**3, 2),
        "percent": round(used / total * 100, 1) if total > 0 else 0.0,
    }


# --- CPU Temperature ---

def _get_cpu_temp() -> float | None:
    """Read CPU temperature. Pi: /sys/class/thermal. macOS: not available."""
    if _IS_LINUX:
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return round(int(f.read().strip()) / 1000, 1)
        except (OSError, ValueError):
            return None
    return None


# --- Uptime ---

def _get_uptime() -> float:
    """System uptime in seconds."""
    if _IS_LINUX:
        try:
            with open("/proc/uptime") as f:
                return round(float(f.read().split()[0]), 1)
        except (OSError, ValueError):
            return 0.0

    if _IS_MAC:
        try:
            out = subprocess.check_output(
                ["sysctl", "kern.boottime"], text=True, timeout=5,
            )
            m = re.search(r"sec\s*=\s*(\d+)", out)
            if m:
                return round(time.time() - int(m.group(1)), 1)
        except (subprocess.SubprocessError, ValueError):
            pass

    return 0.0


# --- Public API ---

async def get_system_info() -> dict[str, object]:
    """Collect all system metrics. Returns a JSON-serializable dict."""
    ram = _get_ram()
    disk = _get_disk("/")
    cpu_temp = _get_cpu_temp()
    uptime = _get_uptime()
    cpu_pct = await _get_cpu_percent()

    return {
        "cpu_percent": cpu_pct,
        "ram": ram,
        "disk": disk,
        "cpu_temp_c": cpu_temp,
        "uptime_seconds": uptime,
        "python_version": platform.python_version(),
        "os_version": f"{platform.system()} {platform.release()}",
        "hostname": platform.node(),
        "architecture": platform.machine(),
    }
