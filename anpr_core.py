"""ANPR image pipeline adapted from the supplied project.

Detection: OpenCV contour-based plate proposals (or optional YOLO weights)
OCR: EasyOCR
Validation: Indian registration format, e.g. TN09AB1234
"""
import re
from pathlib import Path

import cv2
import numpy as np

ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
PLATE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$")
STATE_CODES = set(
    "AN AP AR AS BR CH CG DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP "
    "MZ NL OD OR PB PY RJ SK TN TR TS UK UP WB".split()
)
TO_DIGIT = {"O": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}
TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}
_reader = None
_yolo_model = None

def clean_text(raw):
    return re.sub(r"[^A-Z0-9]", "", raw.upper())

def fix_indian_plate(text):
    n = len(text)
    if n < 9 or n > 11:
        return None
    series_len = n - 8
    kinds = "LLDD" + "L" * series_len + "DDDD"
    out = []
    for ch, kind in zip(text, kinds):
        if kind == "L":
            ch = TO_LETTER.get(ch, ch) if ch.isdigit() else ch
            if not ch.isalpha():
                return None
        else:
            ch = TO_DIGIT.get(ch, ch) if ch.isalpha() else ch
            if not ch.isdigit():
                return None
        out.append(ch)
    fixed = "".join(out)
    return fixed if PLATE_RE.match(fixed) else None

def format_plate(plate):
    if PLATE_RE.match(plate):
        return f"{plate[:2]} {plate[2:4]} {plate[4:-4]} {plate[-4:]}"
    return plate

def get_reader():
    global _reader
    if _reader is None:
        try:
            import easyocr
        except ImportError as exc:
            raise ImportError("EasyOCR is not installed. Run: pip install -r requirements.txt") from exc
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader

def preprocess_plate(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    h = gray.shape[0]
    if h and h < 80:
        scale = 80.0 / h
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)

def ocr_crop(crop, reader):
    results = reader.readtext(preprocess_plate(crop), allowlist=ALLOWLIST, detail=1, paragraph=False)
    if not results:
        return "", 0.0
    items = []
    for box, text, conf in results:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((float(np.mean(ys)), float(min(xs)), max(ys)-min(ys), text, conf))
    items.sort(key=lambda item: item[0])
    med_h = float(np.median([item[2] for item in items])) or 1.0
    lines, current = [], [items[0]]
    for item in items[1:]:
        if item[0] - current[-1][0] > 0.6 * med_h:
            lines.append(current)
            current = [item]
        else:
            current.append(item)
    lines.append(current)
    ordered = []
    for line in lines:
        ordered.extend(sorted(line, key=lambda item: item[1]))
    return clean_text("".join(item[3] for item in ordered)), float(np.mean([item[4] for item in ordered]))

def classic_candidates(img, max_candidates=6):
    height, width = img.shape[:2]
    scale = 800.0 / width if width > 800 else 1.0
    small = cv2.resize(img, None, fx=scale, fy=scale) if scale != 1.0 else img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(gray, 30, 200)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:40]
    small_area = small.shape[0] * small.shape[1]
    boxes = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4:
            continue
        x, y, w, h = cv2.boundingRect(approx)
        if h == 0:
            continue
        aspect = w / float(h)
        area_frac = (w * h) / float(small_area)
        if 1.2 <= aspect <= 6.5 and 0.002 <= area_frac <= 0.25:
            boxes.append((x, y, w, h))
    output = []
    for x, y, w, h in boxes[:max_candidates]:
        pad_x, pad_y = int(0.04*w), int(0.08*h)
        x0 = max(int((x-pad_x)/scale), 0)
        y0 = max(int((y-pad_y)/scale), 0)
        x1 = min(int((x+w+pad_x)/scale), width)
        y1 = min(int((y+h+pad_y)/scale), height)
        output.append((x0, y0, x1-x0, y1-y0))
    return output

def yolo_candidates(img, weights, conf=0.25):
    global _yolo_model
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ImportError("YOLO mode requires ultralytics. Install it with: pip install ultralytics") from exc
    if _yolo_model is None:
        _yolo_model = YOLO(weights)
    prediction = _yolo_model.predict(img, conf=conf, verbose=False)[0]
    height, width = img.shape[:2]
    boxes = []
    for x1, y1, x2, y2 in prediction.boxes.xyxy.cpu().numpy():
        x1, y1 = max(int(x1), 0), max(int(y1), 0)
        x2, y2 = min(int(x2), width), min(int(y2), height)
        boxes.append((x1, y1, x2-x1, y2-y1))
    return boxes

def recognize(img, reader, weights=None):
    boxes = yolo_candidates(img, weights) if weights else classic_candidates(img)
    if not boxes and not weights:
        boxes = [(0, 0, img.shape[1], img.shape[0])]
    best = None
    for x, y, w, h in boxes:
        if w < 20 or h < 8:
            continue
        crop = img[y:y+h, x:x+w]
        raw, confidence = ocr_crop(crop, reader)
        if not raw:
            continue
        fixed = fix_indian_plate(raw)
        valid = fixed is not None
        plate = fixed if valid else raw
        score = confidence + (0.5 if valid else 0.0)
        if valid and plate[:2] in STATE_CODES:
            score += 0.2
        if best is None or score > best["score"]:
            best = {"text": plate, "display": format_plate(plate), "valid": valid,
                    "confidence": confidence, "box": (x, y, w, h), "crop": crop, "score": score}
    return best

def recognize_image(image_path, output_dir, weights=None):
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError("The uploaded file could not be read as an image.")
    result = recognize(image, get_reader(), weights=weights)
    if result is None:
        return None
    annotated = image.copy()
    x, y, w, h = result["box"]
    color = (30, 190, 120) if result["valid"] else (0, 150, 255)
    cv2.rectangle(annotated, (x, y), (x+w, y+h), color, 3)
    label = f'{result["display"]}  |  {result["confidence"]:.0%}'
    cv2.rectangle(annotated, (x, max(0, y-36)), (min(image.shape[1], x+420), y), color, -1)
    cv2.putText(annotated, label, (x+6, max(22, y-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (10, 18, 28), 2)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)
    stem = Path(image_path).stem
    annotated_name = f"{stem}_annotated.jpg"
    crop_name = f"{stem}_plate.jpg"
    cv2.imwrite(str(output_dir / annotated_name), annotated)
    cv2.imwrite(str(output_dir / crop_name), result["crop"])
    return {
        "plate": result["text"], "display": result["display"],
        "valid": bool(result["valid"]), "confidence": float(result["confidence"]),
        "annotated_file": annotated_name, "crop_file": crop_name,
        "seen_at": datetime_now()
    }

def datetime_now():
    from datetime import datetime
    return datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
