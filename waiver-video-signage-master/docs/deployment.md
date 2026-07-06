Signage Appliance Deployment Notes

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
