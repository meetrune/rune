#!/usr/bin/env python3
"""Rune Mac Watcher -- process incoming SQLite exports from the Pi.

Triggered by launchd when a new .db file appears in the iCloud sync folder.
Organizes exports by year/month/date, runs analysis, maintains a latest symlink.

Compatible with macOS system Python 3.9+.

iCloud Drive structure (iOS Shortcut saves here):
  iCloud Drive / Personal / Rune / data /
    rune-2026-03-29_0914.db

Local Mac structure (organized by this script):
  ~/Rune/
    data/
      latest.db -> 2026/03/2026-03-29_0914_rune.db
      2026/
        03/
          2026-03-29_0914_rune.db
          2026-03-29_1742_rune.db
    reports/
      2026-03-29_0914_analysis.txt
    logs/
      watcher.log
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# --- Paths ---
# iCloud: iOS Shortcut drops .db files here
ICLOUD_RUNE_DATA = (
    Path.home() / "Library" / "Mobile Documents"
    / "com~apple~CloudDocs" / "Personal" / "Rune" / "data"
)

# Local: organized storage + analysis output
RUNE_DIR = Path.home() / "Rune"
DATA_DIR = RUNE_DIR / "data"
REPORTS_DIR = RUNE_DIR / "reports"
LOG_DIR = RUNE_DIR / "logs"
LOG_FILE = LOG_DIR / "watcher.log"


def log(msg: str) -> None:
    """Append timestamped message to log file and stdout."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "[{}] {}\n".format(ts, msg)
    with open(LOG_FILE, "a") as f:
        f.write(line)
    print(line, end="")


def find_newest_db() -> Optional[Path]:
    """Find the newest .db file in the iCloud data folder."""
    if not ICLOUD_RUNE_DATA.exists():
        return None
    files = list(ICLOUD_RUNE_DATA.glob("*.db"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def organize_and_copy(src: Path) -> Optional[Path]:
    """Copy DB export into organized year/month structure.

    ~/Rune/data/2026/03/2026-03-29_0914_rune.db
    """
    now = datetime.now()
    year_dir = DATA_DIR / now.strftime("%Y")
    month_dir = year_dir / now.strftime("%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    filename = now.strftime("%Y-%m-%d_%H%M") + "_rune.db"
    dest = month_dir / filename

    # Skip if we already processed this exact file (same size = same export)
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        log("Already processed: {}".format(filename))
        return None

    shutil.copy2(src, dest)
    size_kb = dest.stat().st_size / 1024
    if size_kb < 1024:
        size_str = "{:.1f} KB".format(size_kb)
    else:
        size_str = "{:.1f} MB".format(size_kb / 1024)
    log("Saved: {} ({})".format(dest.relative_to(RUNE_DIR), size_str))

    # Update latest symlink at data/latest.db
    latest = DATA_DIR / "latest.db"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(dest)

    return dest


def cleanup_icloud(keep: int = 3) -> None:
    """Remove old .db files from iCloud data folder.

    Keeps only the N most recent files to avoid iCloud bloat.
    """
    if not ICLOUD_RUNE_DATA.exists():
        return
    files = sorted(
        ICLOUD_RUNE_DATA.glob("*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[keep:]:
        try:
            old.unlink()
            log("Cleaned iCloud: {}".format(old.name))
        except OSError:
            pass


def analyze(db_path: Path) -> None:
    """Run analysis on the exported database and write a report."""
    now = datetime.now()
    report_file = REPORTS_DIR / now.strftime("%Y-%m-%d_%H%M_analysis.txt")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    lines = []  # type: list[str]

    def out(msg: str) -> None:
        lines.append(msg)
        log(msg)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        out("Rune Analysis -- {}".format(now.strftime("%Y-%m-%d %H:%M")))
        out("Source: {}".format(db_path.name))
        out("")

        # --- Table counts ---
        out("== Data Summary ==")
        total_size = db_path.stat().st_size
        if total_size < 1_048_576:
            out("Database size: {:.1f} KB".format(total_size / 1024))
        else:
            out("Database size: {:.1f} MB".format(total_size / 1_048_576))

        for table in ("sensor_readings", "trips", "fillups", "health_scores", "can_frames"):
            try:
                row = conn.execute("SELECT COUNT(*) as c FROM {}".format(table)).fetchone()
                count = row["c"] if row else 0
                out("  {}: {:,} rows".format(table, count))
            except sqlite3.OperationalError:
                out("  {}: (table not found)".format(table))

        # --- Time range ---
        ts_range = conn.execute(
            "SELECT MIN(ts) as first, MAX(ts) as last FROM sensor_readings"
        ).fetchone()
        if ts_range and ts_range["first"]:
            first = datetime.fromtimestamp(ts_range["first"] / 1000)
            last = datetime.fromtimestamp(ts_range["last"] / 1000)
            duration = last - first
            out("")
            out("Data range: {} to {}".format(
                first.strftime("%Y-%m-%d %H:%M"), last.strftime("%Y-%m-%d %H:%M")
            ))
            out("Duration: {}".format(duration))

        # --- Trips ---
        trips = conn.execute(
            "SELECT * FROM trips WHERE end_time IS NOT NULL ORDER BY start_time DESC LIMIT 10"
        ).fetchall()
        if trips:
            out("")
            out("== Recent Trips ({}) ==".format(len(trips)))
            total_miles = 0.0
            total_cost = 0.0
            for t in trips:
                ts = datetime.fromtimestamp(t["start_time"] / 1000)
                miles = t["distance_miles"] or 0
                cost = t["fuel_cost_usd"] or 0
                mpg = t["avg_mpg"]
                mpg_str = "{:.1f} MPG".format(mpg) if mpg else "N/A"
                out("  {} {:5.1f} mi  ${:.2f}  {}".format(
                    ts.strftime("%m/%d %H:%M"), miles, cost, mpg_str
                ))
                total_miles += miles
                total_cost += cost
            out("  Total: {:.1f} mi, ${:.2f}".format(total_miles, total_cost))

        # --- Battery voltage ---
        voltages = conn.execute(
            "SELECT battery_v FROM sensor_readings WHERE battery_v > 0 ORDER BY ts DESC LIMIT 500"
        ).fetchall()
        if voltages:
            vals = [v["battery_v"] for v in voltages]
            avg_v = sum(vals) / len(vals)
            min_v = min(vals)
            max_v = max(vals)
            out("")
            out("== Battery ==")
            out("  Average: {:.2f}V".format(avg_v))
            out("  Range: {:.2f}V - {:.2f}V".format(min_v, max_v))
            if min_v < 12.3:
                out("  WARNING: Min voltage {:.2f}V is below 12.3V threshold".format(min_v))

        # --- Fuel trims ---
        trims = conn.execute(
            "SELECT stft_pct, ltft_pct FROM sensor_readings "
            "WHERE ltft_pct IS NOT NULL ORDER BY ts DESC LIMIT 500"
        ).fetchall()
        if trims:
            stft_vals = [t["stft_pct"] for t in trims if t["stft_pct"] is not None]
            ltft_vals = [t["ltft_pct"] for t in trims if t["ltft_pct"] is not None]
            out("")
            out("== Fuel Trims (last {} readings) ==".format(len(trims)))
            if stft_vals:
                out("  STFT avg: {:+.1f}%  range: {:+.1f}% to {:+.1f}%".format(
                    sum(stft_vals) / len(stft_vals), min(stft_vals), max(stft_vals)
                ))
            if ltft_vals:
                avg_ltft = sum(ltft_vals) / len(ltft_vals)
                out("  LTFT avg: {:+.1f}%  range: {:+.1f}% to {:+.1f}%".format(
                    avg_ltft, min(ltft_vals), max(ltft_vals)
                ))
                if abs(avg_ltft) > 10:
                    out("  WARNING: LTFT {:+.1f}% is outside normal range (+-10%)".format(avg_ltft))

        # --- Warmup tracking (oil dilution risk for L15BE) ---
        warmup_trips = conn.execute(
            """SELECT trip_id, trip_stats FROM trips
               WHERE trip_stats IS NOT NULL AND end_time IS NOT NULL
               ORDER BY start_time DESC LIMIT 20"""
        ).fetchall()
        if warmup_trips:
            short_warmups = 0
            for t in warmup_trips:
                try:
                    stats = json.loads(t["trip_stats"]) if isinstance(t["trip_stats"], str) else t["trip_stats"]
                    if stats and stats.get("warmup_completed") is False:
                        short_warmups += 1
                except (json.JSONDecodeError, TypeError):
                    pass
            if short_warmups > 0:
                pct = short_warmups / len(warmup_trips) * 100
                out("")
                out("== Warmup ==")
                out("  {}/{} trips ended before full warmup ({:.0f}%)".format(
                    short_warmups, len(warmup_trips), pct
                ))
                if pct > 50:
                    out("  NOTE: Most trips are short cold runs. Oil dilution risk for the 1.5T.")
                    out("  Consider a longer drive to let the engine reach full operating temp.")

        # --- CAN frame analysis ---
        try:
            can_count_row = conn.execute("SELECT COUNT(*) as c FROM can_frames").fetchone()
            can_count = can_count_row["c"] if can_count_row else 0
        except sqlite3.OperationalError:
            can_count = 0

        if can_count > 0:
            unique_ids = conn.execute("SELECT COUNT(DISTINCT can_id) as c FROM can_frames").fetchone()
            out("")
            out("== Raw CAN Bus ==")
            out("  Total frames: {:,}".format(can_count))
            out("  Unique CAN IDs: {}".format(unique_ids["c"]))

            top_ids = conn.execute(
                "SELECT can_id, COUNT(*) as cnt FROM can_frames "
                "GROUP BY can_id ORDER BY cnt DESC LIMIT 15"
            ).fetchall()
            if top_ids:
                out("  Top IDs:")
                for r in top_ids:
                    cid = r["can_id"]
                    label = _can_id_label(cid)
                    out("    0x{:03X} ({:>4d}) -- {:>8,} frames  {}".format(
                        cid, cid, r["cnt"], label
                    ))

        conn.close()

    except Exception as e:
        out("Analysis error: {}".format(e))

    # Write report file
    report_file.write_text("\n".join(lines) + "\n")
    log("Report: {}".format(report_file.relative_to(RUNE_DIR)))


def _can_id_label(can_id: int) -> str:
    """Known Honda Accord CAN ID labels from opendbc."""
    labels = {
        0x17C: "STEERING_TORQUE",
        0x14A: "STEERING_ANGLE",
        0x1D0: "WHEEL_SPEEDS",
        0x320: "ENGINE_STATUS (VTEC)",
        0x324: "ENGINE_DATA (fuel counter, coolant)",
        0x405: "DOORS_STATUS",
        0x1A6: "BRAKE_PRESSURE",
        0x1B0: "VEHICLE_SPEED_ALT",
        0x294: "GEAR_POSITION",
    }
    return labels.get(can_id, "")


def main() -> None:
    """Entry point: find newest DB, organize, analyze, clean up."""
    for d in [DATA_DIR, REPORTS_DIR, LOG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    log("=" * 50)
    log("Rune watcher triggered")

    newest = find_newest_db()
    if newest is None:
        log("No .db files in {}".format(ICLOUD_RUNE_DATA))
        return

    size = newest.stat().st_size
    if size < 1_048_576:
        size_str = "{:.1f} KB".format(size / 1024)
    else:
        size_str = "{:.1f} MB".format(size / 1_048_576)
    log("Found: {} ({})".format(newest.name, size_str))

    dest = organize_and_copy(newest)
    if dest is None:
        log("Already processed, skipping")
        return

    analyze(dest)
    cleanup_icloud(keep=3)
    log("Done")
    log("=" * 50 + "\n")


if __name__ == "__main__":
    main()
