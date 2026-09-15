const SHELL_CACHE = 'freetuve-shell-v6';
const OFFLINE_CACHE = 'freetuve-offline-lessons-v1';
const SHELL_ASSETS = [
  '/',
  '/styles.css?v=3',
  '/app.js?v=5',
  '/recovery.js?v=1',
  '/manifest.webmanifest',
  '/icon.svg',
  '/icon-192.png',
  '/icon-512.png',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(SHELL_CACHE).then(cache => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys
        .filter(key => key.startsWith('freetuve-shell-') && key !== SHELL_CACHE)
        .map(key => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function offlineAudioResponse(request) {
  const cache = await caches.open(OFFLINE_CACHE);
  const cached = await cache.match(request.url);
  if (!cached) return fetch(request);

  const range = request.headers.get('range');
  if (!range) return cached;
  const match = /^bytes=(\d+)-(\d*)$/.exec(range.trim());
  if (!match) return cached;

  const blob = await cached.blob();
  const start = Number(match[1]);
  const requestedEnd = match[2] ? Number(match[2]) : blob.size - 1;
  const end = Math.min(requestedEnd, blob.size - 1);
  if (!Number.isFinite(start) || start < 0 || start > end || start >= blob.size) {
    return new Response(null, {
      status: 416,
      headers: { 'Content-Range': `bytes */${blob.size}` },
    });
  }

  const chunk = blob.slice(start, end + 1, cached.headers.get('Content-Type') || 'audio/mp4');
  return new Response(chunk, {
    status: 206,
    statusText: 'Partial Content',
    headers: {
      'Content-Type': chunk.type || 'audio/mp4',
      'Content-Length': String(chunk.size),
      'Content-Range': `bytes ${start}-${end}/${blob.size}`,
      'Accept-Ranges': 'bytes',
    },
  });
}

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/lessons/') && url.pathname.includes('/offline/')) {
    event.respondWith(offlineAudioResponse(event.request));
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match('/')));
    return;
  }

  const cacheKey = `${url.pathname}${url.search}`;
  if (SHELL_ASSETS.includes(cacheKey)) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
  }
});
