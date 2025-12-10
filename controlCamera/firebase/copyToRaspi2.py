import cv2
import numpy as np
import os
import sys
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import aiofiles
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage
import mimetypes

cred = credentials.Certificate("ta-aflatoksin-firebase-adminsdk-fbsvc-bc1c3ed4a4.json")
firebase_admin.initialize_app(cred, {
    'storageBucket' : "ta-aflatoksin.firebasestorage.app"
})
# --- Konfigurasi ---
# Pastikan path folder ini ada di sistem Anda atau ubah sesuai kebutuhan.
# Gunakan forward slashes untuk kompatibilitas lintas platform.
FOLDER_PATH = 'hasil'
LINK_ADDRESS = "https://giving-tolerant-gnat.ngrok-free.app"
if not os.path.exists(FOLDER_PATH):
    os.makedirs(FOLDER_PATH)
    print(f"Created directory: {FOLDER_PATH}")
def save_file_to_firebase(file_path, unique_name):
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        content_type = 'image/jpg'

    bucket = storage.bucket()
    blob = bucket.blob(f'image/{unique_name}')
    
    blob.upload_from_filename(file_path, content_type=content_type)
    blob.make_public()

    return blob.public_url
# --- Fungsi Inti Deteksi dan Grading ---

async def detect_and_grade_aflatoxin(filepath: str):
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
    # Buat mask untuk setiap level secara eksklusif agar tidak tumpang tindih
    level_masks = {}
    processed_mask = np.zeros(NDFI_normalized.shape, dtype=np.uint8)
    for level_name, prop in INTENSITY_LEVELS.items():
        # Buat mask mentah untuk rentang warna saat ini
        raw_mask = cv2.inRange(NDFI_normalized, prop["range"][0], prop["range"][1])
        # Hapus piksel yang sudah diproses oleh level yang lebih tinggi
        exclusive_mask = cv2.bitwise_and(raw_mask, cv2.bitwise_not(processed_mask))
        level_masks[level_name] = exclusive_mask
        
        # Warnai isian (segmentasi) pada gambar output sesuai warna levelnya
        labeled_image[exclusive_mask > 0] = prop["color"]
        
        # Hitung statistik area dan jumlah untuk level ini
        prop["area"] = np.count_nonzero(exclusive_mask)
        contours, _ = cv2.findContours(exclusive_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        prop["count"] = len([c for c in contours if cv2.contourArea(c) > min_contour_area])

        # Perbarui master mask untuk iterasi selanjutnya
        processed_mask = cv2.bitwise_or(processed_mask, exclusive_mask)

    # TAHAP 2: DETEKSI & PELABELAN OBJEK
    # -------------------------------------
    # Gabungkan semua mask untuk menemukan objek/pulau kontaminasi yang utuh
    contours, _ = cv2.findContours(processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    total_detected_area2 = 0
    for contour in contours:
        if cv2.contourArea(contour) < min_contour_area:
            continue
        
        # Tentukan grade tertinggi di dalam kontur objek ini
        priority_level_name = None
        # Buat mask sementara hanya untuk kontur saat ini
        contour_mask_temp = np.zeros_like(processed_mask)
        cv2.drawContours(contour_mask_temp, [contour], -1, 255, cv2.FILLED)

        # Cek dari grade terparah ke teringan
        for level_name in INTENSITY_LEVELS.keys():
            # Cek apakah ada irisan antara kontur ini dengan mask level tersebut
            if np.any(cv2.bitwise_and(contour_mask_temp, level_masks[level_name])):
                priority_level_name = level_name
                break # Ditemukan level tertinggi, hentikan pencarian

        if priority_level_name:
            properties = INTENSITY_LEVELS[priority_level_name]
            priority_color = properties["color"]
            label = f'{priority_level_name.split(" ")[0]}'
            
            x, y, w, h = cv2.boundingRect(contour)
            # Gambar KOTAK dan TULISAN dengan warna prioritas tertinggi
            cv2.rectangle(labeled_image, (x, y), (x + w, y + h), priority_color, 2) 
            cv2.putText(labeled_image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, priority_color, 2)
            total_detected_area2+=1

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
    save_path = os.path.join(FOLDER_PATH, f"graded_image-{timestamp}.jpg")
    
    _, img_encoded = cv2.imencode('.jpg', labeled_image)
    async with aiofiles.open(save_path, "wb") as img_file:
        await img_file.write(img_encoded.tobytes())
    firebase_path = save_file_to_firebase(save_path, f"graded_image-{timestamp}.jpg")
    print(f"✅ Graded image successfully saved to {save_path}")

    # 8. Siapkan data untuk respons API
    response_data = {
        "final_grade": final_grade,
        "total_area_pixels": total_detected_area,
        "total_area_percentage": percentage,
        "detection_details": {
            level: {
                "area": properties["area"],
                "count": properties["count"]
            } for level, properties in INTENSITY_LEVELS.items()
        },
        "total_detected_objects": total_detected_area2,
        "graded_image_path": firebase_path,
        "original_image_path": filepath
    }
    
    return response_data

# --- Konfigurasi FastAPI ---
app = FastAPI()
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_data_from_third_party_api(url: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error from image source: {e}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"Request error to image source: {e}")

# --- Endpoints API ---

@app.get("/DetectAndGrade")
async def detect_and_grade_endpoint():
    """
    Endpoint untuk mengambil gambar dari API lain, menyimpannya,
    menjalankan deteksi & grading, dan mengembalikan hasilnya.
    """
    try:
        image_source_url = f"{LINK_ADDRESS}/captureImage"
        image_data = await fetch_data_from_third_party_api(image_source_url)
        
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        original_save_path = os.path.join(FOLDER_PATH, f"original-{timestamp}.jpg")
        
        async with aiofiles.open(original_save_path, "wb") as img_file:
            await img_file.write(image_data.content)
        original_firebase_path = save_file_to_firebase(original_save_path, f"original-{timestamp}.jpg")
        print(f"✅ Original image successfully saved to {original_save_path}")

        
        grading_result = await detect_and_grade_aflatoxin(original_save_path)

        grading_result["original_image_path"] = original_firebase_path
        
        return JSONResponse(content={"message": "Success", "data": grading_result}, status_code=200)

    except HTTPException as e:
        raise e
    except ValueError as e:
        return JSONResponse(content={"message": "Processing Error", "detail": str(e)}, status_code=400)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return JSONResponse(content={"message": f"An unexpected server error occurred: {str(e)}"}, status_code=500)

@app.get("/getImage")
async def get_image_endpoint(filepath: str):
    """
    Endpoint untuk menyajikan file gambar berdasarkan path yang diberikan.
    """
    if not os.path.abspath(filepath).startswith(os.path.abspath(FOLDER_PATH)):
        raise HTTPException(status_code=403, detail="Access Forbidden: Cannot access files outside the designated folder.")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found at the specified path.")
        
    return FileResponse(filepath)

@app.post("/manuallyInputPath")
async def manually_input_path(filepath: str):
    """
    Endpoint untuk menerima path gambar secara manual dan menjalankan grading.
    """
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Image not found at the specified path.")
    
    try:
        grading_result = await detect_and_grade_aflatoxin(filepath)
        return JSONResponse(content={"message": "Success", "data": grading_result}, status_code=200)
    except ValueError as e:
        return JSONResponse(content={"message": "Processing Error", "detail": str(e)}, status_code=400)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return JSONResponse(content={"message": f"An unexpected server error occurred: {str(e)}"}, status_code=500)
# Untuk menjalankan server:
# uvicorn nama_file_anda:app --reload
