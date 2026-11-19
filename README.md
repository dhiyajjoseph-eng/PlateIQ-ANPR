# PlateIQ · ANPR Web Application

A local web interface for the supplied Automatic Number Plate Recognition project.
It uses OpenCV contour proposals, EasyOCR, Indian registration-format validation and SQLite history.

## 1. Requirements
- Python 3.10–3.12 recommended
- Windows, macOS or Linux
- Internet connection for the first EasyOCR model download

## 2. Setup (Windows PowerShell)

```powershell
cd anpr_web_app
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. Setup (macOS / Linux)

```bash
cd anpr_web_app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

## 4. Features
- Image upload for JPG, JPEG, PNG, WEBP and BMP
- OpenCV contour-based plate candidate detection
- EasyOCR text extraction
- Indian plate structure validation (example: TN09AB1234)
- Annotated result image and cropped plate image
- SQLite detection history with search and delete
- Dashboard statistics

## 5. Important notes
- The first recognition may take longer because EasyOCR downloads its language model.
- The current version processes still images. Video and live camera streaming are not included yet.
- Classic contour detection is a baseline and may miss plates in poor lighting, at long distance or at unusual angles.
- A trained YOLO number-plate detector can improve detection. Add your weights file and wire the optional `weights` argument in `app.py`.
- OCR confidence is not a guarantee that a registration number is correct. Verify results manually.
- This is a prototype. Use only images/cameras you are authorized to process. Add authentication, access controls, secure storage, retention rules and HTTPS before exposing it to a network or public internet.
- Do not use this prototype as the sole basis for enforcement or other high-impact decisions.

## 6. Troubleshooting
- `No module named cv2`: activate the virtual environment and run `pip install -r requirements.txt`.
- EasyOCR / PyTorch installation issues: use Python 3.10 or 3.11 in a fresh virtual environment.
- `No readable number plate`: try a sharp, well-lit, close-up image with the plate occupying a reasonable part of the frame.
- Port 5000 already in use: stop the other app or change the port in `app.py`.
