/**
 * Aadhaar Health Bridge - PWA Service Worker with Secure Caching
 * 
 * Secure Caching Policy:
 * 1. Sensitive PHI Denial: Private APIs (/api/v1/auth, /api/v1/vaults, /api/v1/documents)
 *    and requests with Authorization headers are NEVER stored in browser cache.
 * 2. Isolated Cache Namespaces: Static assets ('healthbridge-static-v2') are separated
 *    from offline emergency access snapshots ('healthbridge-emergency-v2').
 * 3. Secure Purge: Listens for 'PURGE_SECURE_CACHE' postMessage on user logout.
 */

const STATIC_CACHE = 'healthbridge-static-v3';
const EMERGENCY_CACHE = 'healthbridge-emergency-v3';

const PUBLIC_STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/app.js',
  '/theme.css',
  '/theme.js',
  '/i18n.js',
  '/qrcode.min.js',
  '/offline_emergency.html',
  '/icon-192.png',
  '/icon-512.png',
  '/static/index.html',
  '/static/app.js',
  '/static/theme.css',
  '/static/theme.js',
  '/static/i18n.js',
  '/static/qrcode.min.js',
  '/static/offline_emergency.html',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

// Private API prefixes that must NEVER be cached by the Service Worker
const SENSITIVE_API_PATTERNS = [
  '/api/v1/auth',
  '/api/v1/vaults',
  '/api/v1/documents',
  '/api/v1/chat',
  '/api/v1/metrics',
  '/api/v1/consent',
  '/api/v1/audit',
  '/api/v1/provenance'
];

// 1. Install Event: Precache Public App Shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      console.log('[Service Worker] Precaching secure public app shell...');
      return cache.addAll(PUBLIC_STATIC_ASSETS).catch((err) => {
        console.warn('[Service Worker] Precache warning:', err);
      });
    })
  );
  self.skipWaiting();
});

// 2. Activate Event: Clean up stale caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== EMERGENCY_CACHE)
          .map((key) => {
            console.log('[Service Worker] Removing deprecated cache:', key);
            return caches.delete(key);
          })
      );
    })
  );
  self.clients.claim();
});

// 3. Message Event: Secure Cross-Session Purge on Logout
self.addEventListener('message', (event) => {
  if (event.data && event.data.action === 'PURGE_SECURE_CACHE') {
    console.log('[Service Worker] Secure cache purge requested on user logout.');
    event.waitUntil(
      caches.delete(EMERGENCY_CACHE).then(() => {
        console.log('[Service Worker] Ephemeral emergency cache purged cleanly.');
      })
    );
  }
});

// 4. Fetch Event: Secure Routing & Caching Enforcement
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Ignore non-GET requests and chrome extensions
  if (event.request.method !== 'GET' || url.protocol.startsWith('chrome-extension')) {
    return;
  }

  // Security Rule 1: NEVER cache authenticated or sensitive PHI APIs
  const isSensitiveApi = SENSITIVE_API_PATTERNS.some((p) => url.pathname.startsWith(p));
  const hasAuthHeader = event.request.headers.has('Authorization');

  if (isSensitiveApi || hasAuthHeader) {
    // Strictly bypass cache - dispatch directly to network
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(
          JSON.stringify({
            error: 'Network unavailable. Sensitive health data is not cached unencrypted.',
            offline: true
          }),
          {
            status: 503,
            headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
          }
        );
      })
    );
    return;
  }

  // Static Assets & App Shell: Cache-First with Network Revalidation
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json' || url.pathname === '/favicon.ico') {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, copy));
          }
          return response;
        });
      })
    );
    return;
  }

  // HTML / App Navigation: Network-First with Offline Fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            if (cached) return cached;
            return caches.match('/static/offline_emergency.html') || caches.match('/');
          });
        })
    );
    return;
  }

  // Default: Cache match fallback
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});