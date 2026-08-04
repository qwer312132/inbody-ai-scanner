import sqlite3
import os

DB_FILE = "db/inbody_records.db"

def init_db():
    """初始化資料庫與資料表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 1. 建立使用者表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    # 2. 建立測量紀錄表 (加上 user_id 作為外鍵)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            record_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            -- 基本數據 --
            weight REAL,
            bmi REAL,
            body_fat REAL,
            visceral_fat REAL,
            bmr REAL,
            body_age REAL,
            
            -- 皮下脂肪 (Subcutaneous Fat) --
            subfat_whole REAL,
            subfat_trunk REAL,
            subfat_arms REAL,
            subfat_legs REAL,
            
            -- 骨骼肌 (Skeletal Muscle) --
            muscle_whole REAL,
            muscle_trunk REAL,
            muscle_arms REAL,
            muscle_legs REAL,
            
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # 預先塞入幾個家人名單供測試
    try:
        cursor.execute("INSERT INTO users (name) VALUES ('爸爸'), ('媽媽'), ('我')")
    except sqlite3.IntegrityError:
        pass # 如果已經存在就忽略

    conn.commit()
    conn.close()
    print("✅ 資料庫初始化完成！")

if __name__ == "__main__":
    init_db()