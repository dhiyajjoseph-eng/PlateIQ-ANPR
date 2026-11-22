# PlateIQ 🚘 | Automatic Number Plate Recognition

**PlateIQ** is a Flask-based web application that detects candidate vehicle registration plates in uploaded images, extracts text using the OCR.space cloud OCR API, validates Indian registration-number formats, and displays annotated results and detection history.

**Live demo:** https://plateiq-anpr.onrender.com  
**Repository:** https://github.com/dhiyajjoseph-eng/PlateIQ-ANPR

> **Project status:** Cloud OCR version deployed on Render; a successful recognition was observed for `KA 02 MP 9657`. This is a prototype, not a production-grade traffic enforcement system.

## Features

- Upload JPG, JPEG, PNG, WEBP or BMP images (Flask upload limit: **5 MB**).
- Detect possible number-plate regions using OpenCV contours.
- Extract text using **OCR.space API** rather than local EasyOCR/PyTorch.
- Normalize common OCR letter/digit substitutions and validate Indian registration patterns.
- Show an annotated vehicle image, cropped plate and formatted result.
- Store and search detection records in SQLite; display dashboard statistics.
- Provide a `/health` endpoint for deployment checks.

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, Jinja2 templates |
| Backend | Python, Flask |
| Image processing | OpenCV, NumPy, Pillow |
| OCR | OCR.space API (Engine 2) via Requests |
| Database | SQLite |
| Hosting | Render, Gunicorn |
| Version control | Git, GitHub |

## Processing workflow

```text
User uploads image
       |
       v
Flask validates file type and saves temporary upload
       |
       v
OpenCV resizes image and proposes plate-like regions
       |
       v
Candidate crops compressed to JPEG (< 900 KB each)
       |
       v
OCR.space cloud API extracts text
       |
       v
Text normalization + Indian registration-format validation
       |
       v
Annotated image + cropped plate saved to results/
       |
       v
SQLite history updated; result shown in browser
```

The implementation tries up to three contour candidates, followed by whole-image OCR if needed. It stops early on a valid plate. Each upload can therefore make up to **four OCR API requests**.

## Project structure

```text
PlateIQ-ANPR/
├── app.py                  # Flask routes and upload handling
├── anpr_core.py            # OpenCV proposals, OCR API, plate validation
├── database.py             # SQLite history and statistics
├── requirements.txt        # Python dependencies
├── .env.example            # Names of required environment variables
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── detect.html
│   └── history.html
├── static/
│   └── style.css
├── uploads/                # Temporary uploads (removed after processing)
└── results/                # Annotated images and plate crops
```

## Local setup

1. Install a supported Python version and create a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables. Never commit real credentials.

   **PowerShell:**
   ```powershell
   $env:OCRSPACE_API_KEY="YOUR_PRIVATE_API_KEY"
   $env:SECRET_KEY="YOUR_LONG_RANDOM_SECRET"
   python app.py
   ```

4. Visit http://127.0.0.1:5000 and upload a clear vehicle image.

Get an API key at https://ocr.space/ocrapi/freekey. Uploaded image crops are sent to that third-party service.

## Render deployment

1. Connect the GitHub repository to a Render **Web Service**.
2. Set **Build Command** to `pip install -r requirements.txt`.
3. Set **Start Command** to:

   ```bash
   gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 180 --max-requests 50 --max-requests-jitter 5
   ```

4. Under **Environment**, set `OCRSPACE_API_KEY` and `SECRET_KEY`.
5. Deploy and verify `/health` returns `{"service":"ANPR web app","status":"ok"}`.
6. Test `/detect` with a permitted, clear image.

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Dashboard and recent detections |
| `GET /detect` | Upload form |
| `POST /detect` | Run plate recognition |
| `GET /history` | Search history |
| `POST /history/<id>/delete` | Delete a history record |
| `GET /results/<filename>` | Serve generated images |
| `GET /health` | Basic service health check |

## Validation and accuracy

The validator expects a registration resembling `TN09AB1234` (two state letters, two digits, one to three series letters, four digits) and checks recognized state/UT codes. It applies a limited set of character substitutions, such as `O` ↔ `0` and `I` ↔ `1`.

**A valid-looking registration is not proof of vehicle identity.** OCR accuracy varies with blur, lighting, angle, obstruction, plate design and background text. No benchmark accuracy or precision/recall figure has been established for this prototype.

## Known limitations

- **Cloud dependency:** OCR needs network access and a valid OCR.space key; the API has usage, size and latency limits.
- **Privacy:** Candidate image crops are transmitted to OCR.space. Obtain consent and avoid sensitive uploads.
- **Ephemeral storage:** Render free instances do not provide durable local SQLite/history/image storage across restarts or redeploys.
- **No authentication:** Public history and generated image routes should not be used with sensitive real-world data.
- **Confidence:** OCR.space response is not mapped to a calibrated confidence value; the backend stores `0.0`. Treat confidence displays and averages as unavailable, not actual 0% accuracy.
- **Dashboard count:** The current `today` statistic uses total detections rather than a correctly filtered daily count; this should be fixed before presenting it as a daily metric.
- **Heuristic detection:** OpenCV contours can miss plates or select non-plate regions; whole-image OCR is a fallback.
- **Scope:** Still images only; no video streaming, CCTV integration or trained YOLO detector in the cloud edition.

## Suggested next improvements

- Move history to a persistent managed database and results to object storage.
- Add authentication, retention policies and access controls.
- Correct daily statistics and replace the confidence indicator with `N/A`.
- Evaluate on a consented dataset with varied lighting and angles; report exact-match accuracy and latency.
- Add better plate localization and test multiple plates per image.

## Responsible use

Use images you own or have permission to process. Vehicle registration data may be personal information depending on context and jurisdiction. Do not use this prototype for automated enforcement or identity decisions without appropriate validation, safeguards and legal review.

## Documentation

See [PROJECT_REPORT.md](PROJECT_REPORT.md) for the detailed project report, architecture, methodology, testing notes and future scope.
