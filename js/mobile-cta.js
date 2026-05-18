// Sticky CTA mobile — apparait après 400px de scroll, se cache près du footer
(function () {
  const cta = document.getElementById('mobileCta');
  if (!cta) return;

  // N'activer que sur mobile (matchMedia matches le breakpoint CSS)
  const mq = window.matchMedia('(max-width: 880px)');

  // Respect prefers-reduced-motion : on garde l'affichage mais sans transition
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reducedMotion) cta.style.transition = 'none';

  let ticking = false;
  let visible = false;

  function update() {
    ticking = false;
    if (!mq.matches) {
      if (visible) { cta.classList.remove('visible'); visible = false; }
      return;
    }
    const scrolled = window.scrollY;
    const docHeight = document.documentElement.scrollHeight;
    const viewport = window.innerHeight;
    const nearBottom = scrolled + viewport > docHeight - 240;

    const shouldShow = scrolled > 400 && !nearBottom;
    if (shouldShow !== visible) {
      cta.classList.toggle('visible', shouldShow);
      visible = shouldShow;
    }
  }

  function onScroll() {
    if (!ticking) {
      requestAnimationFrame(update);
      ticking = true;
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', update, { passive: true });
  update();
})();
