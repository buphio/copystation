"""
POC for copystation backend.

TODO: implement proper logging
TODO: use jinja template for /
"""

from datetime import datetime
from subprocess import check_output
from typing import Tuple
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


def get_device_info(device: str) -> Tuple[str, str] | None:
    device_info = check_output(["./get_disk_info.sh", device]).decode().strip()
    if len(device_info.split()) < 3:
        return None
    return (device_info.split()[1], device_info.split()[2])


def handle_device(name: str, action: str):
    partition, label = get_device_info("mmcblk0p")
    if not partition or not label:
        return
    with open("logfile", mode="a", encoding="utf-8") as logfile:
        logfile.write(f"{action} {datetime.now()} /dev/{name} {partition} {label}\n")


@app.get("/")
async def root():  # TEMP SOLUTION FOR TESTING PURPOSES
    html_response = """<html><head><title>Copystation</title>
    <style>body { font-family: monospace; background-color: black; }</style></head>
    <body><h1 style="color:white;">Logfile</h1>"""
    with open("logfile", mode="r", encoding="utf-8") as logfile:
        for line in logfile:
            color = "white"
            if line.split()[0] == "+++":
                color = "green"
            elif line.split()[0] == "---":
                color = "red"
            html_response += f"<div style='color:{color};'>{line}</div>"
    html_response += "</body></html>"
    return HTMLResponse(content=html_response, status_code=200)


@app.post("/add/device/{name}")
async def add_device(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(handle_device, name, "+++")
    return name


@app.post("/del/device/{name}")
async def del_device(name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(handle_device, name, "---")
    return name
