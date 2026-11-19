import sqlite3
from pathlib import Path

def connect(db_path):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con

def init_db(db_path):
    with connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate TEXT NOT NULL,
                display TEXT NOT NULL,
                valid INTEGER NOT NULL,
                confidence REAL NOT NULL,
                annotated_file TEXT NOT NULL,
                crop_file TEXT,
                seen_at TEXT NOT NULL
            )
        """)

def add_detection(db_path, result):
    with connect(db_path) as con:
        # Avoid adding the same plate repeatedly within a short period.
        existing = con.execute(
            "SELECT id FROM detections WHERE plate=? AND seen_at=?",
            (result["plate"], result["seen_at"])
        ).fetchone()
        if not existing:
            con.execute("""
                INSERT INTO detections
                (plate, display, valid, confidence, annotated_file, crop_file, seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (result["plate"], result["display"], int(result["valid"]),
                  result["confidence"], result["annotated_file"], result.get("crop_file"),
                  result["seen_at"]))

def get_detections(db_path, query="", limit=100):
    with connect(db_path) as con:
        if query:
            rows = con.execute("""
                SELECT * FROM detections WHERE plate LIKE ? OR display LIKE ?
                ORDER BY id DESC LIMIT ?
            """, (f"%{query.upper()}%", f"%{query.upper()}%", limit)).fetchall()
        else:
            rows = con.execute("SELECT * FROM detections ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

def get_stats(db_path):
    with connect(db_path) as con:
        total = con.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
        valid = con.execute("SELECT COUNT(*) FROM detections WHERE valid=1").fetchone()[0]
        avg = con.execute("SELECT AVG(confidence) FROM detections").fetchone()[0] or 0
        today = con.execute("SELECT COUNT(*) FROM detections WHERE substr(seen_at,1,11)=?", ("",)).fetchone()[0]
        return {"total": total, "valid": valid, "avg_confidence": round(avg*100, 1), "today": total}

def delete_detection(db_path, detection_id):
    with connect(db_path) as con:
        con.execute("DELETE FROM detections WHERE id=?", (detection_id,))
