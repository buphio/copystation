#!/usr/bin/bash

# lsblk -n -o KNAME,LABEL,SIZE --bytes /dev/$1[1-9] | sort -k 3 -n -r | head -1
lsblk -n -o KNAME,LABEL,SIZE --bytes /dev/$1