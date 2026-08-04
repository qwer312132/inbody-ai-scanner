import cv2
import numpy as np
from collections import defaultdict, Counter
from ultralytics import YOLO

print("⏳ 正在載入 YOLOv8 模型至記憶體...")
# 🚀 關鍵 1：將模型宣告在全域，伺服器啟動時只載入一次
model = YOLO('ai/weight/best.pt')
print("✅ 模型載入完成！")

# 標籤定義與分類
label_map = {
    'subfat': 'Subcutaneous Fat',
    'muscle': 'Skeletal Muscle',
    'fat': 'Body Fat',
    'visceral': 'Visceral Fat',
    'whole': '(Whole Body)',
    'trunk': '(Trunk)',
    'arm': '(Arms)',
    'leg': '(Legs)',
    'bmi': 'BMI',
    'bmr': 'BMR',
    'weight': 'Weight',
    'age': 'Body Age'
}

SINGLE_MODES = {'Weight', 'Body Fat', 'Visceral Fat', 'BMR', 'BMI', 'Body Age'}
COMP_MAIN = {'Subcutaneous Fat', 'Skeletal Muscle'}
COMP_PART = {'(Whole Body)', '(Trunk)', '(Arms)', '(Legs)'}

def run_inbody_analysis(video_path: str) -> dict:
    """
    接收影片路徑，執行 YOLO 推論，回傳最終聚合的數據字典。
    """
    cap = cv2.VideoCapture(video_path)
    final_report = defaultdict(list)

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        results = model.predict(frame, conf=0.5, imgsz=1088, agnostic_nms=True, verbose=False)
        result = results[0]
        h, w = frame.shape[:2]
        
        raw_digits = []
        detected_modes = []
        
        for box in result.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            box_h = y2 - y1
            
            if cls_name in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'dot']:
                raw_digits.append((center_x, center_y, box_h, cls_name))
            else:
                detected_modes.append(label_map.get(cls_name, cls_name))
                
        # 🚀 小數點分流的 Y 軸錨點過濾邏輯
        digit_boxes = []
        if len(raw_digits) > 0:
            pure_digits = [d for d in raw_digits if d[3] != 'dot']
            dots = [d for d in raw_digits if d[3] == 'dot']
            
            if len(pure_digits) > 0:
                y_values = [d[1] for d in pure_digits]
                median_y = np.median(y_values)
                avg_h = sum(d[2] for d in pure_digits) / len(pure_digits)
                
                threshold = avg_h * 0.6 
                for d in pure_digits:
                    cx, cy, h_box, cls_name = d
                    if abs(cy - median_y) <= threshold:
                        digit_boxes.append((cx, cls_name))
                        
                dot_threshold = avg_h * 0.85 
                for d in dots:
                    cx, cy, h_box, cls_name = d
                    if abs(cy - median_y) <= dot_threshold:
                        digit_boxes.append((cx, cls_name))

        # 狀態機過濾
        singles = [m for m in detected_modes if m in SINGLE_MODES]
        mains = [m for m in detected_modes if m in COMP_MAIN]
        parts = [m for m in detected_modes if m in COMP_PART]
        
        is_valid_frame = False
        current_mode = ""
        
        if len(singles) == 1 and len(mains) == 0 and len(parts) == 0:
            is_valid_frame = True
            current_mode = singles[0]
        elif len(singles) == 0 and len(mains) == 1 and len(parts) == 1:
            is_valid_frame = True
            current_mode = f"{mains[0]} {parts[0]}"

        # 收集選票
        if is_valid_frame:
            digit_boxes.sort(key=lambda x: x[0])
            val_str = ""
            for _, digit in digit_boxes:
                val_str += "." if digit == 'dot' else digit
            
            if val_str != "" and val_str != ".":
                final_report[current_mode].append(val_str)

    cap.release()
    # 🚀 關鍵 2：拔除 cv2.imshow，改為純資料返回

    # ==========================================
    # 開票統計並轉為 JSON 友善的字典格式
    # ==========================================
    MIN_VOTES = 0
    report_data = {}
    
    for mode, values in final_report.items():
        most_common_val, count = Counter(values).most_common(1)[0]
        if count >= MIN_VOTES:
            # 嘗試轉換為浮點數，如果失敗（例如 --）則保持字串
            try:
                report_data[mode] = float(most_common_val)
            except ValueError:
                report_data[mode] = most_common_val

    return report_data