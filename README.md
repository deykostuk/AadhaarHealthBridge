# 📱 Aadhaar Health Bridge — Standalone Frontend (PWA)

This directory contains the decoupled, standalone Progressive Web App (PWA) client for **Aadhaar Health Bridge**.

---

## 🚀 Quick Start (Local Development)

### Option 1: Using Python (Zero extra dependencies)
```bash
# From within the frontend/ directory:
python serve.py 3000
```
Then visit [http://localhost:3000](http://localhost:3000).

### Option 2: Using Node / npx
```bash
# From within the frontend/ directory:
npm run dev
# OR: npx serve -p 3000 .
```

---

## ⚙️ Configuration

The frontend dynamically communicates with the backend API at `http://localhost:5000/api/v1` during local development.

To target a remote staging/production backend, set `window.AHB_API_BASE_URL` in `index.html` or pass it in your hosting environment:
```javascript
window.AHB_API_BASE_URL = "https://api.yourdomain.com";
```

---

## 📦 Production Deployment

Because this frontend is a decoupled static PWA with client-side state and Service Worker caching, it can be deployed to any modern static hosting service:

- **Vercel**: Deploy directory `frontend/` directly.
- **Netlify**: Set publish directory to `frontend/`.
- **Cloudflare Pages**: Link repo and set build output directory to `frontend/`.
- **AWS S3 + CloudFront**: Sync `frontend/` files directly to an S3 bucket.
- **Nginx**: Point `root /var/www/html/frontend;` in your Nginx site configuration.

---

## 📂 Directory Structure

```
frontend/
├── index.html              # Main PWA Single-Page Application Shell
├── app.js                  # Client logic, state management, REST API client
├── theme.css               # CSS Variables, Design tokens, Dark/Light modes
├── theme.js                # Theme initialization and persistence
├── i18n.js                 # 6 Indian language offline dictionaries (EN, HI, BN, TE, TA, MR)
├── sw.js                   # Service Worker with secure PHI cache denial
├── manifest.json           # PWA installation manifest
├── offline_emergency.html  # Standalone zero-login emergency profile viewer
├── qrcode.min.js           # Client-side QR generation engine
├── locales/                # JSON translation bundles
├── serve.py                # Zero-dependency local dev server
└── package.json            # npm scripts
```
