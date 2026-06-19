# backend/app/routes/health.py
from flask import Blueprint, jsonify
import datetime

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status":    "ok",
        "service":   "Aadhaar Health Bridge API",
        "version":   "0.1.0",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200


@health_bp.route("/health/db", methods=["GET"])
def health_check_db():
    try:
        from app import db
        db.session.execute(db.text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return jsonify({
        "status":   "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }), 200 if db_status == "connected" else 503