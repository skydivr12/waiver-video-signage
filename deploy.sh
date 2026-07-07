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
#   To deploy from a branch other than master, set REPO_BRANCH (this also
#   controls which branch's copy of deploy.sh you should fetch, so they match):
#   curl -fsSL https://raw.githubusercontent.com/skydivr12/waiver-video-signage/raspios-trixie/deploy.sh | sudo REPO_BRANCH=raspios-trixie bash
#
#   Note: the interactive USB drive setup (Step 6) and the wait-for-USB
#   prompt (Step 15) only run when this script has a real terminal attached.
#   Piping via curl | sudo bash does not — download the file first and run
#   it directly (chmod +x deploy.sh && sudo ./deploy.sh) to get those prompts.
#
# Requirements:
#   - Raspberry Pi OS Lite (Bookworm / Debian 12, or Trixie / Debian 13)
#   - Internet connection (only needed during deployment)
#   - Run as root (sudo)
#
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

REPO_URL="https://github.com/skydivr12/waiver-video-signage"
REPO_BRANCH="${REPO_BRANCH:-master}"
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
# Step 6: Prepare USB update drive (interactive only, does not block install)
# -----------------------------------------------------------------------------

header "Step 6: Prepare USB update drive"

if [ "$IS_UPDATE" = true ]; then
    info "Update mode — skipping USB drive setup prompt"
    info "Run any time: sudo python3 $SCRIPTS_DIR/prep_usb.py"
elif [ ! -t 0 ]; then
    info "Non-interactive install — skipping USB drive setup prompt"
    info "Prepare your USB drive manually, or run later: sudo python3 $SCRIPTS_DIR/prep_usb.py"
else
    echo ""
    echo -e "  A USB drive (exFAT) is how you load ad images, showcase images,"
    echo -e "  and the instructional video onto this signage box."
    echo ""
    echo -e "  Setting one up now costs a couple of minutes, but then you can load"
    echo -e "  your media onto it on another computer while the rest of this"
    echo -e "  install keeps running in the background."
    echo ""
    read -r -p "  Set up a USB update drive now? [Y/n]: " SETUP_USB
    SETUP_USB="${SETUP_USB:-y}"
    case "${SETUP_USB,,}" in
        y|yes)
            if python3 "$REPO_DIR/scripts/prep_usb.py"; then
                success "USB drive ready"
                echo ""
                echo -e "  ${YELLOW}Remove the drive now and load your content onto it:${NC}"
                echo -e "    ${BLUE}ads/${NC}                 at least 1 image or video"
                echo -e "    ${BLUE}showcase/${NC}            optional images"
                echo -e "    ${BLUE}videos/${NC}              exactly 1 instructional video"
                echo ""
                echo -e "  Keep the drive handy — the installer will ask you to insert it"
                echo -e "  again once services are ready to start, later in this run."
                echo ""
            else
                warn "USB drive setup did not complete — you can run it again any time with:"
                warn "  sudo python3 $SCRIPTS_DIR/prep_usb.py"
            fi
            ;;
        *)
            info "Skipping — run it manually any time with:"
            info "  sudo python3 $SCRIPTS_DIR/prep_usb.py"
            ;;
    esac
fi

# -----------------------------------------------------------------------------
# Step 7: Create directory structure
# -----------------------------------------------------------------------------

header "Step 7: Creating directory structure"

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

# Pre-create the shared log file now, before anything can create it as root
# (see Step 15) — otherwise whichever process opens it first "wins" the
# ownership, and signage.service/button.service (running as $SERVICE_USER)
# would get locked out of a root-owned file.
touch "$INSTALL_ROOT/logs/signage.log"

chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT"
chown root:root "$USB_MOUNT"
success "Ownership set: $INSTALL_ROOT → $SERVICE_USER:$SERVICE_GROUP"

# -----------------------------------------------------------------------------
# Step 8: Install Python scripts
# -----------------------------------------------------------------------------

header "Step 8: Installing Python scripts"

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
# Step 9: Install systemd service files
# -----------------------------------------------------------------------------

header "Step 9: Installing systemd services"

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
# Step 10: Install udev rules
# -----------------------------------------------------------------------------

header "Step 10: Installing udev rules"

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
# Step 11: Check ImageMagick security policy
# -----------------------------------------------------------------------------

header "Step 11: Checking ImageMagick policy"

# Bookworm/Debian 12 ships ImageMagick 6 (/etc/ImageMagick-6/policy.xml).
# Trixie/Debian 13 ships ImageMagick 7 (/etc/ImageMagick-7/policy.xml).
# Patch whichever one is actually present.
POLICY_CANDIDATES=(
    "/etc/ImageMagick-7/policy.xml"
    "/etc/ImageMagick-6/policy.xml"
)

POLICY_FILE=""
for candidate in "${POLICY_CANDIDATES[@]}"; do
    if [ -f "$candidate" ]; then
        POLICY_FILE="$candidate"
        break
    fi
done

if [ -n "$POLICY_FILE" ]; then
    sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS"/rights="read|write" pattern="PS"/g'   "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS2"/rights="read|write" pattern="PS2"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="PS3"/rights="read|write" pattern="PS3"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="EPS"/rights="read|write" pattern="EPS"/g' "$POLICY_FILE"
    sed -i 's/rights="none" pattern="XPS"/rights="read|write" pattern="XPS"/g' "$POLICY_FILE"
    success "ImageMagick policy updated ($POLICY_FILE)"
else
    warn "No ImageMagick policy file found (checked: ${POLICY_CANDIDATES[*]})"
fi

# -----------------------------------------------------------------------------
# Step 12: Verify Python libraries
# -----------------------------------------------------------------------------

header "Step 12: Verifying Python libraries"

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
# Step 13: Display hardening — fresh install only, skip if already applied
# -----------------------------------------------------------------------------

header "Step 13: Display hardening"

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
# Step 14: Clean up
# -----------------------------------------------------------------------------

header "Step 14: Cleaning up"

rm -rf "$REPO_DIR"
success "Removed temporary clone: $REPO_DIR"

# -----------------------------------------------------------------------------
# Step 15: Check for media content
# -----------------------------------------------------------------------------

header "Step 15: Checking for media content"

check_media_present() {
    has_ads=false
    has_video=false
    for f in "$INSTALL_ROOT/ads/"*; do
        if [ -f "$f" ]; then
            has_ads=true
            break
        fi
    done
    for f in "$INSTALL_ROOT/videos/"*; do
        if [ -f "$f" ]; then
            has_video=true
            break
        fi
    done
}

check_media_present

# If content is missing and we have a real terminal, actively wait for the
# USB drive to be (re)inserted instead of just starting services and hoping
# udev triggers signage-update.service in time.
if { [ "$has_ads" = false ] || [ "$has_video" = false ]; } && [ -t 0 ]; then
    echo ""
    echo -e "  ${YELLOW}No media content installed yet.${NC}"
    echo -e "  Insert your prepared USB drive now — it'll be picked up automatically."
    echo -e "  Press 's' then Enter at any time to stop waiting and continue."
    echo ""

    WAITING=true
    ATTEMPTS=0
    MAX_ATTEMPTS=150   # ~5 minutes at roughly 2s per attempt

    while [ "$WAITING" = true ] && [ "$ATTEMPTS" -lt "$MAX_ATTEMPTS" ]; do
        DEVICE=$(blkid -t TYPE=exfat -o device 2>/dev/null | head -1)
        if [ -n "$DEVICE" ]; then
            info "Found USB drive at $DEVICE — checking content..."
            if python3 "$SCRIPTS_DIR/usb_update.py"; then
                success "Content loaded from USB"
                WAITING=false
            else
                warn "Content on the drive didn't load — fix it on the drive and it'll retry automatically."
                warn "(or press 's' then Enter to stop waiting)"
            fi
            # usb_update.py just ran as root (needed for mount/umount) and may
            # have created/modified files under $INSTALL_ROOT (content, manifest,
            # log). Restore ownership so $SERVICE_USER's services can still
            # read/write them.
            chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_ROOT"
        fi

        if [ "$WAITING" = true ]; then
            if read -r -t 2 -n 1 key 2>/dev/null; then
                if [ "${key,,}" = "s" ]; then
                    warn "Skipping — the drive will still auto-update once inserted after services start."
                    WAITING=false
                fi
            fi
        fi
        ATTEMPTS=$((ATTEMPTS + 1))
    done

    if [ "$WAITING" = true ]; then
        warn "Timed out waiting for a USB drive — continuing without content."
    fi

    check_media_present
fi

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
    echo -e "  Easiest way to build one: ${BLUE}sudo python3 $SCRIPTS_DIR/prep_usb.py${NC}"
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
# Step 16: Start / restart services
# -----------------------------------------------------------------------------

header "Step 16: $([ "$IS_UPDATE" = true ] && echo 'Restarting' || echo 'Starting') services"

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
