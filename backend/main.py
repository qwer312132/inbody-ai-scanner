from fastapi import FastAPI, File, UploadFile, Form, Body, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import sqlite3
import csv
import logging
import time
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
# 匯入 AI 模組與資料庫設定
from ai.inbody_analyzer import run_inbody_analysis
from db.database import DB_FILE, init_db
from fastapi.responses import FileResponse
app = FastAPI(title="InBody AI Scanner API")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("inbody.api")

# This keeps progress for the local single-process server.  Use Redis or a job
# queue if the app is later deployed with multiple backend workers.
analysis_progress: dict[str, dict] = {}
# Video files are kept only until the user confirms the reviewed values.  The
# mapping is intentionally server-side so the client cannot choose an
# arbitrary path to archive.
pending_analyses: dict[str, dict] = {}

MEASUREMENT_FIELDS = {
    "Weight", "BMI", "Body Fat", "Visceral Fat", "BMR", "Body Age",
    "Subcutaneous Fat (Whole Body)", "Subcutaneous Fat (Trunk)",
    "Subcutaneous Fat (Arms)", "Subcutaneous Fat (Legs)",
    "Skeletal Muscle (Whole Body)", "Skeletal Muscle (Trunk)",
    "Skeletal Muscle (Arms)", "Skeletal Muscle (Legs)",
}


def validate_measurement(data: dict) -> dict:
    unexpected_fields = set(data) - MEASUREMENT_FIELDS
    if unexpected_fields:
        raise HTTPException(status_code=422, detail="Unsupported measurement field")

    normalized = {}
    for field, value in data.items():
        if value is None or value == "":
            normalized[field] = None
            continue
        if isinstance(value, bool):
            raise HTTPException(status_code=422, detail=f"{field} must be a number")
        try:
            normalized[field] = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{field} must be a number") from exc
    return normalized


def update_analysis_progress(
    request_id: str,
    frame_number: int = 0,
    total_frames: int = 0,
    elapsed_seconds: float = 0,
    stage: str = "analyzing",
) -> None:
    progress = round((frame_number / total_frames) * 100) if total_frames > 0 else None
    analysis_progress[request_id] = {
        "stage": stage,
        "progress": progress,
        "frame": frame_number,
        "total_frames": total_frames,
        "elapsed_seconds": round(elapsed_seconds, 1),
    }

# 添加 CORS 中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有 HTTP 方法
    allow_headers=["*"],  # 允許所有請求頭
)

UPLOAD_DIR = "temp_videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)
HARD_EXAMPLES_DIR = Path(__file__).resolve().parent / "hard_examples"
HARD_EXAMPLES_VIDEOS_DIR = HARD_EXAMPLES_DIR / "videos"
HARD_EXAMPLES_CSV = HARD_EXAMPLES_DIR / "corrections.csv"
HARD_EXAMPLES_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# 伺服器啟動時，自動確保資料庫存在
init_db()

def insert_measurement(user_name: str, data: dict):
    """將解析後的數據完整寫入 SQLite"""
    conn = sqlite3.connect(DB_FILE) # 請確認路徑
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE name = ?", (user_name,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("INSERT INTO users (name) VALUES (?)", (user_name,))
        user_id = cursor.lastrowid
    else:
        user_id = user[0]

    # Keep only the newest measurement for each user on the current local day.
    cursor.execute('''
        DELETE FROM measurements
        WHERE user_id = ?
          AND DATE(record_time, 'localtime') = DATE('now', 'localtime')
    ''', (user_id,))

    # 對應 YOLO 字典的 Key，取出數值。若未辨識到則預設存入 None (SQL 的 NULL)
    cursor.execute('''
        INSERT INTO measurements (
            user_id, weight, bmi, body_fat, visceral_fat, bmr, body_age,
            subfat_whole, subfat_trunk, subfat_arms, subfat_legs,
            muscle_whole, muscle_trunk, muscle_arms, muscle_legs
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        data.get('Weight'),
        data.get('BMI'),
        data.get('Body Fat'),
        data.get('Visceral Fat'),
        data.get('BMR'),
        data.get('Body Age'),
        
        # 皮下脂肪
        data.get('Subcutaneous Fat (Whole Body)'),
        data.get('Subcutaneous Fat (Trunk)'),
        data.get('Subcutaneous Fat (Arms)'),
        data.get('Subcutaneous Fat (Legs)'),
        
        # 骨骼肌
        data.get('Skeletal Muscle (Whole Body)'),
        data.get('Skeletal Muscle (Trunk)'),
        data.get('Skeletal Muscle (Arms)'),
        data.get('Skeletal Muscle (Legs)')
    ))
    
    conn.commit()
    conn.close()


def get_modified_fields(original_data: dict, reviewed_data: dict) -> list[str]:
    """Return the fields whose reviewed numeric value differs from the AI result."""
    return [
        field
        for field, value in reviewed_data.items()
        if field in original_data and value != original_data[field]
    ]


def archive_hard_example(video_path: str) -> Path:
    """Move a corrected video to hard_examples/videos with a timestamp name."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    source = Path(video_path)
    video_dir = Path(HARD_EXAMPLES_VIDEOS_DIR)
    video_dir.mkdir(parents=True, exist_ok=True)
    destination = video_dir / f"{timestamp}_{uuid4().hex[:8]}{source.suffix.lower()}"
    shutil.move(str(source), destination)
    return destination


def write_hard_example_record(
    archived_video: Path,
    user_name: str,
    original_data: dict,
    reviewed_data: dict,
    modified_fields: list[str],
) -> None:
    """Append the AI prediction and user-reviewed data for one hard example."""
    csv_path = Path(HARD_EXAMPLES_CSV)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "recorded_at", "video_path", "user_name", "modified_fields",
        *[f"predicted_{field}" for field in sorted(MEASUREMENT_FIELDS)],
        *[f"reviewed_{field}" for field in sorted(MEASUREMENT_FIELDS)],
    ]
    row = {
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "video_path": archived_video.relative_to(Path(HARD_EXAMPLES_DIR)).as_posix(),
        "user_name": user_name,
        "modified_fields": "|".join(modified_fields),
    }
    row.update({f"predicted_{field}": original_data.get(field) for field in MEASUREMENT_FIELDS})
    row.update({f"reviewed_{field}": reviewed_data.get(field) for field in MEASUREMENT_FIELDS})

    has_header = csv_path.exists() and csv_path.stat().st_size > 0
    with csv_path.open("a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if not has_header:
            writer.writeheader()
        writer.writerow(row)

# ==========================================
# API 路由
# ==========================================
# @app.get("/")
# def read_root():
#     return {"message": "InBody AI Scanner Backend is running!"}

# 🚀 修改：加入 user_name 作為 Form 表單參數
@app.post("/api/analyze")
async def analyze_video(
    user_name: str = Form(...), 
    file: UploadFile = File(...),
    request_id: str | None = Form(None),
):
    request_id = request_id or uuid4().hex[:8]
    request_started = time.perf_counter()
    update_analysis_progress(request_id, stage="saving")
    logger.info(
        "[%s] Request received: user=%r, filename=%r, content_type=%r",
        request_id, user_name, file.filename, file.content_type,
    )
    if not file.filename.endswith(('.mp4', '.avi', '.mov')):
        return JSONResponse(status_code=400, content={"error": "只支援影片格式"})

    unique_filename = f"{uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    parsed_data = None

    try:
        logger.info("[%s] Saving uploaded video", request_id)
        save_started = time.perf_counter()
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        logger.info("[%s] Upload saved: %.2f MB in %.2f s", request_id, file_size_mb, time.perf_counter() - save_started)
            
        # 呼叫 YOLO 進行分析
        logger.info("[%s] Starting AI analysis", request_id)
        analysis_started = time.perf_counter()
        parsed_data = await run_in_threadpool(
            run_inbody_analysis,
            file_path,
            request_id,
            lambda frame, total, elapsed: update_analysis_progress(
                request_id, frame, total, elapsed,
            ),
        )
        logger.info("[%s] AI analysis finished in %.2f s", request_id, time.perf_counter() - analysis_started)
        
        if not parsed_data:
            return JSONResponse(status_code=422, content={"status": "failed", "message": "辨識失敗"})
        
        # 🚀 將數據與使用者名稱綁定，寫入資料庫
        analysis_progress[request_id]["stage"] = "completed"
        logger.info("[%s] Request complete in %.2f s", request_id, time.perf_counter() - request_started)
        
        return {
            "status": "success",
            "message": f"分析完成！已將數據記錄至 {user_name} 的名下。",
            "data": parsed_data,
            "request_id": request_id,
        }

    except Exception as e:
        analysis_progress[request_id] = {"stage": "failed", "progress": None}
        logger.exception("[%s] Request failed after %.2f s", request_id, time.perf_counter() - request_started)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        file.file.close()
        # A successful analysis must stay available until the user either
        # confirms it unchanged (delete) or corrects it (archive).
        if parsed_data:
            pending_analyses[request_id] = {
                "file_path": file_path,
                "data": parsed_data,
            }
        elif os.path.exists(file_path):
            os.remove(file_path)
            logger.info("[%s] Temporary video removed", request_id)

# 🚀 新增：提供給前端畫圖用的歷史紀錄 API
@app.get("/api/analyze/{request_id}/progress")
def get_analysis_progress(request_id: str):
    """Return the latest in-memory frame progress for one video analysis."""
    return analysis_progress.get(request_id, {"stage": "waiting", "progress": None})


@app.post("/api/measurements/confirm")
async def confirm_measurement(payload: dict = Body(...)):
    """Save a user-reviewed measurement after AI analysis."""
    user_name = payload.get("user_name")
    data = payload.get("data")
    request_id = payload.get("request_id")
    if not isinstance(user_name, str) or not user_name.strip():
        raise HTTPException(status_code=422, detail="user_name is required")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="data must be an object")

    validated_data = validate_measurement(data)
    await run_in_threadpool(insert_measurement, user_name.strip(), validated_data)

    archived_video = None
    pending_analysis = pending_analyses.pop(request_id, None) if isinstance(request_id, str) else None
    if pending_analysis:
        video_path = pending_analysis["file_path"]
        modified_fields = get_modified_fields(pending_analysis["data"], validated_data)
        if modified_fields and os.path.exists(video_path):
            archived_video = await run_in_threadpool(
                archive_hard_example, video_path,
            )
            await run_in_threadpool(
                write_hard_example_record,
                archived_video,
                user_name.strip(),
                pending_analysis["data"],
                validated_data,
                modified_fields,
            )
            logger.info("[%s] Archived corrected video at %s", request_id, archived_video)
        elif os.path.exists(video_path):
            os.remove(video_path)
            logger.info("[%s] Temporary video removed after unchanged confirmation", request_id)

    return {
        "status": "success",
        "message": "Measurement saved.",
        "archived": archived_video is not None,
    }


@app.get("/api/records/{user_name}")
def get_user_records(user_name: str):
    conn = sqlite3.connect(DB_FILE)
    # 將查詢結果轉換為字典格式，方便轉成 JSON
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.record_time, m.weight, m.bmi, m.body_fat, m.visceral_fat, m.bmr, m.body_age,
               m.subfat_whole, m.subfat_trunk, m.subfat_arms, m.subfat_legs,
               m.muscle_whole, m.muscle_trunk, m.muscle_arms, m.muscle_legs
        FROM measurements m
        JOIN users u ON m.user_id = u.id
        WHERE u.name = ?
        ORDER BY m.record_time ASC
    ''', (user_name,))
    
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"user": user_name, "history": records}
FRONTEND_DIST_DIR = Path(__file__).resolve().parent / "dist"

# The backend API can run independently of a locally built frontend.  This is
# important for API-only CI tests, where ``dist/`` is intentionally ignored.
app.mount(
    "/assets",
    StaticFiles(directory=FRONTEND_DIST_DIR / "assets", check_dir=False),
    name="assets",
)
@app.get("/")
def read_index():
    return FileResponse(FRONTEND_DIST_DIR / "index.html")

# 3. (選用) 如果 Vue 有使用 Vue Router 的 history 模式，建議加上這段捕捉所有其他路由
@app.get("/{catchall:path}")
def serve_vue_router(catchall: str):
    return FileResponse(FRONTEND_DIST_DIR / "index.html")
