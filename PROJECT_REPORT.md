# PlateIQ: Automatic Number Plate Recognition Web Application

## 1. Abstract

PlateIQ is a web-based Automatic Number Plate Recognition (ANPR) prototype designed to process uploaded vehicle images, identify possible registration-plate regions, recognize alphanumeric text and check whether the result matches common Indian registration formats. It uses Flask for the web application, OpenCV for image-based candidate detection, OCR.space for cloud text recognition and SQLite for detection history. The prototype is deployed to Render and has demonstrated a successful plate recognition. It is intended for educational demonstration and further experimentation, not for enforcement-grade recognition.

## 2. Problem statement

Manually reading and recording vehicle registration numbers is time-consuming and can introduce transcription errors. A web-based image-processing workflow can demonstrate how computer vision and optical character recognition help automate this task. Real-world accuracy is challenged by lighting, angle, blur, plate variations and occlusion.

## 3. Objectives

1. Build an accessible browser interface for still-image uploads.
2. Detect candidate number-plate areas from vehicle images.
3. Extract registration text with OCR.
4. Normalize and validate common Indian registration formats.
5. Display an annotated image, cropped plate and recognition result.
6. Maintain searchable detection history for demonstrations.
7. Deploy the application online with a lightweight server footprint.

## 4. Scope

**Included:** still-image uploads, contour-based plate proposals, cloud OCR, format validation, result visualization, SQLite history and basic dashboard.

**Not included:** live video/CCTV processing, production authentication, persistent managed storage, trained YOLO-based localization, verified ownership lookup or legal enforcement decisions.

## 5. System architecture

```text
Browser (HTML/CSS)
      |
      v
Flask routes (app.py)
      |
      +--> Image validation / temporary upload
      |
      v
ANPR pipeline (anpr_core.py)
      |
      +--> OpenCV resize + grayscale + filtering + Canny edges
      +--> Contour selection + bounding-box proposals
      +--> JPEG compression of candidate crop
      +--> HTTPS request to OCR.space API
      +--> Text cleanup + registration-format check
      +--> Annotated output and cropped plate
      |
      v
SQLite (database.py) --> Dashboard / searchable history
```

The web service runs under Gunicorn on Render. A single worker reduces simultaneous memory use. The OCR model runs on an external API rather than inside the Render instance.

## 6. Technologies

| Component | Tool | Role |
|---|---|---|
| Web framework | Flask | Routes, uploads, templates and responses |
| Frontend | HTML, CSS, Jinja2 | Dashboard, detection and history pages |
| Computer vision | OpenCV, NumPy | Image resizing, edges and plate proposals |
| Image encoding | Pillow | JPEG compression for OCR API |
| OCR | OCR.space API | Alphanumeric text extraction |
| HTTP client | Requests | Cloud OCR requests |
| Database | SQLite | Detection records |
| Server | Gunicorn | Production WSGI serving |
| Hosting | Render | Public web deployment |
| Source control | GitHub | Code and revision history |

## 7. Methodology

### 7.1 Image input

A user submits a JPG, JPEG, PNG, WEBP or BMP file. Flask checks the extension and applies a 5 MB request-size limit. A UUID-based filename reduces collisions. The temporary uploaded file is deleted after processing.

### 7.2 Plate candidate detection

OpenCV loads the image and reduces its longest dimension to at most 1400 pixels. For contour analysis, image width is reduced to at most 800 pixels. The algorithm converts the image to grayscale, applies bilateral filtering and Canny edge detection, finds contours, approximates polygons and retains plausible quadrilateral regions based on aspect ratio and area. At most three candidates are selected. A whole-image OCR attempt is appended as fallback.

### 7.3 OCR extraction

Each candidate crop is encoded as JPEG, reduced to fit below approximately 900 KB and sent over HTTPS to OCR.space with Engine 2. The application can make up to four requests for one upload and stops early if a valid registration is found. API errors are surfaced to the application.

### 7.4 Text normalization and validation

The returned text is uppercased and non-alphanumeric characters are removed. OCR substitutions address common confusions between letters and digits. The validator accepts a pattern of two state letters, two district digits, one to three series letters and four terminal digits, with a recognized state/UT prefix. Example: `KA02MP9657` is displayed as `KA 02 MP 9657`.

### 7.5 Results and persistence

The application draws a bounding rectangle and recognized text on the image, saves an annotated image and a plate crop, and writes a record to SQLite. The interface displays results and permits history search and record deletion.

## 8. Database design

The `detections` table contains `id`, `plate`, `display`, `valid`, `confidence`, `annotated_file`, `crop_file` and `seen_at`. The primary key is an autoincrementing integer. The application prevents an identical plate from being inserted twice when both plate and timestamp strings match.

**Caution:** The current OCR integration stores `confidence = 0.0` because a calibrated confidence is not supplied. This should not be interpreted as measured OCR accuracy.

## 9. Implementation and deployment

The project is structured around `app.py`, `anpr_core.py`, `database.py`, `templates/`, `static/` and `requirements.txt`. Required environment variables are `OCRSPACE_API_KEY` and `SECRET_KEY`; real values must never be committed to GitHub.

Render uses `pip install -r requirements.txt` for builds and a Gunicorn start command. The `/health` route returns a JSON status for basic availability checks. The live application URL is https://plateiq-anpr.onrender.com.

### Deployment challenge and resolution

The initial prototype used EasyOCR with PyTorch inside the Render web service. Image processing was slow and Gunicorn logs reported a worker being killed with a possible out-of-memory condition. The project was revised to call OCR.space externally, remove local EasyOCR/PyTorch dependencies and use headless OpenCV. The cloud version was subsequently deployed and an example registration was recognized. This does not establish reliability across all inputs or future deployments.

## 10. Observed test evidence

| Scenario | Observation | Interpretation |
|---|---|---|
| Render deployment | Cloud OCR deployment reported live | Server deployment succeeded |
| `/health` | JSON `status: ok` observed | Basic Flask endpoint responded |
| Vehicle image upload | Successful processing message observed | Upload-to-result flow worked for at least one test |
| Indian registration | `KA 02 MP 9657` shown | Example recognition and format display succeeded |
| Earlier local EasyOCR deployment | 500/502 errors and worker SIGKILL warning | Likely memory-related failure; not formally profiled |

**Not yet measured:** test-set size, accuracy, false positives, precision, recall, mean processing time, API failure rate, peak memory and long-term uptime. Do not claim numerical accuracy without a controlled evaluation.

## 11. Limitations and risks

- **Detection:** Contour heuristics can fail on tilted, obscured or unusually styled plates.
- **OCR:** Cloud response may be delayed, unavailable or incorrect; external API limits apply.
- **Privacy:** Crops of uploaded images leave the application and are processed by a third-party OCR provider.
- **Storage:** Local SQLite and result files are not durable on Render free instances.
- **Security:** The prototype lacks login, access control and a retention policy for stored results.
- **Metrics:** The dashboard's `today` counter currently returns total detections; confidence is not calibrated and is stored as zero.
- **Generalization:** One observed successful recognition is not sufficient to establish accuracy.

## 12. Future enhancements

1. Use a managed PostgreSQL database and durable object storage.
2. Implement authentication, rate limits and secure deletion policies.
3. Fix dashboard metrics and clearly label confidence as unavailable.
4. Evaluate performance on a consented and diverse test dataset.
5. Improve plate localization and handle multiple plates per image.
6. Add optional video processing only after privacy, performance and security requirements are addressed.
7. Monitor API request volume, latency, errors and deployment health.

## 13. Conclusion

PlateIQ demonstrates an end-to-end ANPR workflow from image upload through contour-based localization, cloud OCR, registration-format validation and result presentation. Moving OCR inference outside the small Render instance addressed a practical deployment constraint and enabled an observed successful recognition. Further testing, persistent storage and security controls are necessary before real-world use.

## 14. Project links

- **Live application:** https://plateiq-anpr.onrender.com
- **GitHub repository:** https://github.com/dhiyajjoseph-eng/PlateIQ-ANPR
- **OCR provider:** https://ocr.space/

*This report describes the inspected Cloud OCR source and the deployment observations shared during development. It is not an independently audited performance study.*
