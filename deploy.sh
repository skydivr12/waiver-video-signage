#!/bin/bash

# =============================================================================
# Waiver Video Signage System — Deploy / Update Script
# =============================================================================
#
# Works for both fresh installs and software updates — run the same command
# either way. The script detects which mode it is in automatically.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/skydivr12/waiver-video-signage/master/deploy.sh | sudo bash
#
#   or if you already have the file:
#   chmod +x deploy.sh && sudo ./deploy.sh
#
# Requirements:
#   - Raspberry Pi OS Lite (Bookworm / Debian 12 or newer)
#   - Internet connection (only needed during deployment)
#   - Run as root (sudo)
#
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

REPO_URL="https://github.com/skydivr12/waiver-video-signage"
REPO_BRANCH="master"
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

if ! id "$SERVICE_USER" &>/dev/null; then
    warn "User '$SERVICE_USER' does not exist."
    warn "If your Pi user is named differently, edit SERVICE_USER at the top of this script."
fi

# -----------------------------------------------------------------------------
# Detect fresh install vs update
# -----------------------------------------------------------------------------

IS_UPDATE=false
if [ -f "/etc/systemd/system/signage.service" ]; then
    IS_UPDATE=true
fi

echo ""
echo -e "${BOLD}=============================================${NC}"
if [ "$IS_UPDATE" = true ]; then
    echo -e "${BOLD}  Waiver Video Signage — Software Update     ${NC}"
else
    echo -e "${BOLD}  Waiver Video Signage — Fresh Install       ${NC}"
fi
echo -e "${BOLD}=============================================${NC}"
echo ""
info "Mode:   $([ "$IS_UPDATE" = true ] && echo 'UPDATE (existing installation found)' || echo 'FRESH INSTALL')"
info "Repo:   $REPO_URL"
info "Branch: $REPO_BRANCH"
info "Target: $INSTALL_ROOT"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Stop running services (update mode only)
# -----------------------------------------------------------------------------

if [ "$IS_UPDATE" = true ]; then
    header "Step 1: Stopping services for update"
    systemctl stop signage.service 2>/dev/null && success "Stopped signage.service" || info "signage.service was not running"
    systemctl stop button.service  2>/dev/null && success "Stopped button.service"  || info "button.service was not running"
else
    header "Step 1: Pre-flight check"
    success "Fresh install — no services to stop"
fi

# -----------------------------------------------------------------------------
# Step 2: Update package lists
# -----------------------------------------------------------------------------

header "Step 2: Updating package lists"
apt-get update -q
success "Package lists updated"

# -----------------------------------------------------------------------------
# Step 3: Install all required packages
# -----------------------------------------------------------------------------

header "Step 3: Installing packages"

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
# Step 4: Verify critical binaries
# -----------------------------------------------------------------------------

header "Step 4: Verifying binaries"

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
# Step 5: Clone the repository
# -----------------------------------------------------------------------------

header "Step 5: Cloning repository"

if [ -d "$REPO_DIR" ]; then
    info "Removing existing clone at $REPO_DIR"
    rm -rf "$REPO_DIR"
fi

git clone --branch "$REPO_BRANCH" --depth 1 "$REPO_URL" "$REPO_DIR"
success "Repository cloned to $REPO_DIR"

# -----------------------------------------------------------------------------
# Step 6: Create directory structure
# -----------------------------------------------------------------------------

header "Step 6: Creating directory structure"

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

chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT"
chown root:root "$USB_MOUNT"
success "Ownership set: $INSTALL_ROOT → $SERVICE_USER:$SERVICE_GROUP"

# -----------------------------------------------------------------------------
# Step 7: Install Python scripts
# -----------------------------------------------------------------------------

header "Step 7: Installing Python scripts"

SCRIPTS=(
    "signage.py"
    "button.py"
    "led.py"
    "ipc.py"
    "logger.py"
    "config.py"
    "content_manager.py"
    "usb_update.py"
    "prep_usb.py"
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

# Copy deploy files, docs, and README from repo
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
# Step 8: Install systemd service files
# -----------------------------------------------------------------------------

header "Step 8: Installing systemd services"

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

systemctl daemon-reload
success "systemd daemon reloaded"

systemctl enable signage.service
success "Enabled: signage.service"

systemctl enable button.service
success "Enabled: button.service"

systemctl enable signage-update.service
success "Enabled: signage-update.service (triggered by udev)"

# -----------------------------------------------------------------------------
# Step 9: Install udev rules
# -----------------------------------------------------------------------------

header "Step 9: Installing udev rules"

UDEV_SRC="$INSTALL_ROOT/deploy/udev/99-signage-update.rules"
UDEV_DST="/etc/udev/rules.d/99-signage-update.rules"

if [ -f "$UDEV_SRC" ]; then
    cp "$UDEV_SRC" "$UDEV_DST"
    chmod 644 "$UDEV_DST"
    udevadm control --reload-rules
    udevadm trigger
    success "Installed udev rules: $UDEV_DST"
else
    warn "udev rules file not found: $UDEV_SRC — USB auto-update will not work"
fi

# -----------------------------------------------------------------------------
# Step 10: Check ImageMagick security policy
# -----------------------------------------------------------------------------

header "Step 10: Checking ImageMagick policy"

POLICY_FILE="/etc/ImageMagick-6/policy.xml"

if [ -f "$POLICY_FILE" ]; then
    sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS"/rights="read|write" pattern="PS"/g'   "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS2"/rights="read|write" pattern="PS2"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS3"/rights="read|write" pattern="PS3"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="EPS"/rights="read|write" pattern="EPS"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="XPS"/rights="read|write" pattern="XPS"/g' "$POLICY_FILE"
    success "ImageMagick policy updated"
else
    warn "ImageMagick policy file not found at $POLICY_FILE"
fi

# -----------------------------------------------------------------------------
# Step 11: Verify Python libraries
# -----------------------------------------------------------------------------

header "Step 11: Verifying Python libraries"

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
# Step 12: Display hardening — fresh install only, skip if already applied
# -----------------------------------------------------------------------------

header "Step 12: Display hardening"

CMDLINE_FILE="/boot/firmware/cmdline.txt"

if [ "$IS_UPDATE" = true ]; then
    info "Update mode — skipping display hardening (already applied on install)"
elif [ ! -f "$CMDLINE_FILE" ]; then
    warn "$CMDLINE_FILE not found — skipping (not running on a Pi?)"
elif grep -q "console=tty3" "$CMDLINE_FILE"; then
    info "Display hardening already applied — skipping"
else
    cp "$CMDLINE_FILE" "${CMDLINE_FILE}.bak"
    success "Backed up cmdline.txt to ${CMDLINE_FILE}.bak"

    CURRENT="$(cat "$CMDLINE_FILE")"
    CURRENT="$(echo "$CURRENT" | sed \
        -e 's/console=tty[0-9][^ ]*//g' \
        -e 's/quiet//g' \
        -e 's/loglevel=[^ ]*//g' \
        -e 's/logo\.nologo//g' \
        -e 's/vt\.global_cursor_default=[^ ]*//g' \
        -e 's/  */ /g' \
        -e 's/^ //;s/ $//')"

    NEW="$CURRENT console=tty3 quiet loglevel=0 logo.nologo vt.global_cursor_default=0"
    printf '%s\n' "$NEW" > "$CMDLINE_FILE"
    success "Updated $CMDLINE_FILE"

    systemctl disable getty@tty1.service
    success "Disabled getty@tty1.service"

    systemctl mask getty@tty1
    success "Masked getty@tty1"
fi

# -----------------------------------------------------------------------------
# Step 13: Clean up
# -----------------------------------------------------------------------------

header "Step 13: Cleaning up"

rm -rf "$REPO_DIR"
success "Removed temporary clone: $REPO_DIR"

# -----------------------------------------------------------------------------
# Step 14: Check for media content
# -----------------------------------------------------------------------------

header "Step 14: Checking for media content"

has_ads=false
has_video=false

for f in "$INSTALL_ROOT/ads/"*; do
    [ -f "$f" ] && has_ads=true && break
done

for f in "$INSTALL_ROOT/videos/"*; do
    [ -f "$f" ] && has_video=true && break
done

MEDIA_READY=true

if [ "$has_ads" = false ] || [ "$has_video" = false ]; then
    MEDIA_READY=false
    echo ""
    echo -e "  ${YELLOW}No media content found.${NC}"
    [ "$has_ads"   = false ] && warn "  ads/ folder is empty — needs at least 1 image or video"
    [ "$has_video" = false ] && warn "  videos/ folder is empty — needs exactly 1 instructional video"
    echo ""
    echo -e "  To load content, prepare a USB drive formatted as exFAT containing:"
    echo -e "    ${BLUE}SIGNAGE_UPDATE.KEY${NC}   (containing the text: WAIVER_VIDEO_SIGNAGE_V1)"
    echo -e "    ${BLUE}content_version.json${NC}"
    echo -e "    ${BLUE}ads/${NC}                 (at least 1 image or video)"
    echo -e "    ${BLUE}showcase/${NC}            (optional)"
    echo -e "    ${BLUE}videos/${NC}              (exactly 1 instructional video)"
    echo ""
    echo -e "  Insert the USB drive after the services start — the update runs automatically."
    echo ""

    # Prompt only if stdin is a terminal (not piped from curl)
    START_SERVICES="y"
    if [ -t 0 ]; then
        read -r -p "  Start services now anyway and wait for content? [Y/n]: " START_SERVICES
        START_SERVICES="${START_SERVICES:-y}"
    else
        info "Non-interactive mode — services will be started and will wait for content"
    fi
else
    success "ads/ has content"
    success "videos/ has content"
    START_SERVICES="y"
fi

# -----------------------------------------------------------------------------
# Step 15: Start / restart services
# -----------------------------------------------------------------------------

header "Step 15: $([ "$IS_UPDATE" = true ] && echo 'Restarting' || echo 'Starting') services"

case "${START_SERVICES,,}" in
    y|yes|"")
        if [ "$IS_UPDATE" = true ]; then
            info "Restarting signage.service..."
            systemctl restart --no-block signage.service
            success "signage.service restarted"

            info "Restarting button.service..."
            systemctl restart button.service || warn "button.service did not restart"
        else
            info "Starting signage.service (non-blocking — will wait for content)..."
            systemctl start --no-block signage.service
            success "signage.service start queued"

            info "Starting button.service..."
            systemctl start button.service || warn "button.service did not start"
        fi

        sleep 2
        if systemctl is-active --quiet button.service; then
            success "button.service is running"
        else
            warn "button.service is not active — check: sudo journalctl -u button.service -n 20"
        fi
        ;;
    *)
        warn "Services not started. Start them manually when ready:"
        warn "  sudo systemctl start signage.service button.service"
        ;;
esac

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

echo ""
echo -e "${BOLD}=============================================${NC}"
echo -e "${BOLD}  $([ "$IS_UPDATE" = true ] && echo 'Update' || echo 'Deployment') Complete${NC}"
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

if [ "$MEDIA_READY" = false ]; then
    echo -e "  ${YELLOW}Next step: load media via USB drive (see instructions above)${NC}"
else
    echo -e "  ${GREEN}Media content present — system should be running${NC}"
fi

echo ""
echo -e "  Monitor logs:"
echo -e "    tail -f $INSTALL_ROOT/logs/signage.log"
echo ""

exit 0
