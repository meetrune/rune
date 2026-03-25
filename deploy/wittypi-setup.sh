#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# Witty Pi 4 setup for Rune
#
# Run AFTER setup.sh, with the Witty Pi 4 physically
# connected to the Pi's GPIO header.
#
# What this does:
#   1. Enables I2C (Witty Pi uses GPIO 2/3)
#   2. Installs Witty Pi 4 software from UUGear
#   3. Installs our custom shutdown hook
#   4. Configures low voltage threshold for car use
#
# Prerequisites:
#   - Witty Pi 4 connected to Pi GPIO header
#   - CR2032 battery installed in Witty Pi 4
#   - Pi connected to 12V via Witty Pi 4 input
# ──────────────────────────────────────────────────
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Must run as root (sudo)."
    exit 1
fi

echo "═══════════════════════════════════════════════"
echo "  Witty Pi 4 Setup for Rune"
echo "═══════════════════════════════════════════════"
echo ""

# ── 1. Enable I2C ─────────────────────────────────
echo "[1/4] Enabling I2C..."
raspi-config nonint do_i2c 0  # 0 = enable
echo "  I2C enabled on GPIO 2/3"

# Verify I2C
if ! command -v i2cdetect &>/dev/null; then
    apt-get install -y -qq i2c-tools
fi

echo "  Scanning I2C bus..."
i2cdetect -y 1 || true
echo "  (Witty Pi 4 should appear at address 0x08 and RTC at 0x68)"

# ── 2. Install Witty Pi 4 software ───────────────
echo "[2/4] Installing Witty Pi 4 software..."
WITTYPI_DIR="/opt/wittypi"

if [[ -d "$WITTYPI_DIR" ]]; then
    echo "  Witty Pi software already installed at $WITTYPI_DIR"
else
    # UUGear's official install script
    cd /tmp
    wget -q https://www.uugear.com/repo/WittyPi4/install.sh -O wittypi4-install.sh
    chmod +x wittypi4-install.sh

    echo "  Running UUGear install script..."
    echo "  (This installs to $WITTYPI_DIR and sets up the daemon)"
    bash wittypi4-install.sh
    rm -f wittypi4-install.sh
fi

# ── 3. Install Rune shutdown hook ─────────────────
echo "[3/4] Installing Rune shutdown hook..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/rune-shutdown.sh" /opt/rune/shutdown.sh
chmod +x /opt/rune/shutdown.sh

# Configure Witty Pi to call our shutdown hook.
# The Witty Pi daemon calls /opt/wittypi/beforeShutdown.sh
# before initiating shutdown. We hook into that.
BEFORE_SHUTDOWN="$WITTYPI_DIR/beforeShutdown.sh"
if [[ -f "$BEFORE_SHUTDOWN" ]]; then
    # Check if our hook is already installed
    if ! grep -q "rune" "$BEFORE_SHUTDOWN"; then
        echo "" >> "$BEFORE_SHUTDOWN"
        echo "# Rune: graceful backend shutdown before power off" >> "$BEFORE_SHUTDOWN"
        echo "/opt/rune/shutdown.sh" >> "$BEFORE_SHUTDOWN"
        echo "  Hooked into $BEFORE_SHUTDOWN"
    else
        echo "  Shutdown hook already installed in $BEFORE_SHUTDOWN"
    fi
else
    # Create the hook file if it doesn't exist
    cat > "$BEFORE_SHUTDOWN" <<'EOF'
#!/bin/bash
# Called by Witty Pi daemon before shutdown

# Rune: graceful backend shutdown before power off
/opt/rune/shutdown.sh
EOF
    chmod +x "$BEFORE_SHUTDOWN"
    echo "  Created $BEFORE_SHUTDOWN with Rune hook"
fi

# ── 4. Configure for car use ─────────────────────
echo "[4/4] Configuring Witty Pi registers for automotive use..."

# All config via I2C to the ATtiny841 MCU at address 0x08.
# Register map from firmware source (WittyPi4.ino):
#
#   Reg 1,2  = Vin (integer, decimal) -- read-only
#   Reg 3,4  = Vout (integer, decimal) -- read-only
#   Reg 5,6  = Iout (integer, decimal) -- read-only
#   Reg 7    = Temperature -- read-only (LM75B)
#   Reg 8    = LV_SHUTDOWN flag (1 = last shutdown was low-voltage)
#   Reg 17   = DEFAULT_ON (1 = auto-boot when power arrives)
#   Reg 19   = LOW_VOLTAGE threshold (value = volts * 10)
#   Reg 21   = POWER_CUT_DELAY (value * 0.1 = seconds after OS halt)
#   Reg 47   = DEFAULT_ON_DELAY (seconds to wait before booting)

# Register 17: AUTO-BOOT when 12V arrives
# The armrest 12V outlet is ignition-switched. When you start the car,
# 12V flows, the Witty Pi detects it, and boots the Pi automatically.
echo "  Setting auto-boot on power (reg 17 = 1)..."
i2cset -y 1 0x08 17 1

# Register 19: LOW VOLTAGE THRESHOLD = 9.0V
# Car voltages:
#   Running:      13.5-14.8V (alternator)
#   Ignition off: 0V (outlet is dead -- ignition-switched)
#   Cranking dip:  ~10V for 1-3 seconds
# Since our outlet goes to 0V on ignition off, ANY threshold works.
# We set 9.0V (value=90) as a safety net -- below cranking dip,
# so it won't false-trigger during engine start.
echo "  Setting low voltage threshold to 9.0V (reg 19 = 90)..."
i2cset -y 1 0x08 19 90

# Register 21: POWER CUT DELAY = 25 seconds after OS halt
# After the Pi shuts down (TxD pin goes low), the Witty Pi waits
# this many 0.1s units before cutting power. 250 = 25 seconds.
# This gives the filesystem time to fully sync.
echo "  Setting power cut delay to 25s (reg 21 = 250)..."
i2cset -y 1 0x08 21 250

# Register 47: STARTUP DELAY = 12 seconds
# Wait 12 seconds after 12V arrives before booting the Pi.
# This skips the cranking voltage dip (engine start takes 1-3s)
# and lets the alternator stabilize. By the time the Pi boots,
# the electrical system is stable.
echo "  Setting startup delay to 12s (reg 47 = 12)..."
i2cset -y 1 0x08 47 12

# Set over-temperature shutdown at 65C
# LM75B sensor is on the Witty Pi board (inside the armrest).
# Pi 4B throttles at 80C. 65C gives us a safety margin.
echo "  Setting over-temperature shutdown at 65C (via wittyPi.sh)..."
# Over-temp action is set via the interactive menu or schedule script.
# For now, we log a reminder. The exact register depends on firmware version.
echo "  NOTE: Run 'cd $WITTYPI_DIR && sudo ./wittyPi.sh' to set:"
echo "    Option 9 -> Over temperature action -> Shutdown at 65C"

# Verify the settings
echo ""
echo "  Verifying Witty Pi configuration..."
VIN_I=$(i2cget -y 1 0x08 1 2>/dev/null || echo "??")
VIN_D=$(i2cget -y 1 0x08 2 2>/dev/null || echo "??")
DEF_ON=$(i2cget -y 1 0x08 17 2>/dev/null || echo "??")
LV_THR=$(i2cget -y 1 0x08 19 2>/dev/null || echo "??")
PC_DLY=$(i2cget -y 1 0x08 21 2>/dev/null || echo "??")
ON_DLY=$(i2cget -y 1 0x08 47 2>/dev/null || echo "??")

echo "  ┌──────────────────────────────────────┐"
echo "  │ Witty Pi 4 -- Rune Configuration     │"
echo "  ├──────────────────────────────────────┤"
echo "  │ Input voltage:    ${VIN_I}.${VIN_D}V          │"
echo "  │ Auto-boot:        reg17=${DEF_ON} (1=yes)     │"
echo "  │ Low voltage:      reg19=${LV_THR} (9.0V)      │"
echo "  │ Power cut delay:  reg21=${PC_DLY} (25s)       │"
echo "  │ Startup delay:    reg47=${ON_DLY} (12s)       │"
echo "  └──────────────────────────────────────┘"

echo ""
echo "═══════════════════════════════════════════════"
echo "  Witty Pi 4 setup complete."
echo "═══════════════════════════════════════════════"
echo ""
echo "  What happens now:"
echo "  1. Turn ignition ON  -> 12V flows -> Witty Pi waits 12s"
echo "  2. After 12s delay   -> Pi boots -> systemd starts Rune"
echo "  3. Turn ignition OFF -> 0V at outlet -> below 9.0V threshold"
echo "  4. Witty Pi signals daemon -> beforeShutdown.sh runs"
echo "  5. Our hook: stops Rune, WAL checkpoint, filesystem sync"
echo "  6. Pi halts -> TxD goes low -> 25s delay -> power cut"
echo "  7. Standby: 0.5mA, RTC keeps time on CR2032"
echo ""
echo "  MANUAL TODO (run once, interactive):"
echo "    cd $WITTYPI_DIR && sudo ./wittyPi.sh"
echo "    -> Option 9: Set over-temperature shutdown at 65C"
echo "    -> Option 10: Set below-temperature no-boot at -20C"
echo ""
echo "  To verify voltage/temp readings:"
echo "    cd $WITTYPI_DIR && sudo ./wittyPi.sh"
echo "    (Shows Vin, Vout, Iout, temperature at the top)"
echo ""
echo "  To test shutdown: unplug the 12V input and watch:"
echo "    sudo journalctl -f -t rune-shutdown"
echo ""
