// Service Worker registration — chargé une fois, register le SW à la racine
(function () {
  if (!('serviceWorker' in navigator)) return;
  // Ne register qu'en HTTPS (ou localhost) — http insecure context = no SW
  if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') return;

  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .catch(err => console.warn('SW registration failed:', err));
  });
})();
