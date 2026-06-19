const CACHE_NAME = 'health-bridge-v2';
const ASSETS_TO_CACHE = [
  '/static/manifest.json',
  '/static/offline_emergency.html'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE)));
});

// Clean up old caches to force fresh assets load
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Helper function to read from IndexedDB inside service worker scope
function getCachedFileFromIndexedDB(filePath) {
  return new Promise((resolve) => {
    const request = indexedDB.open('HealthBridgeOfflineCache', 1);
    request.onsuccess = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('encrypted_documents')) {
        resolve(null);
        return;
      }
      try {
        const transaction = db.transaction('encrypted_documents', 'readonly');
        const store = transaction.objectStore('encrypted_documents');
        const getReq = store.get(filePath);
        getReq.onsuccess = () => resolve(getReq.result);
        getReq.onerror = () => resolve(null);
      } catch (err) {
        resolve(null);
      }
    };
    request.onerror = () => resolve(null);
  });
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Intercept requests directed to the medical files directory
  if (url.pathname.startsWith('/static/vault_docs/')) {
    const filePath = url.pathname.replace('/static/', '');
    event.respondWith(
      getCachedFileFromIndexedDB(filePath).then((arrayBuffer) => {
        if (arrayBuffer) {
          // Detect MIME type
          let mimeType = 'application/octet-stream';
          const cleanPath = filePath.replace(/\.enc$/i, '').toLowerCase();
          if (cleanPath.endsWith('.pdf')) mimeType = 'application/pdf';
          else if (cleanPath.endsWith('.png')) mimeType = 'image/png';
          else if (cleanPath.endsWith('.jpg') || cleanPath.endsWith('.jpeg')) mimeType = 'image/jpeg';
          else if (cleanPath.endsWith('.gif')) mimeType = 'image/gif';
          else if (cleanPath.endsWith('.txt')) mimeType = 'text/plain';

          return new Response(arrayBuffer, {
            headers: {
              'Content-Type': mimeType,
              'Cache-Control': 'public, max-age=31536000'
            }
          });
        }
        
        // If not cached, fetch from network and dynamically store it in IndexedDB
        return fetch(event.request).then((response) => {
          if (response.status === 200) {
            const responseClone = response.clone();
            responseClone.arrayBuffer().then((buffer) => {
              const reqOpen = indexedDB.open('HealthBridgeOfflineCache', 1);
              reqOpen.onsuccess = (e) => {
                const db = e.target.result;
                if (db.objectStoreNames.contains('encrypted_documents')) {
                  try {
                    const tx = db.transaction('encrypted_documents', 'readwrite');
                    tx.objectStore('encrypted_documents').put(buffer, filePath);
                  } catch (err) {
                    console.warn("SW: Failed to write to IndexedDB:", err);
                  }
                }
              };
            });
          }
          return response;
        }).catch(() => {
          return new Response("This file is not cached for offline access.", { status: 503, statusText: "Offline" });
        });
      })
    );
    return;
  }

  // Bypass cache for non-GET requests and dynamic templates (login, signup, vault, etc.)
  if (
    event.request.method !== 'GET' || 
    url.pathname.includes('/login') || 
    url.pathname.includes('/signup') || 
    url.pathname.includes('/vault') || 
    url.pathname.includes('/scan')
  ) {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    caches.match(event.request).then((response) => response || fetch(event.request))
  );
});