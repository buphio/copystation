"""
COPYTOOLS
Misc tools for copying files - e.g. with checksum verification.

Copyright (c) 2023 Philipp Buchinger
"""

import logging
import subprocess

from pathlib import Path


def vcopy(source: Path, destination: Path):
    """
    Copy all files from 'source' to 'destination'.
    Create a checksum for each file from 'source' and 'destination' and verify.
    Re-copy files if necessary.
    """

    # 1. Test if source and destination exist
    if not source.exists() or not destination.exists():
        print("source and/or destination do not exist")
        return False

    # 2. Copy all files with rsync
    try:
        subprocess.run(
            ["rsync", "-a", "--exclude", ".*", source, destination], check=True
        )
    except subprocess.CalledProcessError as error:
        print(error.output)
        return False

    return True
