import cv2
import numpy as np
import os
import glob
import sys,requests, time, asyncio, nest_asyncio, aiofiles
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
import httpx
folderpath= 'C:/Users/Ivan Laptop/Downloads/asd/datasets/hasil'
async def fetch_data_from_third_party_api(url: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url,timeout=600)
            # response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error occurred: {e}")
        except httpx.RequestError as e:
             raise HTTPException(status_code=500, detail=f"Request error occurred: {e}")
async def DetectAflatoksinUsingCV(filepath):
    print("Detecting Aflatoksin using OpenCV...")
    image = cv2.imread(str(filepath))
    # Ensure the image is in the correct format
    if image is None:
        print("Image not found or the path is incorrect")
    else:
        # Apply median filtering to reduce salt-and-pepper noise
        filtered_image = cv2.medianBlur(image, 5)

        # Apply Gaussian blurring to smooth the image further
        filtered_image = cv2.GaussianBlur(filtered_image, (9, 9), 0)

        # Split the channels of the filtered image
        B, G, R = cv2.split(filtered_image)
        # B, G, R = cv2.split(image)

        # Convert channels to floats for precision
        B = B.astype(float)
        G = G.astype(float)

        # Apply the NDFI formula
        NDFI = (B - G) / (B + G + 0.0001)

        # Normalize NDFI to 0-255 scale and convert to uint8
        NDFI_normalized = ((NDFI + 1.0) * 127.5).astype(np.uint8)

        # Define the threshold range
        threshold_value_min = 168  # Minimum threshold value
        threshold_value_max = 360  # Maximum threshold value

        # Apply thresholding within the range
        _, lower_threshold = cv2.threshold(NDFI_normalized, threshold_value_min, 255, cv2.THRESH_BINARY_INV)
        _, upper_threshold = cv2.threshold(NDFI_normalized, threshold_value_max, 255, cv2.THRESH_BINARY_INV)
        # Filter out small segments in lower_threshold (ignore areas smaller than 70 pixels)
        contours_lt, _ = cv2.findContours(lower_threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filtered_lower = np.zeros_like(lower_threshold)
        for cnt in contours_lt:
            if cv2.contourArea(cnt) >= 80:
                cv2.drawContours(filtered_lower, [cnt], -1, 255, cv2.FILLED)
        lower_threshold = filtered_lower

        # Combine the lower and upper threshold masks
        dark_regions_mask = cv2.bitwise_and(lower_threshold, upper_threshold)

        # Invert the mask to eliminate dark areas
        inverted_mask = cv2.bitwise_not(dark_regions_mask)

        # Apply the inverted mask to remove dark areas from the image
        cleaned_image = cv2.bitwise_and(filtered_image, filtered_image, mask=inverted_mask)

        # Find contours on the mask
        # contours, _ = cv2.findContours(inverted_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours, _ = cv2.findContours(lower_threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Draw contours and label them
        labeled_image = cleaned_image.copy()

        # Loop through each contour and label them
        countingLabel=1;
        pixel=0;
        percentage=0.0;
        for i, contour in enumerate(contours):
            # Get the area of the contour
            area = cv2.contourArea(contour)

            # If the contour area is smaller than 70 pixels, skip it
            if area < 80:
                continue
            # Get the bounding box for each contour
            x, y, w, h = cv2.boundingRect(contour)
            pixel=pixel+area
            print(pixel)

            # Draw a rectangle around each detected object
            cv2.rectangle(labeled_image, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Put a label with the contour number
            label = f'{countingLabel+1} - {area:.2f} px'
            cv2.putText(labeled_image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            countingLabel+=1

        
        height, width, channels = labeled_image.shape
        percentage=(pixel/(height*width))*100
        print(percentage)
        save_path2=(f"{folderpath}/labeled_image-{datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H:%M:%S')}.jpg")
        print(save_path2)
        async with aiofiles.open(save_path2, "wb") as img_file:
            await img_file.write(cv2.imencode('.jpg', labeled_image)[1].tobytes())
            print(f"✅ Image successfully saved to {save_path2}")
        return (save_path2,countingLabel-1,str(pixel),percentage)
app = FastAPI()
@app.get("/DetectCV")
async def read_root():
    data = await fetch_data_from_third_party_api("https://localhost:3000/captureImage")
    save_path=(f"{folderpath}/{datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H:%M:%S')}.jpg")
    print(save_path)
    # print(data)
    async with aiofiles.open(save_path, "wb") as img_file:
        await img_file.write(data.content)
        print(f"✅ Image successfully saved to {save_path}")
    # await print(data)
    # async def upload_image(file: UploadFile = File(...)):
    try:
        print(save_path)
        responseImage,totalArea,pixel, percentage = await DetectAflatoksinUsingCV(save_path)
        return JSONResponse(content={"message": "Success", "file": responseImage,"total Area":str(totalArea),"pixel":str(pixel),"percentage":str(percentage) }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"message": f"An error occurred: {str(e)}"}, status_code=500)
# @app.get("/test")
# async def read_root():
#     path_baru="c:/Users/Ivan Laptop/Downloads/asd/datasets/images/18.jpg"
#     print("hehe")
#     await DetectAflatoksinUsingCV(path_baru)