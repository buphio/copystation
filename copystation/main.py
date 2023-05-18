from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/add/blkdev")
async def add_blk_device(blk_dev: dict):
    return blk_dev