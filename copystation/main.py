"""
POC for copystation backend

TODO: implement proper logging
TODO: use jinja template for /
"""

import time
from datetime import datetime
from subprocess import check_output, run
from typing import Tuple
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


def get_device_info(device: str) -> Tuple[str, str] | None:
    device_info = check_output(["./get_disk_info.sh", device]).decode().strip()
    if not device_info or len(device_info.split()) != 3:
        return (None, None)
    return (device_info.split()[1], device_info.split()[2])


def handle_device(name: str, action: str) -> None:
    partition, label = get_device_info("mmcblk0p")
    if not partition or not label:
        print("ERROR: not a valid drive.")
        return
    if action == "+++":
        mount_device(partition, label)
    with open("logfile", mode="a", encoding="utf-8") as logfile:
        logfile.write(f"{action} {datetime.now()} {name} {partition} '{label}'\n")


def mount_device(partition: str, label: str) -> None:
    # create mountpoint
    run(["mkdir", "-p", f"/home/copycat/mounts/{label}-{time_formatted()}"], check=False)
    time.sleep(10)
    # mount partition
    # copy empty folder/file structure


def time_formatted() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@app.get("/")
async def root():  # TEMP SOLUTION FOR TESTING PURPOSES
    html_response = """<html><head><title>Copystation</title>
    <style>body { font-family: monospace; background-color: #ebebeb; font-size: 14px; }
    </style></head><body><h1>Logfile</h1>"""
    with open("logfile", mode="r", encoding="utf-8") as logfile:
        for line in logfile:
            color = "black"
            if line.split()[0] == "+++":
                color = "green"
            elif line.split()[0] == "---":
                color = "#ae0000"
            html_response += f"<div style='color:{color};'>{line}</div>"
    html_response += "</body></html>"
    return HTMLResponse(content=html_response, status_code=200)


@app.post("/device/{name}")
async def device_add(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(handle_device, name, "+++")
    return {f"{name}": "added"}


@app.delete("/device/{name}")
async def device_del(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(handle_device, name, "---")
    return {f"{name}": "removed"}
