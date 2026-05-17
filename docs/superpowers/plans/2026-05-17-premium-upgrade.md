# Prestige Coiffure — Premium Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Élever le site Prestige Coiffure au niveau "vraiment premium" via 15 améliorations de finition (grain, animations, typographie, contenu) sans modifier la structure ni l'identité visuelle.

**Architecture:** Site HTML/CSS/JS statique, aucun build tool. Les modifications sont réparties sur 4 fichiers existants : `style.css` (CSS), `index.html` (HTML), `script.js` (JS), `blog.html` (cohérence nav). L'ordre d'implémentation suit la dépendance : CSS → HTML → JS → blog.

**Tech Stack:** HTML5, CSS3 (custom properties, pseudo-éléments, clip-path), JavaScript vanilla (IntersectionObserver, requestAnimationFrame, scroll events). Google Fonts déjà chargées (Cormorant Garamond, Manrope, JetBrains Mono).

---

## Fichiers touchés

| Fichier | Rôle dans ce plan |
|---------|-------------------|
| `style.css` | Grain, espacement, nav, boutons, reveal, guillemets, ornements, CTA meta |
| `index.html` | Scroll-progress, ornament-dividers, featured class, suppression prix, CTA meta |
| `script.js` | Scroll-progress logic, parallaxe hero, stagger+blur, titre hero |
| `blog.html` | Underline actif sur lien Journal |

---

## Task 1 : CSS — Grain de film + Espacement des sections

**Fichiers :**
- Modifier : `style.css`

- [ ] **Étape 1 : Ajouter le grain de film et la barre de progression**

Dans `style.css`, juste après la règle `body { ... }`, ajouter :

```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  opacity: 0.035;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  background-size: 300px 300px;
}

#scroll-progress {
  position: fixed;
  top: 0; left: 0;
  height: 2px;
  width: 0%;
  background: var(--gold-bright);
  z-index: 200;
  transition: width 0.1s linear;
  pointer-events: none;
}
```

- [ ] **Étape 2 : Mettre à jour les paddings des sections**

Dans `style.css`, remplacer :

```css
section { padding: 100px 32px; position: relative; }
```

par :

```css
section { padding: 120px 48px; position: relative; }
```

Remplacer le padding hero :

```css
.hero {
  min-height: 100vh;
  padding: 120px 32px 60px;
```

par :

```css
.hero {
  min-height: 100vh;
  padding: 120px 48px 80px;
```

Remplacer le padding signature-band :

```css
.signature-band {
  padding: 72px 32px;
```

par :

```css
.signature-band {
  padding: 88px 48px;
```

Remplacer le padding cta-band :

```css
.cta-band {
  background: var(--bg-dark);
  color: var(--cream);
  padding: 80px 32px;
```

par :

```css
.cta-band {
  background: var(--bg-dark);
  color: var(--cream);
  padding: 96px 48px;
```

- [ ] **Étape 3 : Vérification visuelle**

Ouvrir `index.html` dans un navigateur. Vérifier :
- Le fond crème a une légère texture granuleuse perceptible (regarder de près sur fond uni)
- Les sections ont plus d'air — l'espace vertical entre les blocs est plus généreux
- Aucun élément n'est décalé ou coupé

- [ ] **Étape 4 : Commit**

```bash
git add style.css
git commit -m "style: grain de film et espacement sections premium"
```

---

## Task 2 : CSS — Navigation underline animé + Transition cubic-bezier

**Fichiers :**
- Modifier : `style.css`

- [ ] **Étape 1 : Remplacer le hover color par underline animé**

Dans `style.css`, remplacer le bloc `.nav-links a` et `.nav-links a:hover` :

```css
/* AVANT */
.nav-links a {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink);
  text-decoration: none;
  transition: color 0.2s ease;
}
.nav-links a:hover { color: var(--sage-deep); }
```

par :

```css
.nav-links a {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink);
  text-decoration: none;
  position: relative;
}
.nav-links a::after {
  content: '';
  position: absolute;
  bottom: -2px; left: 0;
  width: 0; height: 1px;
  background: var(--sage-deep);
  transition: width 0.3s ease;
}
.nav-links a:hover::after,
.nav-links a.active::after { width: 100%; }
```

- [ ] **Étape 2 : Mettre à jour la transition de la nav**

Remplacer :

```css
header.topnav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  padding: 18px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.3s ease;
}
```

par :

```css
header.topnav {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
  padding: 18px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
```

- [ ] **Étape 3 : Vérification visuelle**

Ouvrir `index.html`. Survoler les liens de navigation :
- Une fine ligne apparaît en glissant de gauche à droite sous le lien
- Au scroll vers le bas, la nav passe en fond crème avec une transition plus douce (pas de "clac" brusque)

- [ ] **Étape 4 : Commit**

```bash
git add style.css
git commit -m "style: nav underline animé et transition cubic-bezier"
```

---

## Task 3 : CSS — Effet shine sur .cta-btn + Remplissage directionnel .cta-ghost

**Fichiers :**
- Modifier : `style.css`

- [ ] **Étape 1 : Ajouter l'effet shine sur .cta-btn**

Dans `style.css`, ajouter `position: relative; overflow: hidden;` à la règle `.cta-btn` existante et ajouter le pseudo-élément :

```css
.cta-btn {
  background: var(--sage-deep);
  color: var(--cream);
  padding: 12px 22px;
  border-radius: 999px;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  transition: all 0.2s ease;
  display: inline-block;
  position: relative;
  overflow: hidden;
}
.cta-btn::before {
  content: '';
  position: absolute;
  top: 0; left: -75%;
  width: 50%; height: 100%;
  background: linear-gradient(
    120deg,
    transparent 0%,
    rgba(255,255,255,0.18) 50%,
    transparent 100%
  );
  transform: skewX(-20deg);
  transition: left 0.5s ease;
  pointer-events: none;
}
.cta-btn:hover::before { left: 125%; }
```

- [ ] **Étape 2 : Remplacer le hover .cta-ghost par remplissage directionnel**

Remplacer le bloc `.cta-ghost` et `.cta-ghost:hover` :

```css
/* AVANT */
.cta-ghost {
  background: transparent;
  color: var(--ink);
  border: 1px solid var(--ink);
  padding: 16px 30px;
  border-radius: 999px;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  transition: all 0.2s ease;
  display: inline-block;
}
.cta-ghost:hover { background: var(--ink); color: var(--cream); }
```

par :

```css
.cta-ghost {
  background: transparent;
  color: var(--ink);
  border: 1px solid var(--ink);
  padding: 16px 30px;
  border-radius: 999px;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  display: inline-block;
  position: relative;
  overflow: hidden;
  transition: color 0.25s ease, border-color 0.25s ease;
}
.cta-ghost::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--ink);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.25s ease;
  z-index: -1;
  border-radius: 999px;
}
.cta-ghost:hover::before { transform: scaleX(1); }
.cta-ghost:hover { color: var(--cream); border-color: var(--ink); }
```

- [ ] **Étape 3 : Vérification visuelle**

Ouvrir `index.html`. Survoler le bouton "Prendre rendez-vous" (vert) dans le hero :
- Un reflet blanc glisse de gauche à droite au hover
Survoler le bouton "Découvrir nos prestations" (ghost) :
- Le fond noir envahit le bouton de gauche à droite, le texte passe en crème

- [ ] **Étape 4 : Commit**

```bash
git add style.css
git commit -m "style: effet shine cta-btn et remplissage directionnel cta-ghost"
```

---

## Task 4 : CSS — Animation reveal avec micro-blur + prefers-reduced-motion

**Fichiers :**
- Modifier : `style.css`

- [ ] **Étape 1 : Mettre à jour la règle .reveal**

Remplacer le bloc `.reveal` et `.reveal.visible` existant (en bas de `style.css`) :

```css
/* AVANT */
.reveal {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.8s ease, transform 0.8s ease;
}
.reveal.visible { opacity: 1; transform: translateY(0); }
```

par :

```css
.reveal {
  opacity: 0;
  transform: translateY(28px);
  filter: blur(6px);
  transition: opacity 0.7s ease, transform 0.7s ease, filter 0.7s ease;
}
.reveal.visible {
  opacity: 1;
  transform: translateY(0);
  filter: blur(0);
}

@media (prefers-reduced-motion: reduce) {
  .reveal {
    transform: none;
    filter: none;
    transition: opacity 0.4s ease;
  }
  .reveal.visible {
    transform: none;
    filter: none;
  }
}
```

- [ ] **Étape 2 : Retirer le hover scale sur l'image hero**

Cette règle entre en conflit avec le parallaxe JS qui sera ajouté plus tard. La trouver et la supprimer :

```css
/* À supprimer */
.hero-image:hover img { transform: scale(1.03); }
```

- [ ] **Étape 3 : Vérification visuelle**

Ouvrir `index.html` et scroller lentement. Les éléments qui apparaissent au scroll font maintenant une "mise au point" (flou→net) en plus du fade-translateY. Le mouvement est plus doux et premium. Sur un navigateur avec `prefers-reduced-motion: reduce` activé dans les réglages d'accessibilité, seul le fade reste.

- [ ] **Étape 4 : Commit**

```bash
git add style.css
git commit -m "style: reveal micro-blur et prefers-reduced-motion"
```

---

## Task 5 : CSS — Guillemets décoratifs, review featured, ornement diviseur, CTA meta

**Fichiers :**
- Modifier : `style.css`

- [ ] **Étape 1 : Guillemets décoratifs sur les cartes avis**

Dans `style.css`, ajouter après le bloc `.review { ... }` existant :

```css
.review {
  background: var(--cream);
  border: 1px solid var(--line);
  padding: 26px 28px;
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}
.review::before {
  content: '\201C';
  position: absolute;
  top: -20px; left: 16px;
  font-family: 'Cormorant Garamond', serif;
  font-size: 180px;
  line-height: 1;
  color: var(--ink);
  opacity: 0.06;
  pointer-events: none;
  user-select: none;
}
```

Note : la règle `.review` existante n'a pas `position: relative` ni `overflow: hidden` — les ajouter à la règle existante plutôt qu'en dupliquer une nouvelle.

- [ ] **Étape 2 : Styles du premier avis mis en exergue**

Ajouter après le bloc `.review::before` :

```css
.review--featured {
  background: var(--bg);
  border-color: var(--line);
}
.review--featured .quote {
  font-size: 20px;
}
.review--featured .author {
  border-left: 2px solid var(--gold);
  padding-left: 12px;
  margin-left: 2px;
}
```

- [ ] **Étape 3 : Styles du séparateur ornemental**

Ajouter en fin de `style.css` :

```css
/* === ORNAMENT DIVIDER === */
.ornament-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 0 48px;
  height: 48px;
  background: var(--bg);
}
.ornament-divider span:not(.diamond) {
  flex: 1;
  height: 1px;
  background: var(--line);
  max-width: 120px;
}
.ornament-divider .diamond {
  font-size: 8px;
  color: var(--gold);
  letter-spacing: 0;
}
```

- [ ] **Étape 4 : Style du meta CTA Planity**

Ajouter en fin de `style.css` :

```css
/* === SERVICES CTA META === */
.services-cta-meta {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(251, 248, 242, 0.65);
  margin-bottom: 14px;
}
```

- [ ] **Étape 5 : Commit**

```bash
git add style.css
git commit -m "style: guillemets décoratifs, review featured, ornament-divider, cta-meta"
```

---

## Task 6 : HTML — Scroll progress bar + Ornament dividers + Featured + Suppression prix + CTA meta

**Fichiers :**
- Modifier : `index.html`

- [ ] **Étape 1 : Ajouter l'élément scroll-progress**

Dans `index.html`, juste après `<body>`, ajouter :

```html
<div id="scroll-progress" role="progressbar" aria-hidden="true"></div>
```

- [ ] **Étape 2 : Ajouter le premier séparateur ornemental (après hero, avant #le-salon)**

Trouver la ligne `<!-- ============ LE SALON ============ -->` et insérer avant :

```html
<div class="ornament-divider" aria-hidden="true">
  <span></span>
  <span class="diamond">◆</span>
  <span></span>
</div>

<!-- ============ LE SALON ============ -->
```

- [ ] **Étape 3 : Ajouter le deuxième séparateur ornemental (après #marques, avant #equipe)**

Trouver la ligne `<!-- ============ ÉQUIPE ============ -->` et insérer avant :

```html
<div class="ornament-divider" aria-hidden="true">
  <span></span>
  <span class="diamond">◆</span>
  <span></span>
</div>

<!-- ============ ÉQUIPE ============ -->
```

- [ ] **Étape 4 : Ajouter la classe review--featured sur le premier avis**

Trouver le premier `<div class="review">` dans la section `#avis` et le modifier :

```html
<!-- AVANT -->
<div class="review">
  <div class="quote">« Le meilleur salon de coiffure de Chalon-sur-Saône...

<!-- APRÈS -->
<div class="review review--featured">
  <div class="quote">« Le meilleur salon de coiffure de Chalon-sur-Saône...
```

- [ ] **Étape 5 : Supprimer les 9 éléments .service-price**

Dans la section `#prestations`, supprimer chacun des 9 éléments suivants (ils ont tous cette forme) :

```html
<div class="service-price">À partir de [tarif Planity]</div>
```
et
```html
<div class="service-price">Sur devis · [tarif Planity]</div>
```

Il y en a exactement 9, un par `.service`. Les supprimer tous.

- [ ] **Étape 6 : Nettoyer le .section-lede des prestations**

Trouver dans la section `#prestations` :

```html
<p class="section-lede">Femme, homme, enfant — coupe classique, coloration, balayage, soins profonds, lissage, barberie, mariage. Les tarifs détaillés et les départs techniques sont publiés sur notre fiche Planity.</p>
```

Remplacer par :

```html
<p class="section-lede">Femme, homme, enfant — coupe classique, coloration, balayage, soins profonds, lissage, barberie, mariage.</p>
```

- [ ] **Étape 7 : Enrichir le bloc .services-cta**

Trouver dans `index.html` le bloc `.services-cta` :

```html
<div class="services-cta">
  <p>Tarifs détaillés et départs techniques disponibles sur notre fiche Planity.</p>
  <a href="https://www.planity.com/...
```

Ajouter la ligne meta avant le lien :

```html
<div class="services-cta">
  <p>Tarifs détaillés et départs techniques disponibles sur notre fiche Planity.</p>
  <div class="services-cta-meta">9 prestations · Tarifs détaillés et disponibilités en ligne</div>
  <a href="https://www.planity.com/...
```

- [ ] **Étape 8 : Vérification visuelle**

Ouvrir `index.html`. Vérifier :
- La section prestations n'affiche plus aucun `[tarif Planity]` ni prix placeholder
- Les deux séparateurs ornementaux `◆` sont visibles entre Hero/Salon et Marques/Équipe
- Le premier avis a un fond légèrement différent et le filet doré à gauche de l'auteur
- La barre dorée de progression n'est pas encore visible (JS non implémenté)

- [ ] **Étape 9 : Commit**

```bash
git add index.html
git commit -m "html: scroll-progress, ornaments, featured review, suppression prix placeholders"
```

---

## Task 7 : JS — Scroll progress bar + Parallaxe hero

**Fichiers :**
- Modifier : `script.js`

- [ ] **Étape 1 : Ajouter le scroll progress en début de script**

Dans `script.js`, ajouter au tout début (avant les lignes existantes) :

```js
// Scroll progress bar
const scrollProgress = document.getElementById('scroll-progress');
if (scrollProgress) {
  window.addEventListener('scroll', () => {
    const total = document.documentElement.scrollHeight - window.innerHeight;
    const progress = total > 0 ? (window.scrollY / total) * 100 : 0;
    scrollProgress.style.width = progress + '%';
  }, { passive: true });
}
```

Note : le CSS de `#scroll-progress` a été ajouté dans `style.css` à la Task 1 — ne pas le dupliquer ici.

- [ ] **Étape 2 : Ajouter le parallaxe sur l'image hero**

Dans `script.js`, après le bloc scroll-progress, ajouter :

```js
// Parallaxe image hero
const heroImg = document.querySelector('.hero-image img');
if (heroImg) {
  window.addEventListener('scroll', () => {
    if (window.scrollY < window.innerHeight) {
      heroImg.style.transform = `translateY(${window.scrollY * 0.15}px)`;
    }
  }, { passive: true });
}
```

Note : le listener scroll du nav existant doit rester — ajouter ce code séparément, ne pas fusionner les listeners.

- [ ] **Étape 3 : Vérification visuelle**

Ouvrir `index.html`. Scroller lentement vers le bas :
- La fine ligne dorée de 2px s'étend en haut de page proportionnellement au scroll
- L'image hero se décale légèrement vers le haut pendant le scroll (visible sur les 100 premiers vh)
- La barre dorée atteint 100% de largeur en bas de page

- [ ] **Étape 4 : Commit**

```bash
git add script.js
git commit -m "feat: scroll progress bar dorée et parallaxe image hero"
```

---

## Task 8 : JS — Stagger + micro-blur sur révélations (remplace système existant)

**Fichiers :**
- Modifier : `script.js`

- [ ] **Étape 1 : Remplacer le système de reveal dans script.js**

Trouver et remplacer le bloc reveal existant en entier :

```js
// AVANT — à supprimer entièrement :
const revealEls = document.querySelectorAll('.salon-text, .salon-images, ...');
revealEls.forEach((el, i) => {
  el.classList.add('reveal');
  el.style.transitionDelay = (i % 6) * 60 + 'ms';
});
const obs = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      obs.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });
revealEls.forEach(el => obs.observe(el));
```

Remplacer par :

```js
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
```

- [ ] **Étape 2 : Vérification visuelle**

Ouvrir `index.html`, scroller jusqu'à la section Prestations. Les 9 cartes de service doivent entrer en stagger progressif (chaque carte ~60ms après la précédente) avec l'effet de mise au point (blur→net). Vérifier aussi la section Marques (3 cartes en stagger 80ms) et l'Équipe (6 cartes en stagger 60ms).

- [ ] **Étape 3 : Commit**

```bash
git add script.js
git commit -m "feat: stagger micro-blur sur révélations au scroll"
```

---

## Task 9 : JS — Entrée scénarisée du titre hero

**Fichiers :**
- Modifier : `script.js`

- [ ] **Étape 1 : Ajouter l'animation du titre hero au chargement**

Dans `script.js`, ajouter en tout début du fichier (avant le scroll-progress) :

```js
// Entrée scénarisée du titre hero
(function animateHeroTitle() {
  const title = document.querySelector('.hero-title');
  if (!title) return;

  // Respecter prefers-reduced-motion
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const html = title.innerHTML.replace('<br>', '|||');
  const parts = html.split('|||');
  if (parts.length < 2) return;

  title.innerHTML = parts.map(p =>
    `<span class="hero-line" style="display:block;opacity:0;transform:translate(-12px,8px);will-change:opacity,transform">${p}</span>`
  ).join('');

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      title.querySelectorAll('.hero-line').forEach((line, i) => {
        setTimeout(() => {
          line.style.transition = 'opacity 0.8s ease-out, transform 0.8s ease-out';
          line.style.opacity = '1';
          line.style.transform = 'translate(0,0)';
        }, i * 120);
      });
    });
  });
})();
```

Note : le double `requestAnimationFrame` garantit que le navigateur a peint l'état initial (opacité 0) avant de déclencher la transition.

- [ ] **Étape 2 : Vérification visuelle**

Recharger `index.html` (Ctrl+Shift+R pour éviter le cache). La ligne "L'élégance," entre en glissant légèrement de la gauche, puis 120ms plus tard la ligne "au naturel." fait de même. L'animation ne se rejoue pas au scroll, uniquement au chargement.

- [ ] **Étape 3 : Vérification accessibilité**

Dans les DevTools du navigateur, simuler `prefers-reduced-motion: reduce` (DevTools > Rendering > Emulate CSS media feature > prefers-reduced-motion: reduce). Recharger la page. Le titre doit apparaître immédiatement sans animation.

- [ ] **Étape 4 : Commit**

```bash
git add script.js
git commit -m "feat: entrée scénarisée du titre hero au chargement"
```

---

## Task 10 : Blog — Cohérence nav (underline actif)

**Fichiers :**
- Modifier : `blog.html`

- [ ] **Étape 1 : Ajouter la classe active sur le lien Journal dans la nav**

Dans `blog.html`, trouver dans la nav desktop le lien vers `blog.html` :

```html
<li><a href="blog.html" class="active">Journal</a></li>
```

Ce lien a déjà la classe `active` dans `blog.html`. La règle CSS `.nav-links a.active::after { width: 100%; }` ajoutée à la Task 2 va automatiquement afficher l'underline permanent. Vérifier que c'est bien le cas.

- [ ] **Étape 2 : Vérification visuelle**

Ouvrir `blog.html`. Vérifier que le lien "Journal" dans la navigation desktop affiche l'underline en permanence (la ligne sous le mot est toujours visible, pas seulement au hover). Les autres liens doivent toujours animer au hover uniquement.

- [ ] **Étape 3 : Commit**

```bash
git add blog.html
git commit -m "style: underline actif nav sur page blog"
```

---

## Auto-revue contre la spec

| Spec § | Tâche couverte | Statut |
|--------|----------------|--------|
| 1. Grain de film | Task 1 | ✓ |
| 2. Scroll progress | Task 7 | ✓ |
| 3. Espacement sections | Task 1 | ✓ |
| 4. Nav underline animé | Task 2 | ✓ |
| 5. Shine .cta-btn | Task 3 | ✓ |
| 6. Fill directionnel .cta-ghost | Task 3 | ✓ |
| 7. Transition nav cubic-bezier | Task 2 | ✓ |
| 8. Parallaxe hero | Task 7 | ✓ |
| 9. Stagger + micro-blur | Task 8 | ✓ |
| 10. Entrée titre hero | Task 9 | ✓ |
| 11. Guillemets décoratifs | Task 5 | ✓ |
| 12. Review featured | Task 5 + Task 6 | ✓ |
| 13. Séparateurs ornementaux | Task 5 + Task 6 | ✓ |
| 14. Suppression prix placeholders | Task 6 | ✓ |
| 15. CTA Planity enrichi | Task 5 + Task 6 | ✓ |
| Accessibilité prefers-reduced-motion | Task 4 + Task 9 | ✓ |
| Retrait hover scale hero img | Task 4 | ✓ |
| Blog nav cohérence | Task 10 | ✓ |
