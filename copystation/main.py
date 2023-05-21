"""
POC for copystation backend

TODO: create sha1sum file in dest folder, then unmount, write to logfile
"""

import logging.config
from dataclasses import dataclass
from datetime import datetime
from subprocess import check_output, run, PIPE, STDOUT, CalledProcessError
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")
logging.config.fileConfig("logging.conf")
event_logger = logging.getLogger("events")
app_logger = logging.getLogger("app")


@dataclass
class Device:
    # slots would be faster, but do not support default values (label!)
    # __slots__ = ["name", "partition", "label"]
    name: str
    partition: str
    label: str = ""


def get_device_info(device: str) -> list | None:
    """
    try to get partition and label of attached block device via 'lsblk'
    lsblk -n -o SIZE,KNAME,LABEL --bytes /dev/xxx | sort -r | head -2 | tail -1
    TODO: test edge case when no label is given ?
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
            app_logger.critical(f"'{device}' does not contain proper partition")
            return None
        return device_info.split()[1:]
    except CalledProcessError as error:
        app_logger.critical(f"'{device} does not seem to be a proper block device")
        return None


def add_device(name: str) -> None:
    """
    add device
    """
    device_info = get_device_info("mmcblk0")
    if not device_info:
        return
    device = Device(name, *device_info)
    event_logger.info(f"+++ {datetime.now()} {name} '{device.label}'")
    # device attached - mount and copy
    if not mount_device(device):
        return
    event_logger.info(f"=== {datetime.now()} {name} mounted.")


def delete_device(name: str) -> None:
    """
    remove device
    """
    device_info = get_device_info("mmcblk0")
    if not device_info:
        return
    device = Device(name, *device_info)
    event_logger.info(f"--- {datetime.now()} {name} '{device.label}'")


def mount_device(device: Device) -> bool:
    # create mountpoint
    folder_prefix = device.label if device.label != "" else device.name
    mount_point = f"/home/copycat/mounts/{folder_prefix}-{time_formatted()}"
    try:
        run(["mkdir", "-p", mount_point], check=True)
    except CalledProcessError as error:
        app_logger.critical(error)
        return False
    # mount partition
    # - run(["mount", partition, mount_point], check=True)


def create_checksum_file() -> None:
    pass


def time_formatted() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):  # TEMP SOLUTION FOR TESTING PURPOSES
    logs = []
    with open("logs/events.log", mode="r", encoding="utf-8") as logfile:
        for line in logfile:
            color = "red" if line.split()[0] == "---" else "green"
            logs.append(f"{color};{line}")
    return templates.TemplateResponse(
        "testing.html", {"request": request, "logs": logs}
    )


@app.get("/logs", response_class=HTMLResponse)
async def logfile(request: Request):
    with open("logs/app.log", mode="r", encoding="utf-8") as logfile:
        logs = logfile.readlines()
    return templates.TemplateResponse("logs.html", {"request": request, "logs": logs})


@app.post("/device/{name}")
async def device_post(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(add_device, name)
    return {f"{name}": "added"}


@app.delete("/device/{name}")
async def device_delete(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(delete_device, name)
    return {f"{name}": "removed"}
