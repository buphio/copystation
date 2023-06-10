"""
POC for "copystation" FastAPI backend.

Copyright (c) 2023 Philipp Buchinger
"""

import configparser
import json
import logging.config
import re
import time

from dataclasses import dataclass
from datetime import datetime
from glob import glob
from pathlib import Path
from subprocess import check_output, run, PIPE, STDOUT, CalledProcessError

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


app = FastAPI()

templates = Jinja2Templates(directory="templates")

logging.config.fileConfig("logs/logging.ini")
event_logger = logging.getLogger("events")
app_logger = logging.getLogger("app")


@dataclass
class Device:
    """Device class that holds information of attached drive."""

    name: str
    serial: str
    partition: str
    fstype: str
    smart_status: str
    port: str = ""
    label: str = ""


def get_device_info(device: str) -> list | None:
    """
    Try to get biggest partition and its label of newly attached block device.
    - udevadm info -q path -n /dev/sd
    - (re.search("ata[1-9]|usb[1-9]", string)).group()
    """

    # unfortunately udev fires off the add rule before the kernel module is fully
    # loaded, hence the hacky sleep method
    time.sleep(2)
    print("1: sleep(2) finished")

    try:
        device_path = check_output(
            ["udevadm", "info", "-q", "path", "-n", f"/dev/{device}"]
        ).decode().strip()
        print(f"2: {device_path}")
        port = (re.search("ata[1-9]|usb[1-9]", device_path)).group()  #pyright: ignore

        if not port:
            app_logger.critical("Could not detect device port")
            return

        print(f"3: port defined: {port}")

    except CalledProcessError as error:
        app_logger.critical(error)
        return

    partitions = glob(f"/dev/{device}[0-9]")

    if not partitions:
        app_logger.critical("%s does not contain any valid partitions", device)
        return
    print(f"4: {partitions}")

    command = ["lsblk", "-n", "-o", "SIZE,KNAME,FSTYPE,LABEL", "-b"]
    command.extend(partitions)
    print(f"5: {command}")

    try:
        lsblk = run(command, stderr=STDOUT, stdout=PIPE, check=True)
        sort = run(["sort", "-rn"], input=lsblk.stdout, stdout=PIPE, check=True)
        print(f"6: {sort}")

        device_info = check_output(["head", "-1"], input=sort.stdout).decode().split()[1:]

        if len(device_info) == 1:
            device_info.extend(["exfat", "UNKNOWN"])
        print(f"7: {device_info}")

    except (CalledProcessError) as error:
        app_logger.critical(error)
        return None

    try:
        smartctl = json.loads(
            check_output(["smartctl", "-ia", "--json", f"/dev/{device}"])
            .decode()
            .strip()
        )

        serial_number = smartctl["serial_number"]
        smart_status = "Passed" if smartctl["smart_status"]["passed"] else "Failed"
        print(f"8: {serial_number} {smart_status}")

    except (CalledProcessError, json.JSONDecodeError) as error:
        app_logger.warning(error)
        smart_status, serial_number = ""

    print("9: returning values...")
    return [serial_number, device_info[0], device_info[1], smart_status, port, device_info[2]]


def device_attached(name: str) -> None:
    """Try to mount supplied device and copy all files from it."""

    device_info = get_device_info(name)
    print(f"10: {device_info}")
    if not device_info:
        app_logger.critical("Error obtaining device information.")
        return

    device = Device(name, *device_info)
    print("11: device created!")
    event_logger.info("+++ %s %s (%s) attached", datetime.now(), device.label, name)
    event_logger.info(
        "::: %s %s (%s) SMART status: %s",
        datetime.now(),
        device.label,
        device.serial,
        device.smart_status,
    )

    source = mount_device(device)
    if not source:
        return

    event_logger.info(
        "::: %s %s (%s) mounted on %s",
        datetime.now(),
        device.label,
        device.serial,
        source,
    )

    config = configparser.ConfigParser()
    config.read("config.ini")

    project = f"{config['PROJECT']['name']}-{custom_timestamp('date')}"
    folder_prefix = device.label if device.label != "" else device.name
    folder_root = f"/home/copycat/mounts"

    destination = Path(
        f"{folder_root}/{project}/{folder_prefix}_{custom_timestamp('datetime')}"
    )
    try:
        run(["mkdir", "-p", destination], user="copycat", group="copycat", check=True)
    except CalledProcessError as error:
        app_logger.critical(error)

    if create_checksum_file(source, destination):
        event_logger.info(
            "::: %s %s (%s) copied to %s",
            datetime.now(),
            device.label,
            device.serial,
            destination,
        )

    try:
        run(["umount", source], check=True)
    except CalledProcessError as error:
        app_logger.critical(error)

    try:
        run(["rm", "-rf", source], check=True)
    except CalledProcessError as error:
        app_logger.critical(error)

    event_logger.info(
        "::: %s %s (%s) ready to be ejected",
        datetime.now(),
        device.label,
        device.serial,
    )


def device_detached(name: str) -> None:
    """Remove attached device."""

    event_logger.info("--- %s '%s'", datetime.now(), name)


def mount_device(device: Device) -> Path | None:
    """
    Create mount point from device label or device name and try to mount it.
    """

    mount_point = Path(f"/mnt/{device.name}_{custom_timestamp()}")
    try:
        run(["mkdir", "-p", mount_point], check=True)
    except CalledProcessError:
        app_logger.critical("Could not create '%s'", mount_point)
        return None

    try:
        run(
            [
                "mount",
                "-t",
                device.fstype,
                "-o",
                "ro",
                f"/dev/{device.partition}",
                mount_point,
            ],
            check=True,
        )
    except CalledProcessError as error:
        app_logger.critical(error.output)
        return None

    return mount_point


def create_checksum_file(mount_point: Path, destination: Path) -> bool:
    """Create file with sha1 checksum of all files in destination folder."""

    try:
        checksum_log = f"{destination}/copystation.log"
        run(["touch", checksum_log], user="copycat", group="copycat", check=True)
        with open(checksum_log, mode="w", encoding="utf8") as file:
            run(
                ["find", mount_point, "-type", "f"],
                stderr=STDOUT,
                stdout=file,
                check=True,
            )

    except (CalledProcessError, IOError) as error:
        app_logger.critical(error)
        return False

    return True


def custom_timestamp(date_format="datetime") -> str:
    """Create custom timestamp depending on passed argument."""

    if date_format == "date":
        return datetime.now().strftime("%Y%m%d")
    if date_format == "time":
        return datetime.now().strftime("%H%M%S")
    return datetime.now().strftime("%y%m%d-%H%M%S")


def set_user_settings(project_name: str):
    """Update 'config.ini' file with new project name."""

    config = configparser.ConfigParser()
    config.read("config.ini")
    config["PROJECT"]["name"] = project_name

    with open("config.ini", "w", encoding="utf-8") as config_file:
        config.write(config_file)

    event_logger.info(
        "::: %s Changed project name to '%s'", datetime.now(), project_name
    )
    app_logger.info("Changed project name to %s", project_name)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):  # TEMP SOLUTION FOR TESTING PURPOSES
    """Read 'events.log' and present it in colorcoded fashion."""

    logs = []
    with open("logs/events.log", mode="r", encoding="utf-8") as events_log:
        for line in events_log:
            color = "red" if line.split()[0] == "---" else "green"
            logs.append(f"{color};{line}")
    return templates.TemplateResponse(
        "testing.html", {"request": request, "logs": logs}
    )


@app.get("/logs", response_class=HTMLResponse)
async def logfile(request: Request):
    """Read 'app.log' and display with HTML template."""

    with open("logs/app.log", mode="r", encoding="utf-8") as app_log:
        logs = app_log.readlines()
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})


@app.post("/device/{name}")
async def device_post(name: str, background_tasks: BackgroundTasks):
    """POST newly attached block device."""
    background_tasks.add_task(device_attached, name)
    return {f"{name}": "added"}


@app.delete("/device/{name}")
async def device_delete(name: str, background_tasks: BackgroundTasks):
    """DELETE attached block device."""
    background_tasks.add_task(device_detached, name)
    return {f"{name}": "removed"}


@app.post("/settings/{project_name}")
async def settings_post(project_name: str, background_tasks: BackgroundTasks):
    """POST new user settings."""
    background_tasks.add_task(set_user_settings, project_name)
    return None
