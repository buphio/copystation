from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from datetime import datetime
from typing import Tuple
import subprocess

app = FastAPI()


def get_device_info(device: str) -> Tuple[str, str] | None:
    disk_info = subprocess.check_output(['./get_disk_info.sh', device]).decode().strip()
    print(disk_info)
    return (disk_info.split()[1], disk_info.split()[2])


async def handle_device(name: str, action: str):
    # label = subprocess.check_output(['lsblk', '-n', '-o', 'LABEL', f'/dev/{name}'])
    partition, label = get_device_info("mmcblk0p")
    with open("logfile", mode="a", encoding="utf-8") as logfile:
        logfile.write(f"{action} {datetime.now()} /dev/{name} {partition} {label}\n")


@app.get("/")
async def root():  # TEMP SOLUTION FOR TESTING PURPOSES
    html_response = """<html><head><title>Copystation</title>
    <style>body { font-family: monospace; }</style></head>
    <body><h1>Logfile</h1>"""
    with open("logfile", mode="r", encoding="utf-8") as logfile:
        for line in logfile:
            color = "black"
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
