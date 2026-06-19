import os
import uuid
import threading
import fitz
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import db
from app.models.patient import User, VaultProfile, VaultAccess, Document, QRScanLog, HealthMetric
from datetime import datetime
from app.services.storage_service import upload_document_to_storage
from app.services import semantic_service
from app.middleware.auth import token_required
import jwt
import datetime
import json
import re
import os

try:
    import openai
except Exception:
    openai = None

bridge_bp = Blueprint("bridge", __name__)

# --- Lightweight User-Agent and Geo-IP helpers for QR scan auditing ---
def parse_user_agent(ua):
    if not ua:
        return "Unknown Device", "Unknown Browser"
    
    ua_lower = ua.lower()
    
    # Detect Device / OS
    if "iphone" in ua_lower:
        device = "iPhone"
    elif "android" in ua_lower:
        if "mobile" in ua_lower:
            device = "Android Phone"
        else:
            device = "Android Tablet"
    elif "ipad" in ua_lower:
        device = "iPad"
    elif "windows" in ua_lower:
        device = "Windows PC"
    elif "macintosh" in ua_lower or "mac os x" in ua_lower:
        device = "MacBook / macOS"
    elif "linux" in ua_lower:
        device = "Linux OS"
    else:
        device = "Generic Device"
        
    # Detect Browser
    if "edg/" in ua_lower or "edge" in ua_lower:
        browser = "Microsoft Edge"
    elif "chrome" in ua_lower or "crios" in ua_lower:
        browser = "Google Chrome"
    elif "firefox" in ua_lower or "fxios" in ua_lower:
        browser = "Mozilla Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Apple Safari"
    else:
        browser = "Web Browser"
        
    return device, browser

def get_ip_location(ip):
    if not ip or ip in ["127.0.0.1", "localhost", "::1"] or ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172.16."):
        return "Kanpur, Uttar Pradesh (Local Host)"
    
    try:
        import urllib.request
        import json
        url = f"http://ip-api.com/json/{ip}"
        req = urllib.request.Request(url, headers={'User-Agent': 'AadhaarHealthBridge/1.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "success":
                city = data.get("city", "")
                region = data.get("regionName", "")
                country = data.get("country", "")
                if city and region:
                    return f"{city}, {region}"
                elif city:
                    return f"{city}, {country}"
                return country or "Unknown Location"
    except Exception:
        pass
    
    return "Unknown Location"

# Background processing is disabled since AI/OCR/RAG features have been removed.


@bridge_bp.route("/")
def index():
    return redirect(url_for("bridge.login"))

# --- PWA ENHANCEMENT: Serve Service Worker with correct headers ---
@bridge_bp.route("/sw.js")
def serve_sw():
    """Serves the Service Worker with the correct MIME type."""
    response = make_response(current_app.send_static_file("sw.js"))
    response.headers["Content-Type"] = "application/javascript"
    return response
# ------------------------------------------------------------------

@bridge_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "error")
            return redirect(url_for("bridge.signup"))

        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.flush()

        self_vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name=username)
        db.session.add(self_vault)
        db.session.flush()

        access = VaultAccess(user_id=user.id, vault_id=self_vault.id, access_type="owner")
        db.session.add(access)
        db.session.commit()

        flash("Account created successfully.", "success")
        return redirect(url_for("bridge.login"))
    return render_template("signup.html")

@bridge_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials.")
            return redirect(url_for("bridge.login"))

        session["user_id"] = user.id
        session["username"] = user.username
        
        # Generate secure JWT token (valid for 24 hours)
        payload = {
            "user_id": user.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        token = jwt.encode(
            payload,
            current_app.config.get("JWT_SECRET", "startup_secret_key_validation_tracer"),
            algorithm="HS256"
        )
        session["token"] = token
        
        return redirect(url_for("bridge.vault_dashboard"))
    return render_template("login.html")

@bridge_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("bridge.login"))

@bridge_bp.route("/vault")
def vault_dashboard():
    if "user_id" not in session:
        return redirect(url_for("bridge.login"))
    user_id = session["user_id"]
    access_records = VaultAccess.query.filter_by(user_id=user_id).all()
    vaults = []
    for access in access_records:
        vault = VaultProfile.query.get(access.vault_id)
        vaults.append({
            "id": vault.id, "relation": vault.relation, "full_name": vault.full_name,
            "blood_group": vault.blood_group, "allergies": vault.allergies,
            "qr_token": vault.qr_token, "owner_user_id": vault.owner_user_id,
            "access_type": access.access_type
        })
    return render_template("vault.html", vaults=vaults, current_user_id=user_id)

@bridge_bp.route("/family/add-member", methods=["POST"])
def add_family_member():
    if "user_id" not in session:
        return redirect(url_for("bridge.login"))
    current_user_id = session["user_id"]

    username = request.form.get("username")
    if User.query.filter_by(username=username).first():
        flash("Username for the family member already exists.")
        return redirect(url_for("bridge.vault_dashboard"))

    parent_user = User(
        username=username,
        password_hash=generate_password_hash(request.form.get("password")),
        role="family_member"
    )
    db.session.add(parent_user)
    db.session.flush()

    vault = VaultProfile(
        owner_user_id=parent_user.id,
        relation=request.form.get("relation"),
        full_name=request.form.get("full_name"),
        blood_group=request.form.get("blood_group"),
        allergies=request.form.get("allergies"),
        personal_contact=request.form.get("personal_contact"),
        emergency_1_name=request.form.get("emergency_1_name"),
        emergency_1_relation=request.form.get("emergency_1_relation"),
        emergency_1_phone=request.form.get("emergency_1_phone"),
        emergency_2_name=request.form.get("emergency_2_name"),
        emergency_2_relation=request.form.get("emergency_2_relation"),
        emergency_2_phone=request.form.get("emergency_2_phone"),
        emergency_3_name=request.form.get("emergency_3_name"),
        emergency_3_relation=request.form.get("emergency_3_relation"),
        emergency_3_phone=request.form.get("emergency_3_phone")
    )
    db.session.add(vault)
    db.session.flush()

    db.session.add(VaultAccess(user_id=parent_user.id, vault_id=vault.id, access_type="owner"))
    db.session.add(VaultAccess(user_id=current_user_id, vault_id=vault.id, access_type="caregiver"))
    db.session.commit()
    
    flash(f"{vault.relation} vault created successfully.")
    return redirect(url_for("bridge.vault_dashboard"))

def get_local_ip():
    import socket
    # 1. Try to connect to an external target (fastest way to get the active interface's IP)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass

    # 2. Fallback: Check local interfaces using gethostbyname_ex
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        # Prefer private IP addresses that are not loopback
        for ip in ips:
            if not ip.startswith("127.") and (ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172.")):
                return ip
        # If no private IP is found, return the first non-loopback IP
        for ip in ips:
            if not ip.startswith("127."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"

@bridge_bp.route("/vault/<int:vault_id>")
def view_single_vault(vault_id):
    if "user_id" not in session:
        return redirect(url_for("bridge.login"))
    access = VaultAccess.query.filter_by(user_id=session["user_id"], vault_id=vault_id).first()
    if not access:
        flash("Unauthorized access.")
        return redirect(url_for("bridge.vault_dashboard"))
    vault = VaultProfile.query.get_or_404(vault_id)
    documents = Document.query.filter_by(vault_id=vault.id).all()
    
    # 1. Check if APP_BASE_URL is configured to a non-loopback/public URL
    config_base = current_app.config.get("APP_BASE_URL", "").rstrip('/')
    if config_base and not any(x in config_base for x in ["localhost", "127.0.0.1", "10.0.2.2"]):
        scan_base = config_base
    else:
        # 2. Fallback to dynamically checking the request host
        host_url = request.host_url.rstrip('/')
        if any(x in host_url for x in ["localhost", "127.0.0.1", "10.0.2.2"]):
            local_ip = get_local_ip()
            scan_base = host_url.replace("localhost", local_ip).replace("127.0.0.1", local_ip).replace("10.0.2.2", local_ip)
        else:
            scan_base = host_url
            
    scan_url = f"{scan_base}/api/v1/scan/{vault.qr_token}"
    scan_logs = QRScanLog.query.filter_by(vault_id=vault.id).order_by(QRScanLog.timestamp.desc()).limit(10).all()
    
    # Convert timestamps from UTC to Indian Standard Time (IST, UTC+5:30) for presentation
    from datetime import timedelta
    formatted_logs = []
    for log in scan_logs:
        ist_time = log.timestamp + timedelta(hours=5, minutes=30)
        formatted_logs.append({
            "id": log.id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "location_data": log.location_data,
            "timestamp": ist_time
        })

    db_metrics = HealthMetric.query.filter_by(vault_id=vault.id).all()
    metrics = []
    for m in db_metrics:
        try:
            val = float(m.metric_value)
        except (ValueError, TypeError):
            val = 0.0
        metrics.append({
            "metric_name": m.metric_name,
            "metric_value": val,
            "metric_unit": m.metric_unit or "",
            "observed_date": m.observed_date.strftime('%Y-%m-%d') if m.observed_date else datetime.utcnow().strftime('%Y-%m-%d')
        })

    return render_template(
        "vault_detail.html", 
        vault=vault, 
        documents=documents, 
        access_type=access.access_type, 
        scan_url=scan_url,
        scan_logs=formatted_logs,
        parse_user_agent=parse_user_agent,
        metrics=metrics
    )

@bridge_bp.route("/vault/update/<int:vault_id>", methods=["POST"])
def update_vault(vault_id):
    if "user_id" not in session:
        return redirect(url_for("bridge.login"))
    if not VaultAccess.query.filter_by(user_id=session["user_id"], vault_id=vault_id).first():
        flash("Unauthorized.")
        return redirect(url_for("bridge.vault_dashboard"))
        
    vault = VaultProfile.query.get_or_404(vault_id)
    vault.full_name = request.form.get("full_name")
    vault.blood_group = request.form.get("blood_group")
    vault.allergies = request.form.get("allergies")
    vault.medical_conditions = request.form.get("medical_conditions")
    vault.medications = request.form.get("medications")
    vault.personal_contact = request.form.get("personal_contact")
    
    vault.emergency_1_name = request.form.get("emergency_1_name")
    vault.emergency_1_relation = request.form.get("emergency_1_relation")
    vault.emergency_1_phone = request.form.get("emergency_1_phone")
    vault.emergency_2_name = request.form.get("emergency_2_name")
    vault.emergency_2_relation = request.form.get("emergency_2_relation")
    vault.emergency_2_phone = request.form.get("emergency_2_phone")
    vault.emergency_3_name = request.form.get("emergency_3_name")
    vault.emergency_3_relation = request.form.get("emergency_3_relation")
    vault.emergency_3_phone = request.form.get("emergency_3_phone")
    
    db.session.commit()
    flash("Vault updated successfully.")
    return redirect(url_for("bridge.view_single_vault", vault_id=vault.id))

@bridge_bp.route("/vault/upload/<int:vault_id>", methods=["POST"])
def upload_document(vault_id):
    if "user_id" not in session:
        return redirect(url_for("bridge.login"))

    access = VaultAccess.query.filter_by(user_id=session["user_id"], vault_id=vault_id).first()
    if not access:
        return redirect(url_for("bridge.vault_dashboard"))

    file = request.files.get("file")
    if not file:
        flash("No file selected.")
        return redirect(url_for("bridge.view_single_vault", vault_id=vault_id))

    try:
        # Secure original filename and setup distinct UUID filename
        original_filename = secure_filename(file.filename)
        extension = os.path.splitext(original_filename)[1]
        final_name = f"{uuid.uuid4().hex}{extension}"
        
        # Read file binary data
        file_bytes = file.read()
        
        # Upload file using our hybrid storage service (isolated folder by vault_id)
        storage_url = upload_document_to_storage(file_bytes, final_name, folder=f"vault_docs/vault_{vault_id}")
        
    except Exception as e:
        flash(f"Document upload failed: {str(e)}")
        return redirect(url_for("bridge.view_single_vault", vault_id=vault_id))

    # Create document record
    is_encrypted = request.form.get("is_encrypted") == "true"
    file_name = request.form.get("file_name", "").strip()
    if not file_name:
        file_name = request.form.get("category") or "Diagnostic Lab Report"

    ocr_text = ""
    if not is_encrypted and extension.lower() == ".pdf":
        try:
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            extracted_pages = []
            for page in pdf_doc:
                extracted_pages.append(page.get_text())
            ocr_text = "\n".join(extracted_pages).strip()
            pdf_doc.close()
        except Exception as ocr_err:
            current_app.logger.warning(f"Could not extract digital PDF text: {str(ocr_err)}")
            ocr_text = ""

    if not ocr_text:
        ocr_text = request.form.get("ocr_text", "").strip()

    new_document = Document(
        vault_id=vault_id,
        file_path=storage_url,
        file_name=file_name,
        category=request.form.get("category"),
        ocr_text=ocr_text,
        ai_summary="",
        uploaded_by=session["user_id"],
        is_encrypted=is_encrypted
    )
    db.session.add(new_document)
    db.session.commit()

    # Index the document into Chroma for semantic search and store structured health metrics.
    try:
        semantic_service.index_document(vault_id, new_document.id, new_document.ocr_text or "", file_name=new_document.file_name)
    except Exception:
        current_app.logger.exception("Failed to index document into semantic store")

    try:
        structured = semantic_service.extract_structured_info(new_document.ocr_text or "")
        metric_rows = semantic_service.extract_health_metric_rows(new_document.ocr_text or "", new_document.id)
        for row in metric_rows:
            metric = HealthMetric(
                vault_id=vault_id,
                metric_name=row["metric_name"],
                metric_value=row["metric_value"],
                metric_unit=row["metric_unit"],
                observed_date=row["observed_date"],
                source_document_id=row["source_document_id"]
            )
            db.session.add(metric)
        if structured:
            vault = VaultProfile.query.get(vault_id)
            try:
                existing = json.loads(vault.health_snapshot) if vault.health_snapshot else {}
            except Exception:
                existing = {}
            existing.update(structured)
            vault.health_snapshot = json.dumps(existing)
        db.session.commit()
    except Exception:
        current_app.logger.exception("Failed to extract structured info")

    flash("Document uploaded successfully!")
    return redirect(url_for("bridge.view_single_vault", vault_id=vault_id))









@bridge_bp.route("/scan/<string:token>")
def emergency_scan(token):
    vault = VaultProfile.query.filter_by(qr_token=token).first_or_404()
    
    # Resolve scanner IP, checking for proxy headers from ngrok or load balancers
    ip = request.remote_addr
    if request.headers.get("X-Forwarded-For"):
        ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
        
    location = get_ip_location(ip)
    
    new_log = QRScanLog(
        vault_id=vault.id,
        ip_address=ip,
        user_agent=request.headers.get('User-Agent'),
        location_data=location,
        timestamp=datetime.datetime.utcnow()
    )
    db.session.add(new_log)
    db.session.commit()
    
    return render_template("patient_view.html", vault=vault, location=location)



@bridge_bp.route("/vault/document/delete/<int:document_id>", methods=["POST"])
def delete_document(document_id):
    if "user_id" not in session:
        return redirect(url_for("bridge.login"))

    document = Document.query.get_or_404(document_id)

    access = VaultAccess.query.filter_by(
        user_id=session["user_id"],
        vault_id=document.vault_id
    ).first()

    if not access:
        flash("Unauthorized access.")
        return redirect(url_for("bridge.vault_dashboard"))

    try:
        full_path = os.path.join(current_app.static_folder, document.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception as e:
        print("FILE DELETE ERROR:", e)

    vault_id = document.vault_id
    db.session.delete(document)
    db.session.commit()
    flash("Medical record deleted successfully.")
    return redirect(url_for("bridge.view_single_vault", vault_id=vault_id))


def _normalize_metric_name(query):
    metric_key = semantic_service.metric_key_from_query(query)
    if metric_key:
        return metric_key
    return None


def _is_metric_question(query):
    return semantic_service.is_trend_query(query)


def _build_metric_response(vault_id, query):
    metric_name = _normalize_metric_name(query)
    metrics_q = HealthMetric.query.filter_by(vault_id=vault_id)
    if metric_name:
        metrics_q = metrics_q.filter_by(metric_name=metric_name)
    metrics = metrics_q.order_by(HealthMetric.observed_date.asc()).all()
    rows = []
    for m in metrics:
        rows.append({
            "metric_name": m.metric_name,
            "metric_value": m.metric_value,
            "metric_unit": m.metric_unit,
            "observed_date": m.observed_date.isoformat() if m.observed_date else None,
            "source_document_id": m.source_document_id
        })
    if not rows:
        return None
    if metric_name:
        answer = semantic_service.format_metric_trend_answer(metric_name, rows)
    else:
        # Build a summary overview of the latest reading for each unique metric type
        latest_map = {}
        for r in rows:
            latest_map[r["metric_name"]] = r
            
        summary_lines = []
        for name, r in latest_map.items():
            pretty_name = name.replace('_', ' ').title()
            obs_date = r["observed_date"][:10] if r["observed_date"] else "Unknown"
            ref_info = semantic_service.BIOMARKER_RANGES.get(name, {"minNormal": 0.0, "maxNormal": 999.0})
            val = None
            try:
                if re.match(r"^\d+(\.\d+)?$", r["metric_value"]):
                    val = float(r["metric_value"])
            except Exception:
                pass
            status = "✅ Normal"
            if val is not None:
                if val < ref_info.get("minNormal", 0.0):
                    status = "⚠️ Low"
                elif val > ref_info.get("maxNormal", 999.0):
                    status = "⚠️ High"
            summary_lines.append(f"| {pretty_name} | {r['metric_value']} {r['metric_unit']} | {ref_info.get('minNormal')} - {ref_info.get('maxNormal')} {r['metric_unit']} | {status} | {obs_date} |")
            
        answer = (
            "### 📋 Current Health Dashboard Summary\n\n"
            "Here are the latest recorded values for all your health biomarkers:\n\n"
            "| Biomarker | Value | Reference Range | Status | Observed Date |\n"
            "| :--- | :--- | :--- | :--- | :--- |\n"
            + "\n".join(summary_lines)
        )
    return {"answer": answer, "metrics": rows}


# --- Structured metric APIs --------------------------------------------------
@bridge_bp.route("/vault/<int:vault_id>/metrics", methods=["GET"])
@token_required
def vault_metrics(current_user, vault_id):
    if not VaultAccess.query.filter_by(user_id=current_user.id, vault_id=vault_id).first():
        return jsonify({"error": "unauthorized"}), 403

    metric_name = request.args.get("metric")
    metrics_q = HealthMetric.query.filter_by(vault_id=vault_id)
    if metric_name:
        metrics_q = metrics_q.filter_by(metric_name=metric_name)
    metrics = metrics_q.order_by(HealthMetric.observed_date.asc()).all()
    return jsonify({
        "vault_id": vault_id,
        "metric_name": metric_name,
        "metrics": [
            {
                "metric_name": m.metric_name,
                "metric_value": m.metric_value,
                "metric_unit": m.metric_unit,
                "observed_date": m.observed_date.isoformat() if m.observed_date else None,
                "source_document_id": m.source_document_id
            }
            for m in metrics
        ]
    })


@bridge_bp.route("/vault/<int:vault_id>/snapshot", methods=["GET"])
@token_required
def vault_snapshot(current_user, vault_id):
    if not VaultAccess.query.filter_by(user_id=current_user.id, vault_id=vault_id).first():
        return jsonify({"error": "unauthorized"}), 403

    vault = VaultProfile.query.get_or_404(vault_id)
    snapshot = {}
    try:
        snapshot = json.loads(vault.health_snapshot) if vault.health_snapshot else {}
    except Exception:
        snapshot = {}

    latest_metrics = HealthMetric.query.filter_by(vault_id=vault_id).order_by(HealthMetric.observed_date.desc()).limit(5).all()
    return jsonify({
        "vault_id": vault_id,
        "health_snapshot": snapshot,
        "latest_metrics": [
            {
                "metric_name": m.metric_name,
                "metric_value": m.metric_value,
                "metric_unit": m.metric_unit,
                "observed_date": m.observed_date.isoformat() if m.observed_date else None,
                "source_document_id": m.source_document_id
            }
            for m in latest_metrics
        ]
    })


# --- Simple PDF Chatbot (works over uploaded PDF OCR text) ------------------
def _simple_retrieve(query, chunks, top_n=3):
    """Return top_n chunks by simple keyword overlap scoring with bidirectional synonym expansion."""
    if not query or not chunks:
        return []
    q_tokens = re.findall(r"\w+", query.lower())
    
    # Bidirectional synonym expansion groups
    synonym_groups = [
        {"sugar", "glucose", "hba1c", "diabetes", "fbs", "rbs", "sugars"},
        {"kidney", "creatinine", "urea", "uric", "renal", "kidneys", "gfr", "egfr", "uric_acid"},
        {"blood", "hemoglobin", "hb", "hgb", "urea", "sugar", "pressure"},
        {"anemia", "hemoglobin", "hb", "hgb", "rbc", "iron"},
        {"heart", "pressure", "bp", "pulse", "cholesterol", "hypertension"},
    ]
    
    expanded_tokens = list(q_tokens)
    for token in q_tokens:
        for group in synonym_groups:
            if token in group:
                expanded_tokens.extend(group)
            
    scores = []
    for c in chunks:
        text = c.get("text", "").lower()
        score = sum(text.count(t) for t in expanded_tokens)
        scores.append((score, c))
    scores.sort(key=lambda x: x[0], reverse=True)
    results = [c for s, c in scores if s > 0]
    if not results and chunks:
        # fallback: return first few
        return chunks[:top_n]
    return results[:top_n]


@bridge_bp.route("/vault/<int:vault_id>/chat")
def vault_chat_page(vault_id):
    if "user_id" not in session:
        return redirect(url_for("bridge.login"))
    access = VaultAccess.query.filter_by(user_id=session["user_id"], vault_id=vault_id).first()
    if not access:
        flash("Unauthorized access.")
        return redirect(url_for("bridge.vault_dashboard"))
    vault = VaultProfile.query.get_or_404(vault_id)
    return render_template("vault_chat.html", vault=vault)


@bridge_bp.route("/vault/<int:vault_id>/chat", methods=["POST"])
@token_required
def vault_chat_api(current_user, vault_id):
    access = VaultAccess.query.filter_by(user_id=current_user.id, vault_id=vault_id).first()
    if not access:
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json() or {}
    query = data.get("query", "").strip()
    document_id = data.get("document_id")

    if not query:
        return jsonify({"error": "empty query"}), 400

    if _is_metric_question(query):
        metric_response = _build_metric_response(vault_id, query)
        if metric_response:
            return jsonify({
                "answer": metric_response["answer"],
                "sources": [],
                "metric_response": metric_response
            })

    # Collect text chunks from documents in this vault
    docs_q = Document.query.filter_by(vault_id=vault_id)
    if document_id:
        docs_q = docs_q.filter_by(id=document_id)
    docs = docs_q.all()

    chunks = []
    for d in docs:
        if not d.ocr_text:
            continue
        # split into paragraphs of ~500-1000 chars
        text = d.ocr_text
        parts = re.split(r"\n{2,}|\r\n{2,}", text)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # further chunk if very long
            for i in range(0, len(p), 1000):
                chunks.append({"doc_id": d.id, "file_name": d.file_name, "text": p[i:i+1000]})

    # Prefer semantic search via Chroma/OpenAI embeddings
    try:
        sem_results = semantic_service.semantic_query(vault_id, query, top_k=5)
        top_chunks = []
        for r in sem_results:
            md = r.get('metadata', {}) or {}
            top_chunks.append({
                'doc_id': md.get('doc_id'),
                'file_name': md.get('file_name'),
                'text': r.get('document')
            })
    except Exception:
        top_chunks = _simple_retrieve(query, chunks, top_n=5)

    # Build context string
    context = "\n\n".join([f"[{c.get('file_name')}] {c.get('text')}" for c in top_chunks])

    answer = ""
    ai_source = ""

    # Resolve keys and auto-detect mismatched environments
    xai_key = os.environ.get("XAI_API_KEY")
    groq_key = os.environ.get("GROQ_API_KEY")

    if xai_key and xai_key.strip().startswith("gsk_"):
        groq_key = xai_key.strip()
        xai_key = None
    elif groq_key and groq_key.strip().startswith("xai-"):
        xai_key = groq_key.strip()
        groq_key = None

    prompt = (
        "You are a precise and concise clinical document assistant. Analyze the provided medical context and answer the user's question directly, clearly, and as briefly as possible. Avoid introductory fluff and unnecessary explanations.\n\n"
        "Follow these rules:\n"
        "1. Keep answers short, direct, and focused only on what the user asked.\n"
        "2. If the user asks about abnormalities, specific parameters, or if values are normal, list the values as a clean Markdown bulleted list where EACH item is on a new, separate line (never bundle them onto a single line). Always include both the current value and the expected/normal range (reference interval) so the user knows how much it should be.\n"
        "3. Do not explain what biomarkers measure unless explicitly asked.\n"
        "4. Cite the source document next to the value in brackets like [filename.pdf]. Do not use markdown links.\n"
        "5. Always start each bullet point on its own line using standard Markdown list syntax (* Test Name: Value (Normal Range: X - Y) [source.pdf]).\n\n"
        f"Context from medical records:\n{context}\n\n"
        f"Patient Question: {query}\n\n"
        "Response (short, precise, formatted cleanly in Markdown with each list item on a separate line):"
    )

    # 1. Try Grok (xAI) if configured
    if xai_key and not answer:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=xai_key.strip(),
                base_url="https://api.xai.ai/v1"
            )
            resp = client.chat.completions.create(
                model="grok-beta",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.2
            )
            answer = resp.choices[0].message.content.strip()
            ai_source = "Grok-beta (xAI)"
        except Exception as e:
            current_app.logger.warning(f"Grok Generation API request failed: {e}")
            answer = ""

    # 2. Try Groq (groq.com) if configured
    if groq_key and not answer:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=groq_key.strip(),
                base_url="https://api.groq.com/openai/v1"
            )
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.2
            )
            answer = resp.choices[0].message.content.strip()
            ai_source = "Groq (llama-3.1-8b-instant)"
        except Exception as e:
            current_app.logger.warning(f"Groq Cloud API request failed: {e}")
            answer = ""

    # Cascading fallback to local Ollama if Grok failed or is not configured
    if not answer:
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        ollama_model = os.environ.get("OLLAMA_MODEL", "gemma2:2b")
        try:
            import requests
            prompt = (
                "You are a precise and concise medical document assistant. Use the provided context to answer the user's question directly and briefly.\n\n"
                "Rules:\n"
                "1. Keep answers short and direct.\n"
                "2. Show all list items as clean Markdown bullet points, with each item on a new, separate line. Always include the expected/normal reference range for each parameter.\n"
                "3. Cite sources in brackets like [filename].\n\n"
                f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
            )
            resp = requests.post(
                f"{ollama_host}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2
                    }
                },
                timeout=8
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                ai_source = f"Ollama ({ollama_model})"
        except Exception as e:
            current_app.logger.warning(f"Ollama local fallback failed: {e}")
            answer = ""

    if not answer:
        # Smart offline text fallback: structure the context snippets cleanly
        ai_source = "Local RAG Engine (Offline)"
        if top_chunks:
            snippets = []
            snippets.append("Note: Operating in offline mode with a direct semantic matching lookup.\n")
            for c in top_chunks:
                txt = c.get("text", "").strip()
                if len(txt) > 600:
                    txt = txt[:600].rsplit(" ", 1)[0] + "..."
                snippets.append(f"• From **{c['file_name']}**:\n  \"{txt}\"")
            answer = "\n\n".join(snippets)
        else:
            answer = "No relevant information found in the uploaded documents."

    sources = [{"doc_id": c["doc_id"], "file_name": c["file_name"], "excerpt": c["text"][:300]} for c in top_chunks]
    return jsonify({"answer": answer, "sources": sources, "ai_source": ai_source})

# ---------------------------------------------------------------------------
    return redirect(url_for("bridge.view_single_vault", vault_id=vault_id))






