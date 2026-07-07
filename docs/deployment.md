Signage Appliance Deployment Notes

Supported OS:

Raspberry Pi OS Lite, Bookworm (Debian 12) or Trixie (Debian 13).
deploy.sh detects the correct ImageMagick policy path (IM6 on Bookworm,
IM7 on Trixie) automatically — no manual changes needed either way.

USB Drive Setup:

On a fresh install run with a real terminal attached (not piped through
curl), deploy.sh offers to prepare a USB update drive early on (Step 6,
via scripts/prep_usb.py) so you can load ad/showcase/video content onto
it while the rest of the install continues in the background. Later,
if no content has been installed yet, it actively waits for that drive
to be (re)inserted (Step 15) and loads it immediately instead of relying
solely on udev timing — press 's' + Enter at that prompt to stop waiting
and fall back to the old behavior (start services, load content whenever
the drive shows up).

This interactive flow is skipped automatically for update-mode runs and
for non-interactive installs (curl | sudo bash), which fall back to the
prior static instructions. Run scripts/prep_usb.py manually any time to
prepare a drive outside of deploy.sh.

Systemd Services:

signage.service
button.service
signage-update.service

Udev Rules:

99-signage-update.rules

Installation:

Copy files from deploy/systemd into:

/etc/systemd/system/

Copy files from deploy/udev into:

/etc/udev/rules.d/

Reload systemd:

sudo systemctl daemon-reload

Reload udev:

sudo udevadm control --reload-rules
sudo udevadm trigger
