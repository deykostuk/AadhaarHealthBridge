# 🏥 Aadhaar Health Bridge — Comprehensive Codebase Walkthrough

Aadhaar Health Bridge is a production-grade, privacy-first **Personal Health Record (PHR)** and **Emergency Medical Vault** platform designed for India's digital health ecosystem (ABDM compliant). It provides secure multi-profile health management, zero-knowledge envelope encryption, offline emergency glassbreaker cards, grounded local RAG clinical intelligence ($0 external API cost), and standard HL7 FHIR R4 interoperability.

---

## 🏛️ System Architecture Overview

```
                               ┌─────────────────────────────────────────┐
                               │   Progressive Web App (PWA) / SPA UI    │
                               │   - Glassmorphic Tailwind/Vanilla CSS   │
                               │   - 10 Indian Languages (i18n)          │
                               │   - Offline Emergency Medical Card      │
                               └────────────────────┬────────────────────┘
                                                    │ HTTPS / WSS
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │       FastAPI Gateway & Middleware      │
                               │   - HTTPSTransportSecurity (HSTS 2-Yr)  │
                               │   - Tiered Sliding-Window Rate Limiter  │
                               │   - CSP / Anti-Clickjacking / CORS      │
                               │   - Request Sanitizer & RBAC/ABAC       │
                               └────────────────────┬────────────────────┘
                                                    │
         ┌──────────────────────────────────────────┼──────────────────────────────────────────┐
         ▼                                          ▼                                          ▼
┌──────────────────┐                      ┌──────────────────┐                      ┌──────────────────┐
│  Auth & Identity │                      │ Clinical Records │                      │  Local AI Engine │
│  - OAuth 2.0/OIDC│                      │  - Multi-Vaults  │                      │  - Local Ollama  │
│  - Argon2id Hash │                      │  - PyMuPDF OCR   │                      │  - Sentence-     │
│  - JWT & JWKS    │                      │  - LOINC Vitals  │                      │    Transformers  │
│  - Paramedic QR  │                      │  - HL7 FHIR R4   │                      │  - Prompt Shield │
└────────┬─────────┘                      └────────┬─────────┘                      └────────┬─────────┘
         │                                         │                                         │
         ▼                                         ▼                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    Security & Storage Layer                                          │
│  - Two-Tier Envelope Encryption: HashiCorp Vault KMS / Local KMS + AES-256-GCM DEKs                  │
│  - Storage: Encrypted File Storage + PostgreSQL / SQLite with Static Pool                            │
│  - Vector Engine: ChromaDB / pgvector semantic embeddings                                            │
│  - Audit & Lineage: Immutable AuditEvent & Provenance graph                                          │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure & File Map

```
AadhaarHealthBridge/
├── backend/
│   ├── app/
│   │   ├── __init__.py                # FastAPI Application Factory & Middleware Pipeline
│   │   ├── database.py                # Database Engine & SQLAlchemy Session Dependency
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py        # Root API v1 Router Registry
│   │   │       ├── auth.py            # OAuth 2.0, OIDC UserInfo, JWKS, Login, Signup
│   │   │       ├── vaults.py          # Multi-profile Vault CRUD & Sharing Access
│   │   │       ├── documents.py       # Encrypted Upload, Streaming Download & LOINC Tagging
│   │   │       ├── metrics.py         # Time-series Biomarkers & Health Snapshots
│   │   │       ├── chat.py            # Grounded Local RAG Clinical Assistant
│   │   │       ├── scan.py            # Zero-auth Paramedic Emergency QR Scanning
│   │   │       ├── fhir.py            # HL7 FHIR R4 Standard Endpoints & $everything Export
│   │   │       ├── consent.py         # Patient Consent Granting, Revocation & Tracking
│   │   │       ├── audit.py           # Immutable Audit Trail & Verification
│   │   │       ├── provenance.py      # Clinical Data Transformation Provenance
│   │   │       ├── locales.py         # Multi-language i18n Dictionary Endpoints
│   │   │       └── health.py          # Liveness & Readiness Health Probes
│   │   ├── models/
│   │   │   └── patient.py             # User, VaultProfile, Document, HealthMetric, AuditEvent
│   │   ├── schemas/
│   │   │   └── patient.py             # Strict Pydantic v2 Input/Output Models & Mass-Assignment Defense
│   │   ├── services/
│   │   │   ├── kms_service.py         # Two-Tier Envelope Encryption (KMS Master Key + AES-256-GCM)
│   │   │   ├── password_service.py    # Argon2id Password Hashing & Bcrypt Migration
│   │   │   ├── semantic_service.py    # Local Vector Embeddings (all-MiniLM-L6-v2) & RAG Search
│   │   │   ├── ollama_service.py      # Local LLM Orchestration ($0 External API Cost)
│   │   │   ├── ai_security_service.py # Prompt-Injection Shield, XML Fencing & Citation Grounding
│   │   │   ├── pdf_service.py         # PyMuPDF Document Extraction & Regex LOINC Parsing
│   │   │   ├── fhir_service.py        # HL7 FHIR R4 Bundle Serializer
│   │   │   ├── auth_service.py        # JWT Issuance, Token Refresh Rotation & Auth Logic
│   │   │   ├── vault_service.py       # Vault Profile Management & Geo-IP Resolution
│   │   │   ├── document_service.py    # Encrypted Document Processing Pipeline
│   │   │   ├── metric_service.py      # Health Metric Normalization & Aggregation
│   │   │   ├── consent_service.py     # Patient Consent Lifecycle Management
│   │   │   ├── audit_service.py       # Immutable Audit Event Logging
│   │   │   └── provenance_service.py  # Data Lineage Tracking
│   │   ├── middleware/
│   │   │   ├── security.py            # HTTPS HSTS Preload, CSP, X-Frame-Options, SSRFValidator
│   │   │   ├── rate_limiter.py        # Tiered Sliding-Window Rate Limiter & IETF Headers
│   │   │   ├── rbac.py                # Role-Based & Attribute-Based Access Control
│   │   │   └── auth.py                # Hybrid JWT Bearer & Session Authentication
│   │   ├── utils/
│   │   │   └── sanitizer.py           # Strict Input Sanitization, XSS & Path-Traversal Defense
│   │   └── static/
│   │       ├── index.html             # Responsive PWA SPA Frontend
│   │       ├── app.js                 # Frontend Controller, IndexedDB Caching & Event Handlers
│   │       ├── styles.css             # Glassmorphic Styling & Vibrant Modern UI
│   │       ├── sw.js                  # Service Worker for Offline Availability
│   │       ├── manifest.json          # PWA Web App Manifest
│   │       ├── offline_emergency.html # Standalone Offline Emergency ICE Medical Card
│   │       └── locales/*.json         # 10 Indian Languages (hi, bn, ta, te, mr, gu, kn, ml, pa, en)
│   ├── tests/                         # 111 Automated Unit, Integration & Security Tests
│   ├── scripts/
│   │   └── run_security_audit.py      # Bandit SAST + pip-audit SCA + OWASP Unified Security Runner
│   ├── config.py                      # Application Settings & Security Config
│   ├── pytest.ini                     # Pytest Markers & Test Suite Config
│   ├── requirements.txt               # Production & Security Dependencies
│   ├── run.py                         # Uvicorn Server Launcher with TLS Support
│   └── seed_demo.py                   # Demo Profile Seeder
```

---

## 🔍 Core Subsystems & Deep Dive

### 1. Cryptographic Security & Envelope Encryption
- **File**: [`backend/app/services/kms_service.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/services/kms_service.py)
- **Mechanism**:
  - Two-tier envelope encryption architecture.
  - **Master Key (KEK)**: Stored in HashiCorp Vault KMS or secure local hardware key.
  - **Data Encryption Key (DEK)**: Unique 256-bit key generated per document or clinical record using `AES-256-GCM` with a 96-bit random IV and 128-bit authentication tag.
  - Ensures zero-knowledge encryption: even database administrators cannot inspect raw medical reports or PII without KMS authorization.

### 2. Authentication, OAuth 2.0 & OIDC Identity
- **Files**: [`backend/app/services/auth_service.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/services/auth_service.py), [`backend/app/api/v1/auth.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/api/v1/auth.py), [`backend/app/services/password_service.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/services/password_service.py)
- **Mechanism**:
  - **Argon2id Password Hashing**: State-of-the-art memory-hard password hashing with automatic upgrade migrations from legacy bcrypt/PBKDF2.
  - **OAuth 2.0 Password Grant**: Issues RFC 6749 compliant token bundles (`access_token`, `refresh_token`, `id_token`).
  - **OpenID Connect (OIDC)**: Exposes standard `/.well-known/openid-configuration`, `/jwks.json`, and `/oauth/userinfo` endpoints.
  - **Token Refresh Rotation**: Every refresh token usage invalidates the previous refresh token to prevent replay attacks.

### 3. Paramedic Zero-Auth Emergency Glassbreaker
- **Files**: [`backend/app/api/v1/scan.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/api/v1/scan.py), [`backend/app/static/offline_emergency.html`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/static/offline_emergency.html)
- **Mechanism**:
  - Each vault profile has an unguessable high-entropy `qr_token`.
  - In emergencies (e.g. road accident), first responders scan the patient's QR code to instantly access critical ICE data: Blood Group, Allergies, Chronic Conditions, Emergency Contacts, and Current Medications.
  - **Geo-IP Logging & SMS Dispatch**: Every scan logs IP, coordinates, and triggers emergency alerts.
  - **Offline ICE Card**: PWA Service Worker caches the emergency medical card locally for zero-connectivity scenarios.

### 4. Local RAG Clinical Intelligence ($0 Runtime Cost)
- **Files**: [`backend/app/services/semantic_service.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/services/semantic_service.py), [`backend/app/services/ollama_service.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/services/ollama_service.py), [`backend/app/services/ai_security_service.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/services/ai_security_service.py)
- **Mechanism**:
  - **Local Embeddings**: Generates 384-dimensional dense semantic vectors using `SentenceTransformers (all-MiniLM-L6-v2)`.
  - **Local LLM**: Connects to local Ollama runtime (`llama3`, `mistral`, `gemma`) ensuring **100% data residency and $0 external API billing**.
  - **AI Security Shield**:
    - Multi-layered prompt-injection detection (neutralizing `Ignore previous instructions`, `DAN`, jailbreaks).
    - Structural XML prompt fencing (`<medical_context>`, `<system_rules>`, `<user_query>`).
    - Grounded source attribution linking every clinical AI answer to the exact uploaded lab document.

### 5. HL7 FHIR R4 Interoperability
- **Files**: [`backend/app/services/fhir_service.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/services/fhir_service.py), [`backend/app/api/v1/fhir.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/api/v1/fhir.py)
- **Mechanism**:
  - Implements HL7 FHIR Release 4 standard REST resources: `Patient`, `Observation`, `DiagnosticReport`, `DocumentReference`, `Consent`, `AuditEvent`, `Provenance`.
  - **`$everything` Bundle Export**: Generates complete portable FHIR JSON bundles for hospital EHR interoperability.

### 6. OWASP Top 10 Hardening & Defensive Middleware
- **Files**: [`backend/app/middleware/security.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/middleware/security.py), [`backend/app/middleware/rate_limiter.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/middleware/rate_limiter.py), [`backend/app/utils/sanitizer.py`](file:///c:/Users/deyko/Desktop/AadhaarHealthBridge/backend/app/utils/sanitizer.py)
- **Protections**:
  - **Transport Security**: `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` (2-year HSTS) and HTTP 308 TLS redirection.
  - **Rate Limiting**: Sliding-window quotas with IETF headers (Auth: `5/min`, AI/Chat: `20/min`, General: `120/min`).
  - **SSRF Defense**: `SSRFValidator` hard-blocks loopback (`127.0.0.1`), private subnets (`10.0.0.0/8`, `192.168.0.0/16`), and AWS/GCP cloud metadata (`169.254.169.254`).
  - **BOLA / IDOR Defense**: Strict resource-level RBAC/ABAC dependencies on every vault and document endpoint.
  - **Mass Assignment Defense**: Pydantic v2 schemas configured with `extra="forbid"`.
  - **XSS & Path Traversal Neutralization**: Centralized `InputSanitizer` stripping control bytes, script tags, and path traversal tokens (`../`).

---

## 🧪 Testing & Security Verification

The platform maintains a **111-test automated suite** organized under Pytest markers and a 3-tier security audit pipeline.

### Test Execution Commands:
```powershell
# 1. Run Complete Test Suite (111 Tests)
python -m pytest backend/tests

# 2. Run Unit Tests Only
python -m pytest -m unit

# 3. Run Integration Workflows Only
python -m pytest -m integration

# 4. Run Security Test Suite Only
python -m pytest -m security

# 5. Run Full Security Audit (Bandit SAST + pip-audit SCA + OWASP)
python backend/scripts/run_security_audit.py
```

### Security Audit Results:
```
======================================================================
 [*] SECURITY AUDIT SUMMARY REPORT
======================================================================
  * Bandit SAST Code Analysis       : Passed (0 high/medium issues)
  * pip-audit Dependency Scan (SCA) : Completed with advisory review
  * OWASP Top 10 Automated Checks   : 100% Passed (111/111 Passed)
  * Security Compliance Status      : COMPLIANT (PASS)
======================================================================
```

---

## 🚀 Running the Platform Locally

1. **Activate Virtual Environment**:
   ```powershell
   .\backend\venv\Scripts\Activate.ps1
   ```

2. **Seed Demo Vault**:
   ```powershell
   python backend/seed_demo.py
   # Demo User: kostuk | Password: Demo1234!
   ```

3. **Launch Server**:
   ```powershell
   python backend/run.py
   ```

4. **Access Endpoints**:
   - **PWA Web Application**: `http://localhost:5000/`
   - **Interactive API Docs (Swagger UI)**: `http://localhost:5000/docs`
   - **ReDoc Documentation**: `http://localhost:5000/redoc`
   - **OIDC Discovery**: `http://localhost:5000/.well-known/openid-configuration`
   - **JWKS Endpoint**: `http://localhost:5000/api/v1/auth/jwks.json`
   - **Offline Emergency Card**: `http://localhost:5000/static/offline_emergency.html`
