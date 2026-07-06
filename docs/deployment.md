Signage Appliance Deployment Notes

Supported OS:

Raspberry Pi OS Lite, Bookworm (Debian 12) or Trixie (Debian 13).
deploy.sh detects the correct ImageMagick policy path (IM6 on Bookworm,
IM7 on Trixie) automatically — no manual changes needed either way.

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
