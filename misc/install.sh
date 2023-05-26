#!/usr/bin/bash

apt install samba
ufw allow Samba
useradd -M -s /sbin/nologin -g copycat copysmb
smbpasswd -a copysmb
tee -a /etc/samba/smb.conf << END
[copystatin]
    comment = copystation
    path = /home/copycat/mounts
    browsable = yes
    read only = no
    create mask = 0775
END
systemctl restart smbd

cp 10-local.rules /etc/udev/rules.d/

reboot now
