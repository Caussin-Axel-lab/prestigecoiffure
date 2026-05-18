// Theme toggle — bascule dark/light + persistance localStorage
// Note : le script anti-flash dans <head> de chaque page applique data-theme
// au plus tôt pour éviter le flash blanc. Ce fichier gère uniquement le toggle.
(function () {
  const btn = document.getElementById('themeToggle');
  if (!btn) return;

  const root = document.documentElement;
  const mqDark = window.matchMedia('(prefers-color-scheme: dark)');

  function currentTheme() {
    return root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function updateButtonLabel() {
    const isDark = currentTheme() === 'dark';
    btn.setAttribute('aria-label', isDark ? 'Activer le mode clair' : 'Activer le mode sombre');
    btn.setAttribute('aria-pressed', String(isDark));
  }

  function applyTheme(theme) {
    if (theme === 'dark') {
      root.setAttribute('data-theme', 'dark');
    } else {
      root.removeAttribute('data-theme');
    }
    updateButtonLabel();
  }

  // Sync with system preference if user has NOT made an explicit choice
  mqDark.addEventListener('change', e => {
    if (!localStorage.getItem('theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });

  btn.addEventListener('click', () => {
    const next = currentTheme() === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', next);
    applyTheme(next);
  });

  // Initial label
  updateButtonLabel();
})();
