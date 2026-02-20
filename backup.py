from time import sleep
from datetime import datetime
from sh import gphoto2 as gp
import signal, os, subprocess
import math
from typing import Union
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse
import cv2
import numpy as np
import aiofiles
import json
import anyio
import pymysql
from pymysql.cursors import DictCursor



app = FastAPI()


def _round_ppb(value: float) -> int:
    """Bulatkan ppb ke angka bulat terdekat (half-up).

    Catatan: `round()` Python memakai bankers rounding untuk .5,
    jadi pakai floor(x + 0.5) untuk nilai non-negatif.
    """
    try:
        v = float(value)
    except Exception:
        return 0

    if not np.isfinite(v):
        return 0
    if v <= 0:
        return 0
    return int(math.floor(v + 0.5))


def _get_ppb_scoring_params(overrides: dict | None = None) -> dict:
    """Parameter scoring ppb berbasis ukuran (pixel) dan kecerahan.

    Catatan: ini adalah *estimasi* yang perlu dikalibrasi dengan data lab.
    Anda bisa tuning lewat environment variables agar tidak ubah kode.
    """
    # Default koefisien hasil kalibrasi dari 3 contoh user:
    # 1990R + 654D + 329C = 10 ppb
    # 1806R + 304D + 175C = 8 ppb
    # 1017R + 199D + 217C = 4 ppb
    # Solusi linear exact => C bernilai negatif.
    def _get_float_env(name: str, default: str) -> float:
        try:
            return float(os.getenv(name, default))
        except Exception:
            return float(default)

    w_reject = _get_float_env("PPB_W_REJECT", "0.00394745")
    w_grade_d = _get_float_env("PPB_W_GRADE_D", "0.00615017")
    w_grade_c = _get_float_env("PPB_W_GRADE_C", "-0.00570708")

    # Opsional: kalau ingin tetap memasukkan kecerahan rata-rata sebagai pengali.
    # Default 0 agar sesuai kalibrasi berbasis pixel-per-grade saja.
    brightness_weight = _get_float_env("PPB_BRIGHTNESS_WEIGHT", "4.27290")

    # Override dari API (query param) jika disediakan
    if overrides:
        for key, current in (
            ("w_reject", w_reject),
            ("w_grade_d", w_grade_d),
            ("w_grade_c", w_grade_c),
            ("brightness_weight", brightness_weight),
        ):
            val = overrides.get(key)
            if val is None:
                continue
            try:
                new_val = float(val)
            except Exception:
                continue
            # Jangan override dengan NaN/Inf
            if not np.isfinite(new_val):
                continue
            if key == "brightness_weight" and new_val < 0:
                continue
            if key != "brightness_weight" and new_val < 0:
                # weight negatif tidak selalu salah, tapi biasanya tidak diinginkan.
                # Tetap izinkan kalau user memang set negatif? Untuk aman, tolak.
                continue
            if key == "w_reject":
                w_reject = new_val
            elif key == "w_grade_d":
                w_grade_d = new_val
            elif key == "w_grade_c":
                w_grade_c = new_val
            elif key == "brightness_weight":
                brightness_weight = new_val

    return {
        "w_reject": w_reject,
        "w_grade_d": w_grade_d,
        "w_grade_c": w_grade_c,
        "brightness_weight": brightness_weight,
    }


def _estimate_ppb_for_object(
    *,
    pixels_reject: int,
    pixels_grade_d: int,
    pixels_grade_c: int,
    mean_brightness: float,
    w_reject: float,
    w_grade_d: float,
    w_grade_c: float,
    brightness_weight: float,
) -> float:
    """Rumus ppb per objek berbasis pixel per grade.

    Secara default mengikuti kalibrasi linear (berpotensi kontribusi negatif
    untuk GRADE C). brightness_weight opsional sebagai pengali.
    """
    base = (
        float(max(pixels_reject, 0)) * float(w_reject)
        + float(max(pixels_grade_d, 0)) * float(w_grade_d)
        + float(max(pixels_grade_c, 0)) * float(w_grade_c)
    )

    if brightness_weight == 0:
        return base

    brightness_norm = float(mean_brightness) / 255.0
    if brightness_norm < 0:
        brightness_norm = 0.0
    if brightness_norm > 1:
        brightness_norm = 1.0
    return base * (1.0 + float(brightness_weight) * brightness_norm)


def _get_mysql_connection():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "aflatoksin")
    password = os.getenv("MYSQL_PASSWORD", "aflatoksin")
    database = os.getenv("MYSQL_DATABASE", "aflatoksin")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        autocommit=False,
    )


def _select_grading_history_sync(limit: int):
    limit = int(limit)
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    conn = _get_mysql_connection()
    try:
        with conn.cursor(DictCursor) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    captured_at,
                    final_grade,
                    total_area_pixels,
                    total_area_percentage,
                    total_objects,
                    original_image_path,
                    graded_image_path,
                    detail_json
                FROM grading_runs
                ORDER BY captured_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall() or []

        # Normalisasi tipe datetime agar aman untuk JSON.
        for row in rows:
            if isinstance(row.get("captured_at"), datetime):
                row["captured_at"] = row["captured_at"].strftime("%Y-%m-%d %H:%M:%S")
            # PyMySQL kadang mengembalikan JSON sebagai bytes
            if isinstance(row.get("detail_json"), (bytes, bytearray)):
                row["detail_json"] = row["detail_json"].decode("utf-8", errors="replace")
        return rows
    finally:
        conn.close()


@app.get("/gradingHistory")
async def grading_history(limit: int = 20):
    try:
        rows = await anyio.to_thread.run_sync(_select_grading_history_sync, limit)
        return {"data": rows}
    except pymysql.err.OperationalError as e:
        # Biasanya: access denied / can't connect. Lebih cocok 503.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _insert_grading_sync(data) -> int:
    captured_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = data["summary_by_grade"]

    reject_total_pixels = int(summary["REJECT"]["total_pixels"])
    reject_total_objects = int(summary["REJECT"]["total_objects"])
    grade_d_total_pixels = int(summary["GRADE D"]["total_pixels"])
    grade_d_total_objects = int(summary["GRADE D"]["total_objects"])
    grade_c_total_pixels = int(summary["GRADE C"]["total_pixels"])
    grade_c_total_objects = int(summary["GRADE C"]["total_objects"])

    # Simpan payload detail agar history bisa menampilkan ppb_total juga.
    # Tetap simpan format lama (summary_by_grade) sebagai nested field
    # agar UI bisa dibuat backward/forward compatible.
    detail_payload = {
        "ppb_total": data.get("ppb_total"),
        "ppb_scoring_params": data.get("ppb_scoring_params"),
        "summary_by_grade": summary,
    }
    detail_json = json.dumps(detail_payload, ensure_ascii=False)

    conn = _get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO grading_runs (
                    captured_at,
                    final_grade,
                    total_area_pixels,
                    total_area_percentage,
                    total_objects,
                    reject_total_pixels,
                    reject_total_objects,
                    grade_d_total_pixels,
                    grade_d_total_objects,
                    grade_c_total_pixels,
                    grade_c_total_objects,
                    original_image_path,
                    graded_image_path,
                    detail_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    captured_at,
                    str(data["final_grade"]),
                    int(data["total_area_pixels"]),
                    float(data["total_area_percentage"]),
                    int(data["total_objects"]),
                    reject_total_pixels,
                    reject_total_objects,
                    grade_d_total_pixels,
                    grade_d_total_objects,
                    grade_c_total_pixels,
                    grade_c_total_objects,
                    str(data["original_image_path"]),
                    str(data["graded_image_path"]),
                    detail_json,
                ),
            )
            grading_run_id = int(cursor.lastrowid)

        conn.commit()
        return grading_run_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def save_grading_to_mysql(data) -> int:
    """Simpan hasil grading ke database MySQL (bukan CSV)."""
    grading_run_id = await anyio.to_thread.run_sync(_insert_grading_sync, data)
    print(f"✅ Grading result saved to MySQL: grading_runs.id={grading_run_id}")
    return grading_run_id





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
    prev_cwd = os.getcwd()
    shot_date = datetime.now().strftime("%Y-%m-%d")
    shot_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    picID = "PiShots_" + shot_time

    captureAndDownloadCommand = ["--capture-image-and-download","--filename",picID+".jpg"]

    folder_name = shot_date
    try:
        createSaveFolder(folder_name)
        captureImages(captureAndDownloadCommand, picID)
        image_path = os.path.abspath(picID + ".jpg")
        return FileResponse(image_path)
    finally:
        os.chdir(prev_cwd)

def _validate_thresholds(t1: int, t2: int, t3: int) -> tuple[int, int, int]:
    try:
        t1 = int(t1)
        t2 = int(t2)
        t3 = int(t3)
    except Exception:
        raise HTTPException(status_code=400, detail="Thresholds must be integers")

    for name, value in ("t1", t1), ("t2", t2), ("t3", t3):
        if value < 0 or value > 255:
            raise HTTPException(status_code=400, detail=f"{name} must be in range 0-255")

    if not (t1 < t2 < t3):
        raise HTTPException(
            status_code=400,
            detail="Thresholds must be strictly increasing (t1 < t2 < t3)",
        )
    return t1, t2, t3


def _build_intensity_levels(t1: int, t2: int, t3: int):
    # Pastikan tidak ada rentang negatif / terbalik.
    reject_min, reject_max = 0, t1
    grade_d_min, grade_d_max = t1 + 1, t2
    grade_c_min, grade_c_max = t2 + 1, t3

    return {
        "REJECT (Sangat Terang)": {
            "range": (reject_min, reject_max),
            "color": (0, 0, 255),
            "area": 0.0,
            "count": 0,
        },
        "GRADE D (Terang)": {
            "range": (grade_d_min, grade_d_max),
            "color": (0, 165, 255),
            "area": 0.0,
            "count": 0,
        },
        "GRADE C (Redup)": {
            "range": (grade_c_min, grade_c_max),
            "color": (0, 255, 255),
            "area": 0.0,
            "count": 0,
        },
    }


async def grade_using_cv(
    filepath: str,
    thresholds: tuple[int, int, int] = (150, 160, 168),
    ppb_overrides: dict | None = None,
):
    """
    Mendeteksi dan mengklasifikasikan aflatoksin pada gambar jagung.
    - Warna isian sesuai dengan grade piksel masing-masing.
    - Warna kotak dan label sesuai dengan grade terparah dalam satu area.
    """
    print("Detecting and Grading Aflatoxin using OpenCV..")
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

    t1, t2, t3 = thresholds
    INTENSITY_LEVELS = _build_intensity_levels(t1, t2, t3)

    labeled_image = image.copy()
    min_contour_area = 80

    # Parameter scoring ppb (estimasi) via env, bisa dioverride dari API
    ppb_params = _get_ppb_scoring_params(ppb_overrides)

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
        "GRADE C": [],
    }

    object_counter = 0
    ppb_total = 0.0

    gray_for_brightness = cv2.cvtColor(filtered_image, cv2.COLOR_BGR2GRAY)
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
                grade_short = level_name.split("(")[0].strip()
                object_pixels_per_grade[grade_short] = pixel_count
                total_object_pixels += pixel_count

                # Simpan priority level (grade terparah)
                if priority_level_name is None:
                    priority_level_name = level_name

        if priority_level_name:
            properties = INTENSITY_LEVELS[priority_level_name]
            priority_color = properties["color"]
            grade_short = priority_level_name.split("(")[0].strip()
            label = f"ID {object_counter}"

            # Hitung kecerahan rata-rata pada area kontaminasi objek (pakai grayscale 0-255)
            contour_pixels = cv2.countNonZero(contour_mask_temp)
            if contour_pixels > 0:
                mean_brightness = float(cv2.mean(gray_for_brightness, mask=contour_mask_temp)[0])
            else:
                mean_brightness = 0.0

            # Skor ppb per objek (kalibrasi) = bobot(REJECT,D,C) * pixel_per_grade
            px_reject = int(object_pixels_per_grade.get("REJECT", 0))
            px_grade_d = int(object_pixels_per_grade.get("GRADE D", 0))
            px_grade_c = int(object_pixels_per_grade.get("GRADE C", 0))

            ppb_object = _estimate_ppb_for_object(
                pixels_reject=px_reject,
                pixels_grade_d=px_grade_d,
                pixels_grade_c=px_grade_c,
                mean_brightness=mean_brightness,
                w_reject=float(ppb_params["w_reject"]),
                w_grade_d=float(ppb_params["w_grade_d"]),
                w_grade_c=float(ppb_params["w_grade_c"]),
                brightness_weight=float(ppb_params["brightness_weight"]),
            )

            # Hindari nilai ppb negatif (misal karena w_grade_c < 0 pada hasil kalibrasi).
            if ppb_object < 0:
                ppb_object = 0.0
            ppb_total += ppb_object

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
                "mean_brightness": mean_brightness,
                "ppb": _round_ppb(ppb_object),
                "bounding_box": {"x": int(x), "y": int(y), "width": int(w), "height": int(h)},
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
    cv2.putText(
        labeled_image,
        f"Final Grade: {final_grade}",
        (10, info_text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    info_text_y += 30
    cv2.putText(
        labeled_image,
        f"Total Area Terdeteksi: {total_detected_area:.2f} px ({percentage:.4f}%)",
        (10, info_text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    # 7. Simpan Gambar Hasil
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    save_path = os.path.join("/home/ubuntu/fotohasil/", f"graded_image_cv-{timestamp}.jpg")

    _, img_encoded = cv2.imencode(".jpg", labeled_image)
    async with aiofiles.open(save_path, "wb") as img_file:
        await img_file.write(img_encoded.tobytes())
    print(f"✅ Graded image successfully saved to {save_path}")

    # 8. Siapkan data untuk respons API
    ppb_total_rounded = _round_ppb(ppb_total)
    response_data = {
        "final_grade": final_grade,
        "total_area_pixels": total_detected_area,
        "total_area_percentage": percentage,
        "total_objects": object_counter,
        "ppb_total": ppb_total_rounded,
        "ppb_scoring_params": {
            "w_reject": float(ppb_params["w_reject"]),
            "w_grade_d": float(ppb_params["w_grade_d"]),
            "w_grade_c": float(ppb_params["w_grade_c"]),
            "brightness_weight": float(ppb_params["brightness_weight"]),
            "brightness_source": "grayscale_mean_on_object_mask",
            "formula": "ppb = w_reject*px_reject + w_grade_d*px_grade_d + w_grade_c*px_grade_c (optional * brightness factor)",
        },
        "summary_by_grade": {
            "REJECT": {
                "total_pixels": INTENSITY_LEVELS["REJECT (Sangat Terang)"]["area"],
                "total_objects": len(objects_by_grade["REJECT"]),
                "objects": objects_by_grade["REJECT"],
            },
            "GRADE D": {
                "total_pixels": INTENSITY_LEVELS["GRADE D (Terang)"]["area"],
                "total_objects": len(objects_by_grade["GRADE D"]),
                "objects": objects_by_grade["GRADE D"],
            },
            "GRADE C": {
                "total_pixels": INTENSITY_LEVELS["GRADE C (Redup)"]["area"],
                "total_objects": len(objects_by_grade["GRADE C"]),
                "objects": objects_by_grade["GRADE C"],
            },
        },
        "graded_image_path": save_path,
        "original_image_path": filepath,
        "thresholds": {"t1": t1, "t2": t2, "t3": t3},
    }
    print(final_grade)

    # 9. Simpan hasil grading ke MySQL (jangan gagalkan response kalau DB error)
    try:
        grading_run_id = await save_grading_to_mysql(response_data)
        response_data["grading_run_id"] = grading_run_id
    except Exception as e:
        print(f"⚠️  Failed to save grading to MySQL: {e}")
        response_data["grading_run_id"] = None
        response_data["db_error"] = str(e)

    return response_data


@app.get("/captureImage2")
async def read_root(
    t1: int = 150,
    t2: int = 160,
    t3: int = 168,
    w_reject: Union[float, None] = None,
    w_grade_d: Union[float, None] = None,
    w_grade_c: Union[float, None] = None,
):
    prev_cwd = os.getcwd()
    shot_date = datetime.now().strftime("%Y-%m-%d")
    shot_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    picID = "PiShots_" + shot_time

    captureAndDownloadCommand = ["--capture-image-and-download","--filename",picID+".jpg"]

    folder_name = shot_date
    try:
        thresholds = _validate_thresholds(t1, t2, t3)
        createSaveFolder(folder_name)
        captureImages(captureAndDownloadCommand, picID)
        original_path = os.path.abspath(picID + ".jpg")
        ppb_overrides = {
            "w_reject": w_reject,
            "w_grade_d": w_grade_d,
            "w_grade_c": w_grade_c,
        }
        result = await grade_using_cv(original_path, thresholds=thresholds, ppb_overrides=ppb_overrides)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.chdir(prev_cwd)

    # return FileResponse(picID+".jpg")
    # return {"image_path": os.path.abspath(picID+".jpg")}


@app.get("/gradeImage")
async def grade_image(
    image_path: str,
    t1: int = 150,
    t2: int = 160,
    t3: int = 168,
    w_reject: Union[float, None] = None,
    w_grade_d: Union[float, None] = None,
    w_grade_c: Union[float, None] = None,
):
    try:
        thresholds = _validate_thresholds(t1, t2, t3)
        ppb_overrides = {
            "w_reject": w_reject,
            "w_grade_d": w_grade_d,
            "w_grade_c": w_grade_c,
        }
        result = await grade_using_cv(image_path, thresholds=thresholds, ppb_overrides=ppb_overrides)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}

@app.get("/openImage")
def open_image(image_path: str):
    try:
        if image_path is None or image_path.strip() == "" or image_path.strip().lower() == "null":
            raise HTTPException(status_code=400, detail="image_path is required")
        # Open the image using OpenCV
        image = cv2.imread(image_path)
        if image is None:
            raise HTTPException(status_code=404, detail="Image not found")

        return FileResponse(image_path)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))