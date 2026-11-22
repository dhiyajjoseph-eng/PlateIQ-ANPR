"""PlateIQ: OpenCV plate proposals and OCR.space cloud OCR. No EasyOCR/PyTorch."""
import io
import os
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image, ImageOps

PLATE_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$")
STATE_CODES = set("AN AP AR AS BR CH CG DD DL DN GA GJ HP HR JH JK KA KL LA LD MH ML MN MP MZ NL OD OR PB PY RJ SK TN TR TS UK UP WB".split())
TO_DIGIT = {"O": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}
TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}
API_URL = "https://api.ocr.space/parse/image"

class OCRServiceError(RuntimeError):
    pass

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
    return fixed if PLATE_RE.fullmatch(fixed) and fixed[:2] in STATE_CODES else None

def format_plate(plate):
    if PLATE_RE.fullmatch(plate):
        return f"{plate[:2]} {plate[2:4]} {plate[4:-4]} {plate[-4:]}"
    return plate

def classic_candidates(img, max_candidates=3):
    height, width = img.shape[:2]
    scale = min(1.0, 800.0 / width)
    small = cv2.resize(img, None, fx=scale, fy=scale) if scale < 1 else img
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 17, 17)
    edges = cv2.Canny(gray, 30, 200)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:40]
    boxes = []
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 4: continue
        x, y, w, h = cv2.boundingRect(approx)
        if not h: continue
        area_frac = w * h / float(small.shape[0] * small.shape[1])
        if 1.2 <= w / h <= 6.5 and 0.002 <= area_frac <= 0.25:
            box = (int(x/scale), int(y/scale), int(w/scale), int(h/scale))
            if box not in boxes: boxes.append(box)
        if len(boxes) >= max_candidates: break
    return boxes

def encode_for_api(crop):
    # OCR.space free tier accepts files up to 1 MB; stay comfortably below it.
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    image.thumbnail((1200, 1200))
    for quality in (80, 65, 50, 35):
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        if output.tell() < 900_000:
            return output.getvalue()
    raise OCRServiceError("Image could not be compressed under the OCR API size limit.")

def cloud_ocr(crop):
    api_key = os.environ.get("OCRSPACE_API_KEY", "").strip()
    if not api_key:
        raise OCRServiceError("OCRSPACE_API_KEY is missing from Render environment variables.")
    try:
        response = requests.post(
            API_URL,
            headers={"apikey": api_key},
            data={"language": "eng", "isOverlayRequired": "false", "OCREngine": "2", "scale": "true"},
            files={"file": ("plate.jpg", encode_for_api(crop), "image/jpeg")},
            timeout=(10, 35),
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise OCRServiceError(f"OCR service request failed: {exc}") from exc
    if data.get("IsErroredOnProcessing"):
        message = data.get("ErrorMessage") or data.get("ErrorDetails") or "Unknown OCR error"
        raise OCRServiceError(f"OCR service error: {message}")
    parsed = data.get("ParsedResults") or []
    return " ".join(str(item.get("ParsedText") or "") for item in parsed)

def find_plate(text):
    # OCR may return other text from the vehicle; scan plausible tokens and adjacent words.
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    tokens = re.findall(r"[A-Z0-9]+", text.upper())
    choices = lines + [clean_text("".join(tokens[i:i+n])) for i in range(len(tokens)) for n in (1, 2, 3)]
    for candidate in choices:
        if 9 <= len(candidate) <= 11:
            fixed = fix_indian_plate(candidate)
            if fixed: return fixed, True
    for candidate in choices:
        if 9 <= len(candidate) <= 11:
            return candidate, False
    return "", False

def recognize_image(image_path, output_dir, weights=None):
    if weights:
        raise ValueError("YOLO weights are not supported in the cloud OCR edition.")
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError("The uploaded file could not be read as an image.")
    h, w = image.shape[:2]
    if max(h, w) > 1400:
        ratio = 1400 / max(h, w)
        image = cv2.resize(image, (round(w*ratio), round(h*ratio)), interpolation=cv2.INTER_AREA)
    h, w = image.shape[:2]
    boxes = classic_candidates(image)
    # Use the entire image as fallback; no more than 4 API requests per upload.
    boxes.append((0, 0, w, h))
    best = None
    for x, y, bw, bh in boxes:
        if bw < 20 or bh < 8: continue
        crop = image[y:y+bh, x:x+bw]
        raw = cloud_ocr(crop)
        plate, valid = find_plate(raw)
        if not plate: continue
        # OCR.space doesn't provide a calibrated text confidence in this response.
        candidate = {"text": plate, "display": format_plate(plate), "valid": valid,
                     "confidence": 0.0, "box": (x,y,bw,bh), "crop": crop}
        if best is None or (valid and not best["valid"]): best = candidate
        if valid: break
    if best is None: return None
    annotated = image.copy()
    x, y, bw, bh = best["box"]
    color = (30, 190, 120) if best["valid"] else (0, 150, 255)
    cv2.rectangle(annotated, (x,y), (x+bw,y+bh), color, 3)
    cv2.putText(annotated, best["display"], (max(0,x), max(24,y-10)),
                cv2.FONT_HERSHEY_SIMPLEX, .7, color, 2)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(image_path).stem
    annotated_name, crop_name = f"{stem}_annotated.jpg", f"{stem}_plate.jpg"
    if not cv2.imwrite(str(output_dir / annotated_name), annotated):
        raise OSError("Could not save annotated image")
    if not cv2.imwrite(str(output_dir / crop_name), best["crop"]):
        raise OSError("Could not save plate crop")
    return {"plate": best["text"], "display": best["display"], "valid": best["valid"],
            "confidence": 0.0, "annotated_file": annotated_name, "crop_file": crop_name,
            "seen_at": datetime.now().strftime("%d %b %Y, %I:%M:%S %p")}
