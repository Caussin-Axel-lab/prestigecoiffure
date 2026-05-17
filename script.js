  // Scroll progress bar
  const scrollProgress = document.getElementById('scroll-progress');
  if (scrollProgress) {
    window.addEventListener('scroll', () => {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      const progress = total > 0 ? (window.scrollY / total) * 100 : 0;
      scrollProgress.style.width = progress + '%';
    }, { passive: true });
  }

  // Parallaxe image hero
  const heroImg = document.querySelector('.hero-image img');
  if (heroImg) {
    window.addEventListener('scroll', () => {
      if (window.scrollY < window.innerHeight) {
        heroImg.style.transform = `translateY(${window.scrollY * 0.15}px)`;
      }
    }, { passive: true });
  }

  // Sticky nav scroll effect
  const nav = document.getElementById('topnav');
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 30);
  });

  // Mobile menu toggle
  const hamburger = document.getElementById('hamburger');
  const mobileMenu = document.getElementById('mobileMenu');
  hamburger.addEventListener('click', () => {
    mobileMenu.classList.toggle('open');
  });
  mobileMenu.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => mobileMenu.classList.remove('open'));
  });

  // Smooth scroll with offset
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      if (href.length > 1) {
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
          const offset = 80;
          const pos = target.getBoundingClientRect().top + window.pageYOffset - offset;
          window.scrollTo({ top: pos, behavior: 'smooth' });
        }
      }
    });
  });

  // Stagger + micro-blur reveal
  const STAGGER_CONFIGS = [
    { selector: '.services-grid .service', delay: 60 },
    { selector: '.marques-grid .marque-card', delay: 80 },
    { selector: '.equipe-grid .person-card', delay: 60 },
    { selector: '.reviews-list .review', delay: 100 },
  ];

  // Appliquer stagger aux grilles
  STAGGER_CONFIGS.forEach(({ selector, delay }) => {
    document.querySelectorAll(selector).forEach((el, i) => {
      el.classList.add('reveal');
      el.style.transitionDelay = (i * delay) + 'ms';
    });
  });

  // Éléments non-grille sans stagger
  const singleRevealSelectors = [
    '.salon-text', '.salon-images', '.signature-content',
    '.feature-cabine', '.update-card', '.reviews-summary',
    '.contact-info-block', '.hours-list', '.map-embed', '.hero-image',
  ];
  singleRevealSelectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(el => {
      el.classList.add('reveal');
    });
  });

  // Observer
  const revealObs = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        revealObs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08 });

  document.querySelectorAll('.reveal').forEach(el => revealObs.observe(el));
