"""
POC for copystation backend

TODO: implement proper logging
"""

from dataclasses import dataclass
from datetime import datetime
from subprocess import check_output, run, PIPE, STDOUT, CalledProcessError
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@dataclass
class Device:
    __slots__ = ["partition", "label", "name"]
    partition: str
    label: str
    name: str


def get_device_info(device: str) -> list:
    """
    try to get partition and label of attached block device via 'lsblk'
    lsblk -n -o SIZE,KNAME,LABEL --bytes /dev/xxx | sort -r | head -2 | tail -1
    TODO: test edge case when no label is given
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
        return device_info.split()[1:]
    except CalledProcessError:
        # TODO: logging!
        return [""] * 2


def handle_device(name: str, action: str) -> None:
    """get information about device and decide how to handle it"""
    device = Device(*get_device_info("mmcblk0"), name)
    if device.partition == "":
        # TODO: logging!
        print("ERROR: not a valid drive.")
        return
    if action == "+++":
        mount_device(device)
    with open("logfile", mode="a", encoding="utf-8") as logfile:
        logfile.write(
            f"{action} {datetime.now()} {name} {device.partition} '{device.label}'\n"
        )


def mount_device(device: Device) -> None:
    # create mountpoint
    folder_prefix = device.label if device.label != "" else device.name
    mount_point = f"/home/copycat/mounts/{folder_prefix}-{time_formatted()}"
    run(["mkdir", "-p", mount_point], check=True)
    # mount partition
    # - run(["mount", partition, mount_point], check=False)
    # create sha1sum file for src folder
    # - find copystation -type f -exec sha1sum {} \;
    # copy src -> dest
    # check dest files with sha1sum


def time_formatted() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@app.get("/")
async def root():  # TEMP SOLUTION FOR TESTING PURPOSES
    logs = []
    with open("logfile", mode="r", encoding="utf-8") as logfile:
        for line in logfile:
            color = "black"
            if line.split()[0] == "+++":
                color = "green"
            elif line.split()[0] == "---":
                color = "#ae0000"
            logs.append(f"<div style='color:{color};'>{line}</div>")
    return templates.TemplateResponse("log.html", logs)


@app.post("/device/{name}")
async def device_add(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(handle_device, name, "+++")
    return {f"{name}": "added"}


@app.delete("/device/{name}")
async def device_del(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(handle_device, name, "---")
    return {f"{name}": "removed"}
