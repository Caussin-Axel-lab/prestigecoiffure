// Table des matières auto-générée + scroll-spy
(function () {
  const list = document.getElementById('tocList');
  if (!list) return;

  const article = document.querySelector('.article-body');
  if (!article) return;

  const headings = Array.from(article.querySelectorAll('h2'));
  if (headings.length === 0) return;

  // Génère un slug ASCII simple à partir du texte
  function slugify(str) {
    return str.toLowerCase()
      .normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  // Pour chaque h2, ajoute un id (s'il manque) et un <li><a>
  headings.forEach(h => {
    if (!h.id) h.id = slugify(h.textContent);
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '#' + h.id;
    a.textContent = h.textContent;
    li.appendChild(a);
    list.appendChild(li);
  });

  // Scroll-spy : highlight le h2 visible
  const links = Array.from(list.querySelectorAll('a'));
  const linkByHash = new Map(links.map(a => [a.getAttribute('href').slice(1), a]));

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      const link = linkByHash.get(entry.target.id);
      if (!link) return;
      if (entry.isIntersecting) {
        links.forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
    });
  }, { rootMargin: '-30% 0px -60% 0px', threshold: 0 });

  headings.forEach(h => observer.observe(h));
})();
