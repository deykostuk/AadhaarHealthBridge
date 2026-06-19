import os
import re
import datetime
from datetime import datetime as dt

try:
    import openai
except Exception:
    openai = None

try:
    import chromadb
    from chromadb.config import Settings
except Exception:
    chromadb = None

from flask import current_app

# Configuration
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
CHROMA_DIR = os.environ.get("CHROMA_DIR", os.path.join(os.getcwd(), "chroma_db"))

METRIC_ALIASES = {
    "creatinine": ["creatinine", "creat"],
    "urea": ["blood urea", "urea"],
    "uric_acid": ["uric acid", "uric"],
    "hemoglobin": ["hemoglobin", "hb"],
    "sugar": ["blood sugar", "sugar", "fbs", "rbs", "glucose"],
    "hba1c": ["hba1c", "hb1ac", "glycated hemoglobin", "glycohemoglobin"],
}

TREND_KEYWORDS = re.compile(r"\b(history|trend|changes?|improv|better|worsen|increase|decrease|recent|latest|track|change|looking at|over time|metrics|vitals|dashboard|summary)\b", re.I)
DOCUMENT_KEYWORDS = re.compile(r"\b(medication|prescribed|doctor|recommend|discharge|summary|report|find|what did|when to|why|how to|instructions)\b", re.I)


def _get_openai_key():
    return os.environ.get("OPENAI_API_KEY")


def _ensure_chroma_client():
    if not chromadb:
        raise RuntimeError("chromadb package not installed")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client


def _embed_texts(texts):
    key = _get_openai_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY not configured in environment")
    
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed or outdated")
        
    client = OpenAI(api_key=key)
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    embeddings = [item.embedding for item in resp.data]
    return embeddings


def _chunk_text(text, chunk_size=800, overlap=100):
    tokens = []
    start = 0
    text = text.replace("\r", "")
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        tokens.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return tokens


def index_document(vault_id, document_id, text, file_name=None):
    """Chunk and upsert document chunks into Chroma collection for the vault using local embeddings."""
    try:
        client = _ensure_chroma_client()
    except Exception as e:
        current_app.logger.warning(f"Chroma client not available: {e}")
        return False

    collection_name = f"vault_{vault_id}"
    try:
        from chromadb.utils import embedding_functions
        default_ef = embedding_functions.DefaultEmbeddingFunction()
    except Exception:
        default_ef = None

    try:
        collection = client.get_or_create_collection(name=collection_name, embedding_function=default_ef)
    except Exception:
        try:
            collection = client.get_collection(name=collection_name)
        except Exception:
            collection = client.create_collection(name=collection_name)

    chunks = _chunk_text(text, chunk_size=800, overlap=150)
    ids = [f"{document_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": document_id, "file_name": file_name or "document", "chunk_index": i} for i in range(len(chunks))]

    try:
        collection.upsert(ids=ids, metadatas=metadatas, documents=chunks)
        current_app.logger.info(f"Indexed document {document_id} into Chroma collection {collection_name} locally")
        return True
    except Exception as e:
        current_app.logger.exception(f"Failed to upsert to Chroma: {e}")
        return False


def semantic_query(vault_id, query, top_k=5):
    """Return top_k matching chunks (documents) for a query using Chroma local semantic search."""
    try:
        client = _ensure_chroma_client()
    except Exception as e:
        current_app.logger.warning(f"Chroma client not available: {e}")
        return []

    collection_name = f"vault_{vault_id}"
    try:
        from chromadb.utils import embedding_functions
        default_ef = embedding_functions.DefaultEmbeddingFunction()
    except Exception:
        default_ef = None

    try:
        collection = client.get_collection(name=collection_name, embedding_function=default_ef)
    except Exception:
        return []

    try:
        res = collection.query(query_texts=[query], n_results=top_k, include=["documents", "metadatas", "distances"])
        results = []
        for i in range(len(res["ids"][0])):
            results.append({
                "id": res["ids"][0][i],
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res["distances"][0][i]
            })
        return results
    except Exception as e:
        current_app.logger.exception(f"Chroma query failed: {e}")
        return []


def _parse_observed_date(text):
    candidates = []
    date_patterns = [
        r"report date[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})",
        r"date[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})",
        r"date of report[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})",
        r"(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})"
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            candidates.append(match.group(1))
    for date_text in candidates:
        for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y"]:
            try:
                return dt.strptime(date_text, fmt)
            except ValueError:
                continue
    return None


def _clean_value(value):
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.\/-]", "", value).strip()
    return cleaned


def _find_metric_key(query):
    normalized = query.lower()
    for canonical, aliases in METRIC_ALIASES.items():
        for alias in aliases:
            # Match whole word to avoid substring matching (e.g. matching "hb" inside "hba1c")
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, normalized):
                return canonical
    return None


def is_trend_query(query):
    if not query:
        return False
    if DOCUMENT_KEYWORDS.search(query):
        return False
    return bool(TREND_KEYWORDS.search(query) or _find_metric_key(query))


def extract_structured_info(text):
    info = {}
    t = text
    observed_date = _parse_observed_date(text)
    if observed_date:
        info["observed_date"] = observed_date.isoformat()

    # creatinine (minPhys: 0.1, maxPhys: 25.0)
    m = re.search(r"\b(?:creatinine|creat|s\.\s*creatinine|serum\s+creatinine)\b(?:\s*(?:level|value|is|of|reading|percentage|concentration|result|at|[:=\-]|percentage\s+is)+)*\s*(\d{1,2}\.\d{1,2}|\d{1,2})\s*(mg/dl|mg\s+dl|mg)?", t, re.I)
    if m:
        try:
            val = float(m.group(1))
            if 0.1 <= val <= 25.0:
                info["creatinine"] = {"value": val, "unit": "mg/dL"}
        except ValueError:
            pass

    # urea (minPhys: 2.0, maxPhys: 350.0)
    m = re.search(r"\b(?:urea|blood\s+urea|b\.urea)\b(?:\s*(?:level|value|is|of|reading|percentage|concentration|result|at|[:=\-]|percentage\s+is)+)*\s*(\d{1,3}\.\d{1,2}|\d{1,3})\s*(mg/dl|mg\s+dl|mg)?", t, re.I)
    if m:
        try:
            val = float(m.group(1))
            if 2.0 <= val <= 350.0:
                info["urea"] = {"value": val, "unit": "mg/dL"}
        except ValueError:
            pass

    # uric_acid (minPhys: 1.0, maxPhys: 30.0)
    m = re.search(r"\b(?:uric\s+acid|uric|s\.\s*uric\s+acid)\b(?:\s*(?:level|value|is|of|reading|percentage|concentration|result|at|[:=\-]|percentage\s+is)+)*\s*(\d{1,2}\.\d{1,2}|\d{1,2})\s*(mg/dl|mg\s+dl|mg)?", t, re.I)
    if m:
        try:
            val = float(m.group(1))
            if 1.0 <= val <= 30.0:
                info["uric_acid"] = {"value": val, "unit": "mg/dL"}
        except ValueError:
            pass

    # hemoglobin (minPhys: 2.0, maxPhys: 25.0)
    m = re.search(r"\b(?:hemoglobin|hb|heamoglobin|haemoglobin|hgb)\b(?:\s*(?:level|value|is|of|reading|percentage|concentration|result|at|[:=\-]|percentage\s+is)+)*\s*(\d{1,2}\.\d{1,2}|\d{1,2})\s*(g/dl|g\s+dl|g)?", t, re.I)
    if m:
        # Avoid matching if preceded by hba1c or glycated context
        prefix_check = t[:m.start()].lower()
        if not any(x in prefix_check[-30:] for x in ["glycated", "hba1c", "hb1ac"]):
            try:
                val = float(m.group(1))
                if 2.0 <= val <= 25.0:
                    info["hemoglobin"] = {"value": val, "unit": "g/dL"}
            except ValueError:
                pass

    # sugar (minPhys: 20.0, maxPhys: 1000.0)
    m = re.search(r"\b(?:glucose|sugar|blood\s+sugar|fbs|rbs|ppbs|fasting\s+(?:blood\s+)?glucose|random\s+(?:blood\s+)?glucose|post\s+prandial\s+(?:blood\s+)?glucose|fasting|random|post\s+prandial)\b(?:\s*(?:level|value|is|of|reading|percentage|concentration|result|at|[:=\-]|percentage\s+is)+)*\s*(\d{2,3}(?:\.\d{1,2})?)\s*(mg/dl|mg\s+dl|mg)?", t, re.I)
    if m:
        try:
            val = float(m.group(1))
            if 20.0 <= val <= 1000.0:
                info["sugar"] = {"value": val, "unit": "mg/dL"}
        except ValueError:
            pass

    # hba1c (minPhys: 3.0, maxPhys: 20.0)
    m = re.search(r"\b(?:hba1c|hb1ac|hb-a1c|glycated\s+hemoglobin|glycohemoglobin)\b(?:\s*,\s*glycated)?(?:\s*(?:level|value|is|of|reading|percentage|concentration|result|at|[:=\-]|percentage\s+is)+)*\s*(\d{1,2}\.\d{1,2}|\d{1,2})\s*(%)?", t, re.I)
    if m:
        try:
            val = float(m.group(1))
            if 3.0 <= val <= 20.0:
                info["hba1c"] = {"value": val, "unit": "%"}
        except ValueError:
            pass

    meds = re.findall(r"(?:medications?|drugs|rx|prescription)\s*[:\-]?\s*(.+)", t, re.I)
    if meds:
        meds_list = []
        for match in meds:
            meds_list.extend([x.strip() for x in re.split(r",|;", match) if x.strip()])
        info["medications"] = meds_list

    al = re.findall(r"allerg(y|ies)\s*[:\-]?\s*(.+)", t, re.I)
    if al:
        info["allergies"] = [a[1].strip() for a in al]

    return info


def extract_health_metric_rows(text, source_document_id, observed_date=None):
    rows = []
    observed = observed_date or _parse_observed_date(text) or dt.utcnow()

    def add_metric(name, value, unit=None):
        if value is None:
            return
        rows.append({
            "metric_name": name,
            "metric_value": str(value),
            "metric_unit": unit or "",
            "observed_date": observed,
            "source_document_id": source_document_id
        })

    info = extract_structured_info(text)
    if "creatinine" in info:
        add_metric("creatinine", info["creatinine"]["value"], info["creatinine"]["unit"])
    if "urea" in info:
        add_metric("urea", info["urea"]["value"], info["urea"]["unit"])
    if "uric_acid" in info:
        add_metric("uric_acid", info["uric_acid"]["value"], info["uric_acid"]["unit"])
    if "hemoglobin" in info:
        add_metric("hemoglobin", info["hemoglobin"]["value"], info["hemoglobin"]["unit"])
    if "sugar" in info:
        add_metric("sugar", info["sugar"]["value"], info["sugar"]["unit"])
    if "hba1c" in info:
        add_metric("hba1c", info["hba1c"]["value"], info["hba1c"]["unit"])

    return rows


BIOMARKER_RANGES = {
    "creatinine": {"name": "Creatinine", "minNormal": 0.5, "maxNormal": 1.25, "unit": "mg/dL"},
    "urea": {"name": "Blood Urea", "minNormal": 15.0, "maxNormal": 45.0, "unit": "mg/dL"},
    "uric_acid": {"name": "Uric Acid", "minNormal": 2.5, "maxNormal": 7.2, "unit": "mg/dL"},
    "hemoglobin": {"name": "Hemoglobin", "minNormal": 12.0, "maxNormal": 17.5, "unit": "g/dL"},
    "sugar": {"name": "Blood Sugar", "minNormal": 70.0, "maxNormal": 140.0, "unit": "mg/dL"},
    "hba1c": {"name": "HbA1c", "minNormal": 4.0, "maxNormal": 5.7, "unit": "%"}
}


def metric_key_from_query(query):
    return _find_metric_key(query)


def format_metric_trend_answer(metric_name, metrics):
    if not metrics:
        return None
    
    # Capitalize first letter of biomarker name
    pretty_name = metric_name.replace('_', ' ').title()
    
    # Get range config
    ref_info = BIOMARKER_RANGES.get(metric_name, {"name": pretty_name, "minNormal": 0.0, "maxNormal": 999.0, "unit": ""})
    min_norm = ref_info.get("minNormal")
    max_norm = ref_info.get("maxNormal")
    unit = ref_info.get("unit") or metrics[0].get("metric_unit") or ""
    
    latest = metrics[-1]
    latest_val = None
    try:
        if re.match(r"^\d+(\.\d+)?$", latest["metric_value"]):
            latest_val = float(latest["metric_value"])
    except Exception:
        pass
    
    # Trend evaluation
    status_text = "Unknown"
    if latest_val is not None:
        if latest_val < min_norm:
            status_text = "⚠️ **Low**"
        elif latest_val > max_norm:
            status_text = "⚠️ **High**"
        else:
            status_text = "✅ **Normal**"
            
    # History list & delta
    history_rows = []
    for m in metrics:
        val = m["metric_value"]
        obs_date = m["observed_date"][:10] if isinstance(m["observed_date"], str) else m["observed_date"].strftime("%Y-%m-%d") if m["observed_date"] else "Unknown"
        history_rows.append(f"| {obs_date} | {val} {unit} |")

    # Trend narrative
    narrative = ""
    if len(metrics) >= 2:
        try:
            numeric_vals = []
            for m in metrics:
                if re.match(r"^\d+(\.\d+)?$", m["metric_value"]):
                    numeric_vals.append(float(m["metric_value"]))
            if len(numeric_vals) >= 2:
                delta = numeric_vals[-1] - numeric_vals[-2]
                arrow = "increased 📈" if delta > 0 else "decreased 📉" if delta < 0 else "remained stable ➡️"
                diff = abs(delta)
                prev_val = numeric_vals[-2]
                narrative = f"\nYour level has **{arrow}** by **{diff:.2f} {unit}** compared to the previous reading of **{prev_val} {unit}**."
        except Exception:
            pass

    latest_date = latest['observed_date'][:10] if isinstance(latest['observed_date'], str) else latest['observed_date'].strftime('%Y-%m-%d') if latest['observed_date'] else 'Unknown'

    answer = (
        f"### 📑 Clinical Trend Report: {ref_info['name']}\n\n"
        f"* **Latest Reading:** {latest['metric_value']} {unit} ({latest_date})\n"
        f"* **Reference Interval:** {min_norm} - {max_norm} {unit}\n"
        f"* **Clinical Status:** {status_text}\n"
        f"{narrative}\n\n"
        "#### 📊 Historical Data:\n"
        "| Date | Value |\n"
        "| :--- | :--- |\n"
        + "\n".join(history_rows)
    )
    return answer
