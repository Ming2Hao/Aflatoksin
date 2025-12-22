from time import sleep
from datetime import datetime
from sh import gphoto2 as gp
import signal, os, subprocess
from typing import Union
from fastapi import FastAPI
from fastapi.responses import FileResponse
import cv2
import numpy as np
import aiofiles
import csv
import json



app = FastAPI()


async def save_grading_to_csv(data):
    """
    Menyimpan hasil grading ke file CSV baru untuk setiap grading.
    Nama file: grading_YYYY-MM-DD-HH-MM-SS.csv
    """
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    csv_filename = f"grading_{timestamp}.csv"
    csv_path = os.path.join("/home/ubuntu/Aflatoksin/controlCamera/hehehe/hasil/", csv_filename)
    
    # Siapkan baris data
    timestamp_readable = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = {
        'timestamp': timestamp_readable,
        'final_grade': data['final_grade'],
        'total_area_pixels': data['total_area_pixels'],
        'total_area_percentage': f"{data['total_area_percentage']:.4f}",
        'total_objects': data['total_objects'],
        'reject_total_pixels': data['summary_by_grade']['REJECT']['total_pixels'],
        'reject_total_objects': data['summary_by_grade']['REJECT']['total_objects'],
        'gradeD_total_pixels': data['summary_by_grade']['GRADE D']['total_pixels'],
        'gradeD_total_objects': data['summary_by_grade']['GRADE D']['total_objects'],
        'gradeC_total_pixels': data['summary_by_grade']['GRADE C']['total_pixels'],
        'gradeC_total_objects': data['summary_by_grade']['GRADE C']['total_objects'],
        'original_image_path': data['original_image_path'],
        'graded_image_path': data['graded_image_path'],
        'detail_objects': json.dumps(data['summary_by_grade'], ensure_ascii=False)
    }
    
    # Definisikan fieldnames
    fieldnames = ['timestamp', 'final_grade', 'total_area_pixels', 'total_area_percentage', 
                  'total_objects', 'reject_total_pixels', 'reject_total_objects', 
                  'gradeD_total_pixels', 'gradeD_total_objects', 'gradeC_total_pixels', 
                  'gradeC_total_objects', 'original_image_path', 'graded_image_path', 'detail_objects']
    
    # Tulis ke CSV baru
    with open(csv_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
    
    print(f"✅ Grading result saved to CSV: {csv_path}")
    
    # Tambahkan path CSV ke response data
    data['csv_path'] = csv_path
    return csv_filename





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

async def grade_using_cv(filepath: str):
    """
    Mendeteksi dan mengklasifikasikan aflatoksin pada gambar jagung.
    - Warna isian sesuai dengan grade piksel masing-masing.
    - Warna kotak dan label sesuai dengan grade terparah dalam satu area.
    """
    print("Detecting and Grading Aflatoxin using OpenCV...")
    image = cv2.imread(str(filepath))
    if image is None:
        print(f"Error: Image not found at path: {filepath}")
        raise ValueError("Image not found or the path is incorrect")

    # 1. Pre-processing Gambar
    filtered_image = cv2.medianBlur(image, 5)
    filtered_image = cv2.GaussianBlur(filtered_image, (9, 9), 0)

    # 2. Kalkulasi Indeks NDFI
    B, G, R = cv2.split(filtered_image)
    B = B.astype(float)
    G = G.astype(float)
    NDFI = (B - G) / (B + G + 0.0001)
    NDFI_normalized = ((NDFI + 1.0) * 127.5).astype(np.uint8)
    
    # 3. Definisikan Tingkat Intensitas (PENTING: Urutkan dari terparah ke teringan)
    INTENSITY_LEVELS = {
        "REJECT (Sangat Terang)": {"range": (0, 150), "color": (0, 0, 255), "area": 0.0, "count": 0},
        "GRADE D (Terang)": {"range": (151, 160), "color": (0, 165, 255), "area": 0.0, "count": 0},
        "GRADE C (Redup)": {"range": (161, 168), "color": (0, 255, 255), "area": 0.0, "count": 0}
    }

    labeled_image = image.copy()
    min_contour_area = 80

    # --- LOGIKA BARU: DIPISAH MENJADI 2 TAHAP ---

    # TAHAP 1: KLASIFIKASI & PEWARNAAN PIKSEL (SEGMENTASI)
    # ----------------------------------------------------
    # Buat mask untuk setiap level secara EKSKLUSIF agar tidak tumpang tindih
    level_masks = {}
    
    # Reset area dan count untuk semua level
    for level_name in INTENSITY_LEVELS.keys():
        INTENSITY_LEVELS[level_name]["area"] = 0
        INTENSITY_LEVELS[level_name]["count"] = 0
    
    # Buat semua mask terlebih dahulu berdasarkan rentang warna
    all_masks = {}
    for level_name, prop in INTENSITY_LEVELS.items():
        mask = cv2.inRange(NDFI_normalized, prop["range"][0], prop["range"][1])
        all_masks[level_name] = mask
    
    # Terapkan prioritas: grade terparah menang jika ada tumpang tindih
    # Urutan sudah benar di INTENSITY_LEVELS: REJECT > GRADE D > GRADE C
    processed_pixels = np.zeros(NDFI_normalized.shape, dtype=np.uint8)
    
    for level_name in INTENSITY_LEVELS.keys():
        # Ambil mask mentah untuk level ini
        raw_mask = all_masks[level_name]
        
        # Hapus pixel yang sudah diklaim oleh grade lebih parah
        exclusive_mask = cv2.bitwise_and(raw_mask, cv2.bitwise_not(processed_pixels))
        level_masks[level_name] = exclusive_mask
        
        # Tandai pixel ini sebagai sudah diproses
        processed_pixels = cv2.bitwise_or(processed_pixels, exclusive_mask)
        
        # Warnai isian pada gambar output sesuai warna levelnya
        labeled_image[exclusive_mask > 0] = INTENSITY_LEVELS[level_name]["color"]
        
        # Hitung area (jumlah pixel) untuk level ini
        INTENSITY_LEVELS[level_name]["area"] = int(np.count_nonzero(exclusive_mask))
        
        # Hitung jumlah objek terpisah untuk level ini
        contours, _ = cv2.findContours(exclusive_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        INTENSITY_LEVELS[level_name]["count"] = len([c for c in contours if cv2.contourArea(c) > min_contour_area])
    
    # Gunakan processed_pixels sebagai master mask untuk tahap berikutnya
    processed_mask = processed_pixels

    # TAHAP 2: DETEKSI & PELABELAN OBJEK
    # -------------------------------------
    # Gabungkan semua mask untuk menemukan objek/pulau kontaminasi yang utuh
    contours, _ = cv2.findContours(processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Dictionary untuk menyimpan informasi objek per grade
    objects_by_grade = {
        "REJECT": [],
        "GRADE D": [],
        "GRADE C": []
    }
    
    object_counter = 0
    for contour in contours:
        if cv2.contourArea(contour) < min_contour_area:
            continue
        
        object_counter += 1
        
        # Buat mask sementara hanya untuk kontur saat ini
        contour_mask_temp = np.zeros_like(processed_mask)
        cv2.drawContours(contour_mask_temp, [contour], -1, 255, cv2.FILLED)
        
        # Hitung pixel untuk setiap grade dalam objek ini
        object_pixels_per_grade = {}
        total_object_pixels = 0
        priority_level_name = None
        
        # Cek dari grade terparah ke teringan
        for level_name in INTENSITY_LEVELS.keys():
            # Hitung pixel untuk grade ini dalam objek
            intersection = cv2.bitwise_and(contour_mask_temp, level_masks[level_name])
            pixel_count = int(np.count_nonzero(intersection))
            
            if pixel_count > 0:
                grade_short = level_name.split(" ")[0]
                object_pixels_per_grade[grade_short] = pixel_count
                total_object_pixels += pixel_count
                
                # Simpan priority level (grade terparah)
                if priority_level_name is None:
                    priority_level_name = level_name

        if priority_level_name:
            properties = INTENSITY_LEVELS[priority_level_name]
            priority_color = properties["color"]
            grade_short = priority_level_name.split(" ")[0]
            label = f'{grade_short}'
            
            x, y, w, h = cv2.boundingRect(contour)
            # Gambar KOTAK dan TULISAN dengan warna prioritas tertinggi
            cv2.rectangle(labeled_image, (x, y), (x + w, y + h), priority_color, 2) 
            cv2.putText(labeled_image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, priority_color, 2)
            
            # Simpan informasi objek
            object_info = {
                "object_id": object_counter,
                "grade": grade_short,
                "total_pixels": total_object_pixels,
                "pixels_per_grade": object_pixels_per_grade,
                "bounding_box": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)}
            }
            objects_by_grade[grade_short].append(object_info)

    # 5. Kalkulasi Total dan Tentukan Grade Final
    total_detected_area = sum(level["area"] for level in INTENSITY_LEVELS.values())
    height, width, _ = image.shape
    total_image_area = height * width
    percentage = (total_detected_area / total_image_area) * 100
    
    final_grade = "GRADE A (Bersih)"
    if INTENSITY_LEVELS["REJECT (Sangat Terang)"]["area"] > 0:
        final_grade = "REJECT"
    elif INTENSITY_LEVELS["GRADE D (Terang)"]["area"] > 0:
        final_grade = "GRADE D"
    elif INTENSITY_LEVELS["GRADE C (Redup)"]["area"] > 0:
        final_grade = "GRADE C"
    elif total_detected_area > 0:
        final_grade = "GRADE B (Kontaminasi Minor)"
    
    # 6. Tambahkan Informasi Grading ke Gambar
    info_text_y = 30
    cv2.putText(labeled_image, f"Final Grade: {final_grade}", (10, info_text_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
    info_text_y += 30
    cv2.putText(labeled_image, f"Total Area Terdeteksi: {total_detected_area:.2f} px ({percentage:.4f}%)", (10, info_text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # 7. Simpan Gambar Hasil
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    save_path = os.path.join("/home/ubuntu/Aflatoksin/controlCamera/hehehe/hasil/", f"graded_image_cv-{timestamp}.jpg")
    
    _, img_encoded = cv2.imencode('.jpg', labeled_image)
    async with aiofiles.open(save_path, "wb") as img_file:
        await img_file.write(img_encoded.tobytes())
    print(f"✅ Graded image successfully saved to {save_path}")

    # 8. Siapkan data untuk respons API
    response_data = {
        "final_grade": final_grade,
        "total_area_pixels": total_detected_area,
        "total_area_percentage": percentage,
        "total_objects": object_counter,
        "summary_by_grade": {
            "REJECT": {
                "total_pixels": INTENSITY_LEVELS["REJECT (Sangat Terang)"]["area"],
                "total_objects": len(objects_by_grade["REJECT"]),
                "objects": objects_by_grade["REJECT"]
            },
            "GRADE D": {
                "total_pixels": INTENSITY_LEVELS["GRADE D (Terang)"]["area"],
                "total_objects": len(objects_by_grade["GRADE D"]),
                "objects": objects_by_grade["GRADE D"]
            },
            "GRADE C": {
                "total_pixels": INTENSITY_LEVELS["GRADE C (Redup)"]["area"],
                "total_objects": len(objects_by_grade["GRADE C"]),
                "objects": objects_by_grade["GRADE C"]
            }
        },
        "graded_image_path": save_path,
        "original_image_path": filepath
    }
    
    # 9. Simpan hasil grading ke CSV
    csv_filename = await save_grading_to_csv(response_data)
    response_data['csv_filename'] = csv_filename
    
    return response_data

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

@app.get("/captureImage2")
async def read_root():
    shot_date = datetime.now().strftime("%Y-%m-%d")
    shot_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    picID = "PiShots_" + shot_time

    captureAndDownloadCommand = ["--capture-image-and-download","--filename",picID+".jpg"]

    folder_name = shot_date
    createSaveFolder(folder_name)
    captureImages(captureAndDownloadCommand, picID)


    try:
        result = await grade_using_cv(picID+".jpg")
        return result
    except Exception as e:
        return {"error": str(e)}

    # return FileResponse(picID+".jpg")
    # return {"image_path": os.path.abspath(picID+".jpg")}


@app.get("/gradeImage")
async def grade_image(image_path: str):
    try:
        result = await grade_using_cv(image_path)
        return result
    except Exception as e:
        return {"error": str(e)}

@app.get("/openImage")
def open_image(image_path: str):
    try:
        # Open the image using OpenCV
        image = cv2.imread(image_path)
        if image is None:
            return {"error": "Image not found"}

        return FileResponse(image_path)
    except Exception as e:
        return {"error": str(e)}