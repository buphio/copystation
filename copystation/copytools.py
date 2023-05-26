"""
COPYTOOLS
Misc tools for copying files - e.g. with checksum verification.

Copyright (c) 2023 Philipp Buchinger
"""

import logging
import subprocess

from pathlib import Path


def vcopy(source: Path, destination: Path, logfile: Path):
    """
    Copy all files from 'source' to 'destination'.
    Create a checksum for each file from 'source' and 'destination' and verify.
    Re-copy files if necessary.
    """

    if not source.exists() or not destination.exists():
        print("source and/or destination do not exist")
        return False

    try:
        subprocess.run(
            ["rsync", "-a", "--exclude", ".*", "--log-file", logfile, source, destination],
            #user="copycat",
            #group="copycat",
            check=True
        )
    except subprocess.CalledProcessError as error:
        print(error.output)
        return False

    copylog = f"{destination}/copystation.log"

    print("gathering checksums")
    with open(copylog, "w", encoding="utf-8") as checkfile:
        for file in destination.rglob("*"):
            try:
                subprocess.run(["shasum", "-a", "256", file.as_posix()],
                               stdout=checkfile,
                               #user="copycat",
                               #group="copycat",
                               check=True)
            except subprocess.CalledProcessError:
                pass

    return True
