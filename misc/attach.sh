#!/usr/bin/env bash

logfile=/var/log

disk=$1
disk_info=$(/usr/bin/lsblk -n -o SIZE,KNAME,LABEL --bytes /dev/$disk[1-9] | sort -n -r | head -1)
partition=$(echo $disk_info | cut -d" " -f2)
label=$(echo $disk_info | cut -d" " -f3)

if [[ -z $partition ]]; then
    echo "Could not parse required data."
fi

if [[ -z $label ]]; then
    echo "Could not parse label of disk."
fi
