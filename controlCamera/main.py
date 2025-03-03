from time import sleep
from datetime import datetime
from sh import gphoto2 as gp
import signal, os, subprocess
from typing import Union
from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()





def createSaveFolder(folder_name):
    try:
        os.makedirs(folder_name)
    except:
        print("Failed to create the new directory.")
    os.chdir(folder_name)
    print("Changed to directory: " + folder_name)

def captureImages(command, picID):
    gp(command)
    print("Captured the image: "+picID+".jpg")

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/captureImage")
def read_root():
    shot_date = datetime.now().strftime("%Y-%m-%d")
    shot_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    picID = "PiShots_" + shot_time

    captureAndDownloadCommand = ["--capture-image-and-download","--filename",picID+".jpg"]

    folder_name = shot_date
    createSaveFolder(folder_name)
    captureImages(captureAndDownloadCommand, picID)
    return FileResponse(picID+".jpg")
