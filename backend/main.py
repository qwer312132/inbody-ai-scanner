from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import shutil
import os
from uuid import uuid4

# 🚀 匯入我們剛寫好的 AI 模組
from inbody_analyzer import run_inbody_analysis

app = FastAPI(title="InBody AI Scanner API")

UPLOAD_DIR = "temp_videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "InBody AI Scanner Backend is running!"}

@app.post("/api/analyze")
async def analyze_video(file: UploadFile = File(...)):
    if not file.filename.endswith(('.mp4', '.avi', '.mov')):
        return JSONResponse(status_code=400, content={"error": "只支援 mp4, avi, mov 格式影片"})

    unique_filename = f"{uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        # 1. 儲存影片
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. 呼叫 YOLO 分析器 (會花一段時間在這裡計算)
        parsed_data = run_inbody_analysis(file_path)
        
        # 3. 如果回傳的字典是空的，代表影片可能拍太差或太短
        if not parsed_data:
            return JSONResponse(status_code=422, content={
                "status": "failed",
                "message": "無法從影片中解析出足夠穩定的數據，請重新拍攝。"
            })
        
        # 4. 成功回傳結果
        return {
            "status": "success",
            "message": "影片分析成功！",
            "data": parsed_data
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
        
    finally:
        file.file.close()
        
        # 5. 分析結束後，把暫存影片砍掉，保持硬碟乾淨
        if os.path.exists(file_path):
            os.remove(file_path)