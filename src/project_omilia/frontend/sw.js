/**
 * Project Omiλia — Service Worker
 * PWA Cache-First / Network-Fallback caching strategy for static assets.
 */

const CACHE_NAME = 'omilia-pwa-v1';

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
  '/static/modules/socket.js',
  '/static/modules/ui.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
];

// Pre-cache core shell during installation
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
      .catch((err) => {
        console.warn('SW pre-cache warning:', err);
      })
  );
});

// Purge obsolete caches on activation
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

// Cache-First with Network-Fallback strategy for GET requests
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
    caches.match(request).then((cachedResponse) => {
      // 1. Cache First
      if (cachedResponse) {
        return cachedResponse;
      }

      // 2. Network Fallback
      return fetch(request)
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
          // Offline fallback for navigation requests
          if (request.mode === 'navigate') {
            return caches.match('/');
          }
        });
    })
  );
});
