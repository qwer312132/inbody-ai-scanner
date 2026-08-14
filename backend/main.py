from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import sqlite3
import logging
import time
from uuid import uuid4
from datetime import datetime
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
    file: UploadFile = File(...)
):
    request_id = uuid4().hex[:8]
    request_started = time.perf_counter()
    logger.info(
        "[%s] Request received: user=%r, filename=%r, content_type=%r",
        request_id, user_name, file.filename, file.content_type,
    )
    if not file.filename.endswith(('.mp4', '.avi', '.mov')):
        return JSONResponse(status_code=400, content={"error": "只支援影片格式"})

    unique_filename = f"{uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

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
        parsed_data = run_inbody_analysis(file_path, request_id=request_id)
        logger.info("[%s] AI analysis finished in %.2f s", request_id, time.perf_counter() - analysis_started)
        
        if not parsed_data:
            return JSONResponse(status_code=422, content={"status": "failed", "message": "辨識失敗"})
        
        # 🚀 將數據與使用者名稱綁定，寫入資料庫
        logger.info("[%s] Saving analysis result to database", request_id)
        insert_measurement(user_name, parsed_data)
        logger.info("[%s] Request complete in %.2f s", request_id, time.perf_counter() - request_started)
        
        return {
            "status": "success",
            "message": f"分析完成！已將數據記錄至 {user_name} 的名下。",
            "data": parsed_data
        }

    except Exception as e:
        logger.exception("[%s] Request failed after %.2f s", request_id, time.perf_counter() - request_started)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        file.file.close()
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("[%s] Temporary video removed", request_id)

# 🚀 新增：提供給前端畫圖用的歷史紀錄 API
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
app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
@app.get("/")
def read_index():
    return FileResponse("dist/index.html")

# 3. (選用) 如果 Vue 有使用 Vue Router 的 history 模式，建議加上這段捕捉所有其他路由
@app.get("/{catchall:path}")
def serve_vue_router(catchall: str):
    return FileResponse("dist/index.html")
