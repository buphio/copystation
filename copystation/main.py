"""
POC for "copystation" FastAPI backend.

Copyright (c) 2023 Philipp Buchinger
"""

import configparser
import logging.config

from dataclasses import dataclass
from datetime import datetime
from subprocess import check_output, run, PIPE, STDOUT, CalledProcessError

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

templates = Jinja2Templates(directory="templates")

logging.config.fileConfig("logging.ini")
event_logger = logging.getLogger("events")
app_logger = logging.getLogger("app")


@dataclass
class Device:
    """Device class that holds name, partition to mount and label of attached drive."""

    name: str
    partition: str
    label: str = ""


def get_device_info(device: str) -> list | None:
    """
    Try to get biggest partition (to mount) and label of attached block device via 'lsblk'.
    lsblk -n -o SIZE,KNAME,LABEL --bytes /dev/xxx | sort -r | head -2 | tail -1
    """

    try:
        lsblk = run(
            ["lsblk", "-n", "-o", "SIZE,KNAME,LABEL", "-b", f"/dev/{device}"],
            stderr=STDOUT,
            stdout=PIPE,
            check=True,
        )
        sort = run(["sort", "-r"], input=lsblk.stdout, stdout=PIPE, check=True)
        head = run(["head", "-2"], input=sort.stdout, stdout=PIPE, check=True)
        device_info = check_output(["tail", "-1"], input=head.stdout).decode().strip()

        if len(device_info.split()) < 2:
            app_logger.critical("'%s' does not contain proper partition", device)
            return None

        return device_info.split()[1:]
    except CalledProcessError:
        app_logger.critical("'%s' does not seem to be a proper block device", device)
        return None


def device_attached(name: str) -> None:
    """Try to mount supplied device and copy all files from it."""

    device_info = get_device_info(name)
    if not device_info:
        return

    device = Device(name, *device_info)
    event_logger.info(f"+++ {datetime.now()} {name} '{device.label}'")

    mount_point = mount_device(device)
    if not mount_point:
        return
    event_logger.info(f"::: {datetime.now()} {name} mounted on {mount_point}")

    # read config and create destination folder
    config = configparser.ConfigParser()
    config.read("config.ini")
    project = f"{config['PROJECT']['name']}-{custom_timestamp('date')}"

    folder_prefix = device.label if device.label != "" else device.name
    destination = (
        f"/home/copycat/mounts/{project}/{folder_prefix}-{custom_timestamp('date')}"
    )
    try:
        run(["mkdir", "-p", destination], user="copycat", check=True)
    except CalledProcessError as error:
        app_logger.critical(error)

    if not create_checksum_file(mount_point, destination):
        return
    event_logger.info(f"::: {datetime.now()} {device.label} copied to {destination}")

    # unmount drive
    try:
        run(["umount", mount_point], check=True)
    except CalledProcessError as error:
        app_logger.critical(error)

    # delete mount point
    try:
        run(["rm", "-rf", mount_point], check=True)
    except CalledProcessError as error:
        app_logger.critical(error)

    event_logger.info(f"::: {datetime.now()} {device.label} ready to be ejected")


def device_detached(name: str) -> None:
    """
    remove device
    """
    device_info = get_device_info(name)
    if not device_info:
        return

    device = Device(name, *device_info)
    event_logger.info(f"--- {datetime.now()} {name} '{device.label}'")


def mount_device(device: Device) -> str | None:
    """
    Create mount point from device label or device name and try to mount it.
    # TODO: check mountpoint!!!
    """

    mount_point = f"/mnt/{device.name}-{custom_timestamp()}"
    try:
        run(["mkdir", "-p", f"{mount_point}"], check=True)
    except CalledProcessError:
        app_logger.critical(f"Could not create '{mount_point}'")
        return None

    # mount partition
    # check filesystem first, for edge-cases where multiple fs are given(?)
    try:
        run(["mount", "-t", "auto", f"/dev/{device.partition}", mount_point], check=True)
    except CalledProcessError as error:
        app_logger.critical(error)
        return None

    return mount_point


def create_checksum_file(mount_point: str, destination: str) -> bool:
    """Create file with sha1 checksum of all files in destination folder."""

    try:
        find_files = run(
            ["find", f"{mount_point}", "-type", "f", "-print0"],
            stderr=STDOUT,
            stdout=PIPE,
            check=True,
        )
        # open file with: stdout=file
        with open(f"{destination}/copy.log", mode="w", encoding="utf8") as file:
            run(
                ["xargs", "-0", "sha1sum"],
                input=find_files.stdout,
                stdout=file,
                check=True,
            )
    except (CalledProcessError, IOError) as error:
        app_logger.critical(error)

    return True


def copy_files(mount_point: str, destination: str) -> bool:
    """
    copy mounted drive to destination with rsync
    rsync -a [source] [destination]
    """
    # try:
    #    run(["rsync", "-a", mount_point, destination], user="copycat", check=True)
    # except CalledProcessError as error:
    #    app_logger.critical(error)
    #    return False

    return True


def custom_timestamp(dt_format="datetime") -> str:
    """
    create timestamp depending on passed argument
    """
    if dt_format == "date":
        return datetime.now().strftime("%Y%m%d")
    if dt_format == "time":
        return datetime.now().strftime("%H%M%S")
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def set_user_settings(project_name: str):
    """
    update user.conf file with new project name
    """
    config = configparser.ConfigParser()
    config.read("config.ini")
    config["PROJECT"]["name"] = project_name
    with open("config.ini", "w", encoding="utf-8") as config_file:
        config.write(config_file)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):  # TEMP SOLUTION FOR TESTING PURPOSES
    """
    read events.log and present it in colorcoded fashion to user
    with minimalistic html template
    """
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
