import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename

from anpr_core import recognize_image
from database import init_db, add_detection, get_detections, get_stats, delete_detection

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
RESULT_DIR = BASE_DIR / "results"
DB_PATH = BASE_DIR / "anpr.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

UPLOAD_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
init_db(DB_PATH)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def dashboard():
    return render_template("index.html", stats=get_stats(DB_PATH),
                           detections=get_detections(DB_PATH, limit=8), page="dashboard")

@app.route("/detect", methods=["GET", "POST"])
def detect():
    result = None
    if request.method == "POST":
        uploaded = request.files.get("image")
        if not uploaded or not uploaded.filename:
            flash("Choose an image first.", "error")
            return redirect(url_for("detect"))
        if not allowed_file(uploaded.filename):
            flash("Please upload PNG, JPG, JPEG, WEBP or BMP.", "error")
            return redirect(url_for("detect"))

        safe_name = secure_filename(uploaded.filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        input_path = UPLOAD_DIR / unique_name
        uploaded.save(input_path)

        try:
            result = recognize_image(input_path, RESULT_DIR)
            if result:
                result["image_url"] = url_for("result_file", filename=result["annotated_file"])
                result["crop_url"] = url_for("result_file", filename=result["crop_file"]) if result.get("crop_file") else None
                add_detection(DB_PATH, result)
                flash("Image processed successfully.", "success")
            else:
                flash("No readable number plate was found. Try a clearer, closer image.", "error")
        except ImportError as exc:
            flash(str(exc), "error")
        except Exception as exc:
            app.logger.exception("Recognition failed")
            flash(f"Processing failed: {exc}", "error")
        finally:
            input_path.unlink(missing_ok=True)

    return render_template("detect.html", result=result, page="detect")

@app.route("/history")
def history():
    q = request.args.get("q", "").strip()
    return render_template("history.html", detections=get_detections(DB_PATH, query=q, limit=200),
                           query=q, page="history")

@app.route("/history/<int:detection_id>/delete", methods=["POST"])
def remove_detection(detection_id):
    delete_detection(DB_PATH, detection_id)
    flash("Detection record deleted.", "success")
    return redirect(url_for("history"))

@app.route("/results/<path:filename>")
def result_file(filename):
    return send_from_directory(RESULT_DIR, filename)

@app.route("/health")
def health():
    return {"status": "ok", "service": "ANPR web app"}

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
