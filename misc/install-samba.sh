#!/usr/bin/bash

apt install samba
ufw allow Samba
useradd -M -s /sbin/nologin copyuser
sudo smbpasswd -a copyuser
tee -a /etc/samba/smb.conf << END
[copystatin]
    comment = copystation
    path = /home/copycat/mounts
    browsable = yes
    read only = no
    create mask = 0775
END
systemctl restart smbd
