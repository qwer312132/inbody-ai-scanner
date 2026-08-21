# test_main.py
import pytest
import os
import csv
import sqlite3
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app
from db.database import init_db, DB_FILE

client = TestClient(app)

# ==========================================
# 準備測試環境：在執行測試前建立乾淨的資料庫
# ==========================================

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """
    這個 Fixture 會在每個測試函數執行前自動觸發。
    tmp_path 是 pytest 內建的工具，會自動在你的系統暫存區建立一個用完即丟的乾淨資料夾。
    """
    # 1. 在暫存資料夾中建立一個假的資料庫路徑
    test_db_path = str(tmp_path / "test_inbody.db")
    
    # 2. 備份原本真正的 sqlite3.connect 函數
    original_connect = sqlite3.connect
    
    # 3. 寫一個假的連線函數：無論程式要求連哪個檔案，都強制導向我們的暫存庫
    def mock_connect(database, *args, **kwargs):
        return original_connect(test_db_path, *args, **kwargs)
        
    # 4. 使用 patch 攔截全局的 sqlite3.connect
    with patch("sqlite3.connect", side_effect=mock_connect):
        
        # 5. 在暫存資料庫中初始化資料表 (這裡會觸發 init_db 建表指令)
        from db.database import init_db
        init_db()
        
        # 把控制權交還給測試函數開始跑測試
        yield 
        
        # 測試跑完後，pytest 會自動把 tmp_path 整個銷毀，不會留下任何垃圾檔案

# ==========================================
# 測試案例 1：測試分析 API (成功情境)
# ==========================================
# 使用 @patch 攔截 run_inbody_analysis，讓它不要真的跑 YOLO
@patch("main.run_inbody_analysis")
def test_analyze_video_success(mock_run_analysis):
    # 設定當 main.py 呼叫 run_inbody_analysis 時，直接回傳這個假資料
    mock_run_analysis.return_value = {
        "Weight": 75.5,
        "BMI": 23.4,
        "Body Fat": 15.2,
        "Visceral Fat": 5.0,
        "BMR": 1650.0,
        "Body Age": 28.0,
        "Subcutaneous Fat (Whole Body)": 10.5,
        "Subcutaneous Fat (Trunk)": 5.2,
        "Subcutaneous Fat (Arms)": 1.5,
        "Subcutaneous Fat (Legs)": 3.8,
        "Skeletal Muscle (Whole Body)": 35.2,
        "Skeletal Muscle (Trunk)": 20.1,
        "Skeletal Muscle (Arms)": 4.5,
        "Skeletal Muscle (Legs)": 10.6
    }

    # 模擬上傳一個假的 mp4 檔案與使用者名稱
    # 準備一個假的檔案內容 (在記憶體中)
    fake_video_content = b"fake video data"
    
    response = client.post(
        "/api/analyze",
        data={"user_name": "TestUser123"},
        files={"file": ("test_video.mp4", fake_video_content, "video/mp4")}
    )

    # 驗證結果
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "TestUser123" in data["message"]
    assert data["data"]["Weight"] == 75.5

# ==========================================
# 測試案例 2：測試分析 API (格式錯誤防呆)
# ==========================================
def test_confirm_measurement_saves_user_edited_values():
    response = client.post(
        "/api/measurements/confirm",
        json={"user_name": "TestUser123", "data": {"Weight": 70.2, "BMI": 22.1}},
    )

    assert response.status_code == 200
    records = client.get("/api/records/TestUser123").json()["history"]
    assert len(records) == 1
    assert records[0]["weight"] == 70.2
    assert records[0]["bmi"] == 22.1


def test_confirming_changed_measurement_archives_video(tmp_path, monkeypatch):
    import main

    video_path = tmp_path / "source.mp4"
    video_path.write_bytes(b"video")
    hard_examples_dir = tmp_path / "hard_examples"
    monkeypatch.setattr(main, "HARD_EXAMPLES_DIR", hard_examples_dir)
    monkeypatch.setattr(main, "HARD_EXAMPLES_VIDEOS_DIR", hard_examples_dir / "videos")
    monkeypatch.setattr(main, "HARD_EXAMPLES_CSV", hard_examples_dir / "corrections.csv")
    main.pending_analyses["changed-video"] = {
        "file_path": str(video_path),
        "data": {"Weight": 75.5, "BMI": 23.4},
    }

    response = client.post(
        "/api/measurements/confirm",
        json={
            "user_name": "TestUser123",
            "request_id": "changed-video",
            "data": {"Weight": 70.2, "BMI": 23.4},
        },
    )

    assert response.status_code == 200
    assert response.json()["archived"] is True
    assert not video_path.exists()
    archived_videos = list((tmp_path / "hard_examples" / "videos").glob("*.mp4"))
    assert len(archived_videos) == 1
    with (tmp_path / "hard_examples" / "corrections.csv").open(encoding="utf-8-sig") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert len(rows) == 1
    assert rows[0]["modified_fields"] == "Weight"
    assert rows[0]["predicted_Weight"] == "75.5"
    assert rows[0]["reviewed_Weight"] == "70.2"


def test_analyze_invalid_file_format():
    # 模擬上傳一張圖片，預期會被擋下來
    fake_image_content = b"fake image data"
    
    response = client.post(
        "/api/analyze",
        data={"user_name": "TestUser123"},
        files={"file": ("test_image.jpg", fake_image_content, "image/jpeg")}
    )

    assert response.status_code == 400
    assert response.json()["error"] == "只支援影片格式"

# ==========================================
# 測試案例 3：測試歷史紀錄 API
# ==========================================
def test_get_user_records():
    # 先呼叫原本的 API 寫入一筆資料
    test_user = "TestUserHistory"
    
    # 建立連線，手動塞一筆假資料進資料庫
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (name) VALUES (?)", (test_user,))
    cursor.execute("SELECT id FROM users WHERE name = ?", (test_user,))
    user_id = cursor.fetchone()[0]
    
    cursor.execute('''
        INSERT INTO measurements (user_id, weight, bmi, body_fat)
        VALUES (?, ?, ?, ?)
    ''', (user_id, 80.0, 25.0, 20.0))
    conn.commit()
    conn.close()

    # 測試讀取 API
    response = client.get(f"/api/records/{test_user}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"] == test_user
    assert len(data["history"]) >= 1
    # 檢查我們剛剛塞進去的體重資料是否正確被撈出
    assert any(record["weight"] == 80.0 for record in data["history"])
