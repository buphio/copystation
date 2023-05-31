import logging.config

from dataclasses import dataclass
from glob import glob
from subprocess import run, check_output, PIPE, STDOUT, CalledProcessError


logging.config.fileConfig("../logs/logging.ini")
event_logger = logging.getLogger("events")
app_logger = logging.getLogger("app")


@dataclass
class Device:
    """Device class that holds information of attached drive."""

    name: str
    partition: str
    label: str = ""


def get_device_info(device: str) -> Device | None:
    """
    Try to get biggest partition and its label of newly attached block device.
    """

    command = ["lsblk", "-n", "-o", "SIZE,KNAME", "-b"]
    partitions = glob(f"/dev/{device}[0-9]")

    if not partitions:
        app_logger.critical("Device '%s' not found.", device)
        return None

    command.extend(partitions)

    try:
        lsblk = run(command, stderr=STDOUT, stdout=PIPE, check=True)
        sort = run(["sort", "-r"], input=lsblk.stdout, stdout=PIPE, check=True)

        partition = check_output(["head", "-1"], input=sort.stdout).decode().split()[1]
        print(partition)

        if not partition:
            app_logger.critical("'%s': could not parse required partition", device)
            return None

        label = (
            check_output(["blkid", "-o", "value", "-s", "LABEL", f"/dev/{partition}"])
            .decode()
            .strip()
        )

        #return [partition, label]
        return Device(device, partition, label)

    except CalledProcessError as error:
        app_logger.critical(error)
        return None
