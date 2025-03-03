from time import sleep
from datetime import datetime
from sh import gphoto as gp
import signal, os, subprocess

shot_date = datetime.now().strftime("%Y-%m-%d")
shot_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
picID = "PiShots"

# clearCommand = ["--folder", "/store_00010001/DCIM/100CANON", \
#                 "-R", "--delete-all-files"]
triggerCommand = ["--image-capture"]
downloadCommand = ["--get-all-files"]

folder_name = shot_date + picID

def createSaveFolder():
    try:
        os.makedirs(folder_name)
    except:
        print("Failed to create the new directory.")
    os.chdir(folder_name)
    print("Changed to directory: " + folder_name)

def captureImages():
    gp(triggerCommand)
    # sleep(3)
    gp(downloadCommand)
    # gp(clearCommand)

def renameFiles(ID):
    for filename in os.listdir("."):
        if len(filename) < 13:
            if filename.endswith(".JPG"):
                os.rename(filename, (shot_time + ID + ".JPG"))
                print("Renamed the JPG")
            elif filename.endswith(".CR2"):
                os.rename(filename, (shot_time + ID + ".CR2"))
                print("Renamed the CR2")

createSaveFolder()
captureImages()
renameFiles(picID)

