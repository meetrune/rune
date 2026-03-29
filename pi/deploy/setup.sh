#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# Rune -- Raspberry Pi 4B deployment setup
# Target: Raspberry Pi OS Trixie (Debian 13) 64-bit Lite
# Run once on a fresh Pi. Requires root.
# ──────────────────────────────────────────────────
set -euo pipefail

RUNE_DIR="/opt/rune"
DATA_DIR="/var/lib/rune"
CONFIG_DIR="/etc/rune"
RUNE_USER="rune"
WIFI_SSID="Rune"
WIFI_PASS=""  # set below or pass as argument

# ── Parse arguments ──────────────────────────────
usage() {
    echo "Usage: sudo $0 --wifi-pass <passphrase> [--wican-mac <mac>] [--pixel-mac <mac>]"
    echo ""
    echo "  --wifi-pass   WPA2 passphrase for the Rune WiFi network (required, 8+ chars)"
    echo "  --wican-mac   MAC address of WiCAN Pro (optional, for static DHCP lease)"
    echo "  --pixel-mac   MAC address of Pixel 6 Pro (optional, for static DHCP lease)"
    exit 1
}

WICAN_MAC=""
PIXEL_MAC=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wifi-pass) WIFI_PASS="$2"; shift 2 ;;
        --wican-mac) WICAN_MAC="$2"; shift 2 ;;
        --pixel-mac) PIXEL_MAC="$2"; shift 2 ;;
        *) usage ;;
    esac
done

if [[ -z "$WIFI_PASS" ]]; then
    echo "ERROR: --wifi-pass is required."
    usage
fi

if [[ ${#WIFI_PASS} -lt 8 ]]; then
    echo "ERROR: WiFi passphrase must be at least 8 characters."
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: Must run as root (sudo)."
    exit 1
fi

echo "═══════════════════════════════════════════════"
echo "  Rune -- Pi 4B Deployment Setup"
echo "═══════════════════════════════════════════════"
echo ""

# ── 1. System packages ───────────────────────────
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git avahi-daemon sqlite3

# mDNS: set hostname to "rune" so MacBook can reach us at rune.local
hostnamectl set-hostname rune
echo "  mDNS configured: rune.local"

# ── 2. Create rune user ──────────────────────────
echo "[2/7] Creating rune user..."
if ! id "$RUNE_USER" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "$RUNE_DIR" "$RUNE_USER"
    echo "  Created system user: $RUNE_USER"
else
    echo "  User $RUNE_USER already exists, skipping."
fi

# ── 3. Set up directories ────────────────────────
echo "[3/7] Setting up directories..."
mkdir -p "$RUNE_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$CONFIG_DIR"

chown "$RUNE_USER:$RUNE_USER" "$DATA_DIR"
chmod 750 "$DATA_DIR"

# Allow rune user to call shutdown without password (for thermal shutdown)
echo "rune ALL=(root) NOPASSWD: /sbin/shutdown" > /etc/sudoers.d/rune-shutdown
chmod 440 /etc/sudoers.d/rune-shutdown
echo "  Sudoers entry added for thermal shutdown."

# ── 4. Deploy application ────────────────────────
echo "[4/7] Deploying application..."
# Copy backend + built frontend
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script is at repo/pi/deploy/ -- go up two levels to reach repo root
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Copy backend source (from pi/backend/)
rsync -a --delete "$REPO_DIR/pi/backend/" "$RUNE_DIR/backend/"

# Copy diagnostics dashboard (from pi/diagnostics/)
rsync -a --delete "$REPO_DIR/pi/diagnostics/" "$RUNE_DIR/diagnostics/"
echo "  Diagnostics dashboard copied."

# Copy built frontend (must run `npm run build` in pixel/frontend/ first)
if [[ -d "$REPO_DIR/pixel/frontend/dist" ]]; then
    rsync -a --delete "$REPO_DIR/pixel/frontend/dist/" "$RUNE_DIR/frontend/dist/"
    echo "  Frontend dist copied."
else
    echo "  WARNING: pixel/frontend/dist not found. Run 'cd pixel/frontend && npm run build' first."
fi

# Copy frontend public assets (3D model, icons)
if [[ -d "$REPO_DIR/pixel/frontend/public" ]]; then
    rsync -a "$REPO_DIR/pixel/frontend/public/" "$RUNE_DIR/frontend/public/"
fi

# Copy pyproject.toml for dependency installation
cp "$REPO_DIR/pyproject.toml" "$RUNE_DIR/"

# Create venv and install dependencies
if [[ ! -d "$RUNE_DIR/.venv" ]]; then
    python3 -m venv "$RUNE_DIR/.venv"
    echo "  Created Python venv."
fi
"$RUNE_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$RUNE_DIR/.venv/bin/pip" install --quiet "$RUNE_DIR"

chown -R "$RUNE_USER:$RUNE_USER" "$RUNE_DIR"

# ── 5. Install systemd service ───────────────────
echo "[5/7] Installing systemd service..."
cp "$SCRIPT_DIR/rune.env" "$CONFIG_DIR/rune.env"
chmod 600 "$CONFIG_DIR/rune.env"

cp "$SCRIPT_DIR/rune.service" /etc/systemd/system/rune.service
systemctl daemon-reload
systemctl enable rune.service
echo "  Service installed and enabled."

# ── 6. WiFi Access Point ─────────────────────────
echo "[6/7] Configuring WiFi access point..."

# Create the AP connection via NetworkManager
# Delete existing if present (idempotent)
nmcli con delete Rune 2>/dev/null || true

nmcli con add \
    type wifi \
    ifname wlan0 \
    con-name Rune \
    ssid "$WIFI_SSID" \
    connection.autoconnect yes

nmcli con modify Rune \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    802-11-wireless.channel 6 \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.proto rsn \
    wifi-sec.pairwise ccmp \
    wifi-sec.psk "$WIFI_PASS" \
    ipv4.method shared \
    ipv4.addresses 192.168.4.1/24 \
    ipv6.method disabled

echo "  WiFi AP 'Rune' configured at 192.168.4.1"

# Static DHCP leases (if MAC addresses provided)
DHCP_CONF="/etc/NetworkManager/dnsmasq-shared.d/rune-leases.conf"
mkdir -p /etc/NetworkManager/dnsmasq-shared.d

cat > "$DHCP_CONF" <<DHCP_EOF
# Rune network DHCP configuration
# Dynamic range for unknown devices
dhcp-range=192.168.4.150,192.168.4.200,255.255.255.0,12h
DHCP_EOF

if [[ -n "$WICAN_MAC" ]]; then
    echo "dhcp-host=$WICAN_MAC,wican,192.168.4.100,infinite" >> "$DHCP_CONF"
    echo "  WiCAN Pro: $WICAN_MAC -> 192.168.4.100"
fi

if [[ -n "$PIXEL_MAC" ]]; then
    echo "dhcp-host=$PIXEL_MAC,pixel,192.168.4.50,infinite" >> "$DHCP_CONF"
    echo "  Pixel 6 Pro: $PIXEL_MAC -> 192.168.4.50"
fi

# Disable NAT masquerade (isolated car network, no internet)
cat > /etc/NetworkManager/dispatcher.d/99-rune-no-nat <<'NAT_EOF'
#!/bin/bash
# Rune: remove NAT masquerade -- isolated car network, no internet gateway
IFACE="$1"
ACTION="$2"
if [ "$IFACE" = "wlan0" ] && [ "$ACTION" = "up" ]; then
    nft delete rule ip nm-shared-wlan0 postrouting masquerade 2>/dev/null || true
    sysctl -qw net.ipv4.ip_forward=0
fi
NAT_EOF
chmod +x /etc/NetworkManager/dispatcher.d/99-rune-no-nat

# Trixie bug workaround: nmcli may write connection to /run/ instead of /etc/
# If so, the AP won't survive a reboot. Move it to the persistent location.
if [ -f "/run/NetworkManager/system-connections/Rune.nmconnection" ] && \
   [ ! -f "/etc/NetworkManager/system-connections/Rune.nmconnection" ]; then
    echo "  Fixing Trixie nmcli bug: moving connection to /etc/"
    cp /run/NetworkManager/system-connections/Rune.nmconnection \
       /etc/NetworkManager/system-connections/Rune.nmconnection
    chmod 600 /etc/NetworkManager/system-connections/Rune.nmconnection
    nmcli con reload
fi

# Bring up the AP
nmcli con up Rune || echo "  NOTE: WiFi AP will start on next boot."

# ── 7. OverlayFS (optional, enable manually) ─────
echo "[7/7] OverlayFS preparation..."

# Create the bind-mount unit so /var/lib/rune survives OverlayFS
cat > /etc/systemd/system/var-lib-rune.mount <<'OVERLAY_EOF'
[Unit]
Description=Bind mount /var/lib/rune to real SD card (bypasses overlayfs)
After=local-fs.target
ConditionPathExists=/ro/var/lib/rune

[Mount]
What=/ro/var/lib/rune
Where=/var/lib/rune
Type=none
Options=bind,rw

[Install]
WantedBy=multi-user.target
OVERLAY_EOF

systemctl daemon-reload
systemctl enable var-lib-rune.mount

echo ""
echo "═══════════════════════════════════════════════"
echo "  Setup complete."
echo "═══════════════════════════════════════════════"
echo ""
echo "  WiFi AP:     Rune (192.168.4.1)"
echo "  Backend:     systemctl start rune"
echo "  Database:    $DATA_DIR/rune.db"
echo "  Config:      $CONFIG_DIR/rune.env"
echo "  Logs:        journalctl -u rune -f"
echo ""
echo "  To enable OverlayFS (SD card write protection):"
echo "    sudo raspi-config  ->  Performance  ->  Overlay File System"
echo "    Then edit /etc/overlayroot.local.conf:"
echo "      overlayroot=\"tmpfs:recurse=0\""
echo "    Then: sudo update-initramfs -u && sudo reboot"
echo ""
echo "  The /var/lib/rune directory will stay writable"
echo "  through the bind-mount unit (already enabled)."
echo ""
echo "  Start Rune now:  sudo systemctl start rune"
echo "  View dashboard:  http://192.168.4.1:8080"
echo ""
