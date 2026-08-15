import cv2
import numpy as np
import logging
import time
from collections import defaultdict, Counter
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ultralytics import YOLO

logger = logging.getLogger("inbody.analyzer")

# Resolve from this file rather than the process working directory.
MODEL_PATH = Path(__file__).resolve().parent / "weight" / "best.pt"


@lru_cache(maxsize=1)
def get_model() -> Any:
    """Load the YOLO weights on first inference, then reuse that instance."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO model weights were not found at {MODEL_PATH}. "
            "Set up ai/weight/best.pt before submitting an analysis request."
        )

    logger.info("Loading YOLO model from %s", MODEL_PATH)
    # Keep this import here as well: API-only CI tests do not require the
    # inference package or its PyTorch dependency.
    from ultralytics import YOLO

    return YOLO(str(MODEL_PATH))

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

# A single video has frames with the same dimensions, so YOLO can infer several
# frames together.  Tune this down on low-memory GPUs if necessary.
INFERENCE_BATCH_SIZE = 8

# 所有 API 與資料庫會使用的 InBody 欄位。未辨識到時以 -1 表示。
EXPECTED_MODES = (
    'Weight', 'BMI', 'Body Fat', 'Visceral Fat', 'BMR', 'Body Age',
    *(f'{main} {part}' for main in COMP_MAIN for part in COMP_PART),
)

def run_inbody_analysis(
    video_path: str,
    request_id: str = "-",
    progress_callback: Callable[[int, int, float], None] | None = None,
) -> dict:
    """
    接收影片路徑，執行 YOLO 推論，回傳最終聚合的數據字典。
    """
    # Importing this module (for example in CI API tests) must not require
    # model weights; load them only when an analysis is requested.
    model = get_model()
    cap = cv2.VideoCapture(video_path)
    final_report = defaultdict(list)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = 0
    analysis_started = time.perf_counter()

    if not cap.isOpened():
        raise ValueError(f"Unable to open video: {video_path}")

    logger.info(
        "[%s] Video opened: frames=%s, fps=%.2f",
        request_id, total_frames if total_frames > 0 else "unknown", fps,
    )
    if progress_callback:
        progress_callback(0, total_frames, 0)

    batch_results = iter(())
    while cap.isOpened():
        try:
            frame, result = next(batch_results)
        except StopIteration:
            frames = []
            for _ in range(INFERENCE_BATCH_SIZE):
                success, frame = cap.read()
                if not success:
                    break
                frames.append(frame)

            if not frames:
                break

            if frame_number == 0:
                logger.info(
                    "[%s] Running YOLO inference in batches of %d frames",
                    request_id, INFERENCE_BATCH_SIZE,
                )

            results = model.predict(
                frames, conf=0.5, imgsz=1088, agnostic_nms=True, verbose=False,
            )
            batch_results = iter(zip(frames, results))
            frame, result = next(batch_results)

        frame_number += 1
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

        if frame_number % 30 == 0:
            elapsed_seconds = time.perf_counter() - analysis_started
            progress = f"{frame_number / total_frames:.0%}" if total_frames > 0 else "unknown"
            logger.info(
                "[%s] Analysis progress: frame %d/%s (%s), elapsed %.1f s",
                request_id, frame_number,
                total_frames if total_frames > 0 else "?", progress,
                elapsed_seconds,
            )
            if progress_callback:
                progress_callback(frame_number, total_frames, elapsed_seconds)

    cap.release()
    logger.info(
        "[%s] Finished reading %d frames in %.2f s",
        request_id, frame_number, time.perf_counter() - analysis_started,
    )
    if progress_callback:
        progress_callback(frame_number, total_frames, time.perf_counter() - analysis_started)
    # 🚀 關鍵 2：拔除 cv2.imshow，改為純資料返回

    # ==========================================
    # 開票統計並轉為 JSON 友善的字典格式
    # ==========================================
    MIN_VOTES = 0
    # 先填入完整欄位，避免未辨識到的項目從 JSON 中消失。
    report_data = {mode: -1 for mode in EXPECTED_MODES}
    
    for mode, values in final_report.items():
        most_common_val, count = Counter(values).most_common(1)[0]
        if count >= MIN_VOTES:
            # 嘗試轉換為浮點數，如果失敗（例如 --）則保持字串
            try:
                report_data[mode] = float(most_common_val)
            except ValueError:
                report_data[mode] = most_common_val

    return report_data
