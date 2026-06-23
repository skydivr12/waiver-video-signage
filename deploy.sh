#!/bin/bash

# =============================================================================
# Waiver Video Signage System — Full Deployment Script
# =============================================================================
#
# Run this on a fresh Raspberry Pi OS Lite (Bookworm) installation.
# It will install all dependencies, clone the repo, create the directory
# structure, install services and udev rules, and start everything up.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/skydivr12/waiver-video-signage/development/deploy.sh | sudo bash
#
#   or if you already have the file:
#   chmod +x deploy.sh && sudo ./deploy.sh
#
# Requirements:
#   - Raspberry Pi OS Lite (Bookworm / Debian 12)
#   - Internet connection (only needed during deployment)
#   - Run as root (sudo)
#
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

REPO_URL="https://github.com/skydivr12/waiver-video-signage"
REPO_BRANCH="development"
REPO_DIR="/tmp/waiver-video-signage"

INSTALL_ROOT="/opt/signage"
SCRIPTS_DIR="$INSTALL_ROOT/scripts"
USB_MOUNT="/mnt/signage_update"

SERVICE_USER="pi"
SERVICE_GROUP="pi"

# -----------------------------------------------------------------------------
# Colour helpers
# -----------------------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
success() { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
header()  { echo -e "\n${BOLD}--- $1 ---${NC}"; }

# -----------------------------------------------------------------------------
# Must be run as root
# -----------------------------------------------------------------------------

if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root. Try: sudo ./deploy.sh"
fi

# Verify the pi user exists (standard on Pi OS; warn if not)
if ! id "$SERVICE_USER" &>/dev/null; then
    warn "User '$SERVICE_USER' does not exist."
    warn "If your Pi user is named differently, edit SERVICE_USER at the top of this script."
fi

echo ""
echo -e "${BOLD}=============================================${NC}"
echo -e "${BOLD}  Waiver Video Signage — Deployment Script  ${NC}"
echo -e "${BOLD}=============================================${NC}"
echo ""
info "Repo:   $REPO_URL"
info "Branch: $REPO_BRANCH"
info "Target: $INSTALL_ROOT"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Update package lists
# -----------------------------------------------------------------------------

header "Step 1: Updating package lists"
apt-get update -q
success "Package lists updated"

# -----------------------------------------------------------------------------
# Step 2: Install all required packages
# -----------------------------------------------------------------------------

header "Step 2: Installing packages"

PACKAGES=(
    # Git — needed to clone the repo
    git

    # Media player — primary slideshow and video playback engine
    vlc
    vlc-plugin-base

    # Image processing — normalises images during USB content updates
    imagemagick

    # Video processing — re-encodes videos to consistent frame rate on update
    ffmpeg

    # exFAT filesystem — allows mounting USB drives formatted on Windows/Mac
    exfat-fuse
    exfatprogs

    # IPC utility — useful for manual debugging of the Unix socket interface
    socat

    # Python GPIO — button and LED control
    python3-gpiozero
    python3-lgpio

    # Python package manager — for any future extras
    python3-pip
)

apt-get install -y "${PACKAGES[@]}"
success "All packages installed"

# -----------------------------------------------------------------------------
# Step 3: Verify critical binaries
# -----------------------------------------------------------------------------

header "Step 3: Verifying binaries"

BINARIES=(
    "git:Git"
    "cvlc:VLC (headless)"
    "convert:ImageMagick"
    "ffmpeg:FFmpeg"
    "ffprobe:FFprobe"
    "python3:Python 3"
)

for entry in "${BINARIES[@]}"; do
    bin="${entry%%:*}"
    name="${entry##*:}"
    if command -v "$bin" &>/dev/null; then
        version=$(${bin} --version 2>&1 | head -1)
        success "$name: $version"
    else
        error "$name ($bin) not found after installation — cannot continue"
    fi
done

# -----------------------------------------------------------------------------
# Step 4: Clone the repository
# -----------------------------------------------------------------------------

header "Step 4: Cloning repository"

if [ -d "$REPO_DIR" ]; then
    info "Removing existing clone at $REPO_DIR"
    rm -rf "$REPO_DIR"
fi

git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$REPO_DIR"
success "Repository cloned to $REPO_DIR"

# -----------------------------------------------------------------------------
# Step 5: Create directory structure
# -----------------------------------------------------------------------------

header "Step 5: Creating directory structure"

DIRS=(
    "$INSTALL_ROOT/ads"        # Ad images and videos shown in the slideshow loop
    "$INSTALL_ROOT/showcase"   # Showcase images shown between ad cycles
    "$INSTALL_ROOT/videos"     # Instructional video played on button press
    "$INSTALL_ROOT/scripts"    # Python source files
    "$INSTALL_ROOT/logs"       # Rotating log files
    "$INSTALL_ROOT/config"     # Playlist and content version files
    "$INSTALL_ROOT/backups"    # Timestamped content backups created on each USB update
    "$INSTALL_ROOT/staging"    # Temporary staging area during USB content updates
    "$INSTALL_ROOT/deploy"     # Service and udev source files (from repo)
    "$USB_MOUNT"               # Mount point for exFAT USB update drives
)

for dir in "${DIRS[@]}"; do
    mkdir -p "$dir"
    success "Directory ready: $dir"
done

# Set ownership of the signage tree to the pi user so the service
# can read/write logs, config, and content without running as root
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT"
# The USB mount point is used by the update service which runs as root,
# so leave that owned by root
chown root:root "$USB_MOUNT"

success "Ownership set: $INSTALL_ROOT → $SERVICE_USER:$SERVICE_GROUP"

# -----------------------------------------------------------------------------
# Step 6: Install Python scripts
# -----------------------------------------------------------------------------

header "Step 6: Installing Python scripts"

SCRIPTS=(
    "signage.py"
    "button.py"
    "led.py"
    "ipc.py"
    "logger.py"
    "config.py"
    "content_manager.py"
    "usb_update.py"
    "mpv_controller.py"
)

for script in "${SCRIPTS[@]}"; do
    src="$REPO_DIR/scripts/$script"
    dst="$SCRIPTS_DIR/$script"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        chown "$SERVICE_USER:$SERVICE_GROUP" "$dst"
        success "Installed: $dst"
    else
        warn "Script not found in repo: $src — skipping"
    fi
done

# Copy any test scripts that exist alongside the main scripts
for testfile in "$REPO_DIR"/scripts/test_*.py; do
    [ -f "$testfile" ] || continue
    cp "$testfile" "$SCRIPTS_DIR/"
    chown "$SERVICE_USER:$SERVICE_GROUP" "$SCRIPTS_DIR/$(basename $testfile)"
    success "Installed test script: $(basename $testfile)"
done

# Copy deploy files (services, udev rules, docs) from repo
if [ -d "$REPO_DIR/deploy" ]; then
    cp -r "$REPO_DIR/deploy" "$INSTALL_ROOT/"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT/deploy"
    success "Installed deploy files"
fi

if [ -f "$REPO_DIR/README.md" ]; then
    cp "$REPO_DIR/README.md" "$INSTALL_ROOT/README.md"
    chown "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT/README.md"
    success "Installed README.md"
fi

if [ -d "$REPO_DIR/docs" ]; then
    cp -r "$REPO_DIR/docs" "$INSTALL_ROOT/"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT/docs"
    success "Installed docs"
fi

# -----------------------------------------------------------------------------
# Step 7: Install systemd service files
# -----------------------------------------------------------------------------

header "Step 7: Installing systemd services"

SERVICES=(
    "signage.service"
    "signage-update.service"
    "button.service"
)

for service in "${SERVICES[@]}"; do
    src="$INSTALL_ROOT/deploy/systemd/$service"
    dst="/etc/systemd/system/$service"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        chmod 644 "$dst"
        success "Installed service: $dst"
    else
        warn "Service file not found: $src — skipping"
    fi
done

# Reload systemd so it picks up the new service files
systemctl daemon-reload
success "systemd daemon reloaded"

# Enable services to start on boot
systemctl enable signage.service
success "Enabled: signage.service"

systemctl enable button.service
success "Enabled: button.service"

# signage-update is triggered by udev, not started at boot
# so we enable it but don't start it here
systemctl enable signage-update.service
success "Enabled: signage-update.service (triggered by udev)"

# -----------------------------------------------------------------------------
# Step 8: Install udev rules
# -----------------------------------------------------------------------------

header "Step 8: Installing udev rules"

UDEV_SRC="$INSTALL_ROOT/deploy/udev/99-signage-update.rules"
UDEV_DST="/etc/udev/rules.d/99-signage-update.rules"

if [ -f "$UDEV_SRC" ]; then
    cp "$UDEV_SRC" "$UDEV_DST"
    chmod 644 "$UDEV_DST"
    # Reload udev rules so they take effect immediately without a reboot
    udevadm control --reload-rules
    udevadm trigger
    success "Installed udev rules: $UDEV_DST"
else
    warn "udev rules file not found: $UDEV_SRC — USB auto-update will not work"
fi

# -----------------------------------------------------------------------------
# Step 9: Check ImageMagick security policy
# -----------------------------------------------------------------------------

header "Step 9: Checking ImageMagick policy"

# Debian ships with an overly restrictive ImageMagick policy that blocks
# reading some formats. This patches it to allow the formats we need.
POLICY_FILE="/etc/ImageMagick-6/policy.xml"

if [ -f "$POLICY_FILE" ]; then
    # Replace rights="none" with rights="read|write" for PDF and PS patterns
    # which are often blocked by default and can affect JPEG processing indirectly
    sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS"/rights="read|write" pattern="PS"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS2"/rights="read|write" pattern="PS2"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS3"/rights="read|write" pattern="PS3"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="EPS"/rights="read|write" pattern="EPS"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="XPS"/rights="read|write" pattern="XPS"/g' "$POLICY_FILE"
    success "ImageMagick policy updated"
else
    warn "ImageMagick policy file not found at $POLICY_FILE"
fi

# -----------------------------------------------------------------------------
# Step 10: Verify Python libraries
# -----------------------------------------------------------------------------

header "Step 10: Verifying Python libraries"

PYTHON_LIBS=(
    "gpiozero:gpiozero (GPIO control)"
    "lgpio:lgpio (GPIO backend)"
)

for entry in "${PYTHON_LIBS[@]}"; do
    lib="${entry%%:*}"
    name="${entry##*:}"
    if python3 -c "import ${lib}" 2>/dev/null; then
        success "Python: $name"
    else
        warn "Python library not importable: $name — GPIO features may not work"
    fi
done

# -----------------------------------------------------------------------------
# Step 11: Clean up
# -----------------------------------------------------------------------------

header "Step 11: Cleaning up"

rm -rf "$REPO_DIR"
success "Removed temporary clone: $REPO_DIR"

# -----------------------------------------------------------------------------
# Step 12: Start services
# -----------------------------------------------------------------------------

header "Step 12: Starting services"

info "Starting signage.service..."
systemctl start signage.service
sleep 2

if systemctl is-active --quiet signage.service; then
    success "signage.service is running"
else
    warn "signage.service did not start — this is expected if no content is installed yet"
    warn "Check status with: sudo systemctl status signage.service"
fi

info "Starting button.service..."
systemctl start button.service || warn "button.service did not start — GPIO may not be available yet"

if systemctl is-active --quiet button.service; then
    success "button.service is running"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

echo ""
echo -e "${BOLD}=============================================${NC}"
echo -e "${BOLD}  Deployment Complete${NC}"
echo -e "${BOLD}=============================================${NC}"
echo ""
echo -e "  Signage root:     ${BLUE}$INSTALL_ROOT${NC}"
echo -e "  Scripts:          ${BLUE}$SCRIPTS_DIR${NC}"
echo -e "  Logs:             ${BLUE}$INSTALL_ROOT/logs${NC}"
echo -e "  USB mount point:  ${BLUE}$USB_MOUNT${NC}"
echo ""
echo -e "  Services installed and enabled:"
echo -e "    ${GREEN}✓${NC} signage.service        (main display loop)"
echo -e "    ${GREEN}✓${NC} button.service         (physical button handler)"
echo -e "    ${GREEN}✓${NC} signage-update.service (triggered by USB insertion)"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo -e "  1. Prepare a USB drive with content (see README.md)"
echo -e "     The drive must be formatted as exFAT and contain:"
echo -e "       SIGNAGE_UPDATE.KEY   (with text: WAIVER_VIDEO_SIGNAGE_V1)"
echo -e "       content_version.json"
echo -e "       ads/                 (at least 1 image or video)"
echo -e "       showcase/            (optional showcase images)"
echo -e "       videos/              (exactly 1 instructional video)"
echo ""
echo -e "  2. Insert the USB drive — the update runs automatically"
echo ""
echo -e "  3. Monitor logs:"
echo -e "       tail -f $INSTALL_ROOT/logs/signage.log"
echo ""

exit 0
