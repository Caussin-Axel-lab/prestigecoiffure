// Service Worker — offline-first cache stratégie
// Cache name versionné pour invalidation au déploiement
const CACHE_VERSION = 'v1.1.0';
const CACHE_NAME = 'prestige-' + CACHE_VERSION;

// Ressources statiques à précacher (shell de l'app)
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/404.html',
  '/css/style.css',
  '/css/article.css',
  '/css/service.css',
  '/css/legal.css',
  '/js/script.js',
  '/js/page-common.js',
  '/js/theme-toggle.js',
  '/js/mobile-cta.js',
  '/js/article-toc.js',
  '/assets/logo.png',
  '/assets/favicon.svg',
  '/assets/og-image.jpg',
  '/site.webmanifest'
];

// Install : précache du shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// Activate : suppression des vieux caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k.startsWith('prestige-') && k !== CACHE_NAME)
            .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// Fetch : stratégie cache-first pour same-origin, network-first pour le reste
self.addEventListener('fetch', event => {
  const { request } = event;

  // Ignorer les requêtes non-GET (POST, etc.)
  if (request.method !== 'GET') return;

  // Ignorer les URLs externes (Unsplash, Google Fonts, Planity, etc.)
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // HTML : stratégie network-first (toujours la fraîche, fallback cache)
  if (request.mode === 'navigate' || request.destination === 'document') {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Mettre à jour le cache avec la version fraîche
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          return response;
        })
        .catch(() => caches.match(request).then(r => r || caches.match('/404.html')))
    );
    return;
  }

  // Assets statiques (CSS, JS, images) : cache-first
  event.respondWith(
    caches.match(request).then(cached => {
      if (cached) return cached;
      return fetch(request).then(response => {
        // Cacher la réponse pour le futur
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        }
        return response;
      });
    })
  );
});
