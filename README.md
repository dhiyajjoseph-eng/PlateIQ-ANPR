# PlateIQ Cloud OCR edition

PlateIQ uses Flask, OpenCV contour proposals, and the OCR.space API instead of local EasyOCR/PyTorch.

## Deploy to Render

1. Replace the files in your existing GitHub repository with the contents of this `anpr_web_app` folder (do not create an extra nested folder).
2. Commit and push to GitHub.
3. In Render → Environment, add `OCRSPACE_API_KEY` with your own OCR.space key. Never commit it.
4. Set a strong random `SECRET_KEY` environment variable.
5. Build command: `pip install -r requirements.txt`
6. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 120`
7. Deploy latest commit, visit `/health`, then test `/detect` with a clear image.

## Limitations

- OCR requests send image crops to the third-party OCR.space service. Do not upload private images without permission.
- The free OCR API has usage and file-size limits; image crops are JPEG-compressed under 1 MB.
- Each upload may make up to 4 API requests; latency and accuracy depend on the external API.
- OCR.space does not provide a calibrated confidence in this integration; UI shows N/A and stored confidence is 0.
- OpenCV contour proposals are heuristic and may miss plates; whole-image OCR is used as fallback.
- Render free instance has ephemeral filesystem: SQLite history and saved images can disappear after restarts/deploys. For durable history, use persistent external storage/database.
- No authentication: do not expose sensitive vehicle data on a public site.
