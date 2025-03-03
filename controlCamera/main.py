from time import sleep
from datetime import datetime
from sh import gphoto2 as gp
import signal, os, subprocess

shot_date = datetime.now().strftime("%Y-%m-%d")
shot_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
picID = "PiShots_" + shot_time

captureAndDownloadCommand = ["--capture-image-and-download"]
changeFileNameCommand = ["--filename "+picID+".jpg"]

folder_name = shot_date + picID

def createSaveFolder():
    try:
        os.makedirs(folder_name)
    except:
        print("Failed to create the new directory.")
    os.chdir(folder_name)
    print("Changed to directory: " + folder_name)

def captureImages():
    gp(changeFileNameCommand)
    gp(captureAndDownloadCommand)
    print("Captured the image: "+picID+".jpg")

createSaveFolder()
captureImages()

