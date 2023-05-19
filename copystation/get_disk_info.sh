#!/usr/bin/bash

lsblk -n -o SIZE,KNAME,LABEL --bytes /dev/$1[1-9] | sort -n -r | head -1