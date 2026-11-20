/**
 * Project Omiλia — Service Worker
 * PWA Network-First / Cache-Fallback caching strategy for static assets and scripts,
 * ensuring seamless offline capability while immediately delivering updates in active development.
 */

const CACHE_NAME = 'omilia-pwa-v4';

const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/static/style.css',
  '/static/app.js',
  '/static/dynamic-clip.js',
  '/static/inference.js',
  '/static/modules/camera.js',
  '/static/modules/catalog.js',
  '/static/modules/practice.js',
  '/static/modules/blitz.js',
  '/static/modules/warmup.js',
  '/static/modules/socket.js',
  '/static/modules/ui.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
];

// Pre-cache core shell during installation and activate immediately
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .catch((err) => {
        console.warn('SW pre-cache warning:', err);
      })
  );
});

// Purge obsolete caches on activation and claim all open clients immediately
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.map((key) => {
            if (key !== CACHE_NAME) {
              return caches.delete(key);
            }
          })
        )
      )
      .then(() => self.clients.claim())
  );
});

// Network-First with Cache-Fallback strategy for GET requests
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Ignore non-GET requests, API requests, WebSocket and dev/debug endpoints
  if (request.method !== 'GET') {
    return;
  }
  if (
    url.pathname.startsWith('/api') ||
    url.pathname.startsWith('/ws') ||
    url.pathname.startsWith('/dev') ||
    url.pathname.startsWith('/debug')
  ) {
    return;
  }

  // Only handle HTTP/HTTPS protocols
  if (!url.protocol.startsWith('http')) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((networkResponse) => {
        if (
          networkResponse &&
          networkResponse.status === 200 &&
          (networkResponse.type === 'basic' || networkResponse.type === 'cors')
        ) {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        return caches.match(request, { ignoreSearch: true }).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // Offline fallback for navigation requests
          if (request.mode === 'navigate') {
            return caches.match('/');
          }
        });
      })
  );
});
