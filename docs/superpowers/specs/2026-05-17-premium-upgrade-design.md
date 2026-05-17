# Prestige Coiffure — Upgrade Premium
**Date :** 2026-05-17  
**Direction :** Élégance éditoriale  
**Périmètre :** `index.html`, `style.css`, `script.js` (+ `blog.css` pour cohérence nav)

---

## Contexte

Le site Prestige Coiffure dispose d'une base solide — typographie éditoriale (Cormorant Garamond + Manrope + JetBrains Mono), palette crème/sauge/or cohérente, structure claire. Ce document spécifie les 15 améliorations validées pour élever le site au niveau "vraiment premium" sans toucher à l'identité visuelle ni à la structure des pages.

---

## 1. Grain de film — fond global

**Fichier :** `style.css`

Ajouter un pseudo-élément `body::before` avec un filtre SVG inline de bruit (feTurbulence + feColorMatrix) pour simuler un grain de film photographique :

```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  opacity: 0.035;
  background-image: url("data:image/svg+xml,..."); /* SVG noise inline */
}
```

- Opacity : 3.5% — perceptible à l'œil, invisible sur capture d'écran
- `pointer-events: none` et `z-index: 9999` — ne bloque rien, toujours au-dessus
- Le SVG de bruit est généré via `feTurbulence baseFrequency="0.65"` + `feColorMatrix` pour limiter aux tons neutres

---

## 2. Ligne de progression dorée au scroll

**Fichiers :** `index.html` (élément HTML), `style.css` (style), `script.js` (logique)

Un élément `<div id="scroll-progress">` fixé en haut de page :

```css
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

JS : calculer `scrollY / (scrollHeight - innerHeight) * 100` à chaque événement scroll et mettre à jour `style.width`.

---

## 3. Espacement des sections

**Fichier :** `style.css`

| Propriété | Avant | Après |
|-----------|-------|-------|
| `section { padding }` | `100px 32px` | `120px 48px` |
| `.hero { padding }` | `120px 32px 60px` | `120px 48px 80px` |
| `.signature-band { padding }` | `72px 32px` | `88px 48px` |
| `.cta-band { padding }` | `80px 32px` | `96px 48px` |

Ne pas modifier les paddings mobiles (max-width: 880px) qui restent à 22-32px.

---

## 4. Navigation — underline animé

**Fichier :** `style.css`

Remplacer le `color` hover des liens nav par un underline animé gauche→droite :

```css
.nav-links a {
  position: relative;
  /* retirer le color transition */
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

Le lien actif (ex. `blog.html` dans la nav de la page blog) a l'underline permanent.

---

## 5. Effet "shine" sur `.cta-btn`

**Fichier :** `style.css`

Un reflet blanc qui traverse le bouton au hover :

```css
.cta-btn {
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
}
.cta-btn:hover::before { left: 125%; }
```

S'applique à tous les `.cta-btn` (sage, dark, gold).

---

## 6. Remplissage directionnel `.cta-ghost`

**Fichier :** `style.css`

Remplacer le `background` instantané par un remplissage gauche→droite :

```css
.cta-ghost {
  position: relative;
  overflow: hidden;
  /* conserver border, couleur, etc. */
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
}
.cta-ghost:hover::before { transform: scaleX(1); }
.cta-ghost:hover { color: var(--cream); border-color: var(--ink); }
```

---

## 7. Transition nav cubic-bezier

**Fichier :** `style.css`

```css
header.topnav {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
```

Remplace `transition: all 0.3s ease` — courbe élastique douce, apparition/disparition du fond au scroll perçue comme plus fluide.

---

## 8. Parallaxe image hero

**Fichier :** `script.js`

Au scroll, décaler l'image hero de `scrollY * 0.15` vers le haut :

```js
const heroImg = document.querySelector('.hero-image img');
window.addEventListener('scroll', () => {
  if (heroImg && window.scrollY < window.innerHeight) {
    heroImg.style.transform = `translateY(${window.scrollY * 0.15}px)`;
  }
});
```

- Limité à `scrollY < innerHeight` — actif uniquement quand le hero est visible
- Ne pas combiner avec le hover `scale(1.03)` existant — retirer ce hover ou l'intégrer dans le même transform

---

## 9. Stagger + micro-blur sur révélations au scroll

**Fichier :** `script.js`

Remplacer le système de reveal existant. Nouvelle animation :

```css
/* style.css */
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
```

Pour le stagger sur les grilles, appliquer un délai croissant de `index * 60ms` aux enfants directs :
- `.services-grid .service` : `index * 60ms` (9 items → 0 à 480ms)
- `.marques-grid .marque-card` : `index * 80ms` (3 items → 0 à 160ms)
- `.equipe-grid .person-card` : `index * 60ms` (6 items → 0 à 300ms)
- `.reviews-list .review` : `index * 100ms` (3 items → 0 à 200ms)

Le `transitionDelay` est appliqué via JS au moment de l'ajout de la classe `reveal`.

---

## 10. Entrée scénarisée du titre hero

**Fichier :** `script.js`

Au chargement de la page (`DOMContentLoaded`), animer les deux lignes du titre hero :

Technique : le `h1.hero-title` contient un `<br>` natif. En JS, remplacer le `<br>` par un séparateur de span :

```js
document.addEventListener('DOMContentLoaded', () => {
  const title = document.querySelector('.hero-title');
  if (!title) return;
  // Remplacer le <br> par un marqueur, puis splitter
  const html = title.innerHTML.replace('<br>', '|||');
  const parts = html.split('|||');
  title.innerHTML = parts.map(p =>
    `<span class="hero-line" style="display:block;opacity:0;transform:translate(-12px,8px)">${p}</span>`
  ).join('');
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
```

---

## 11. Guillemets décoratifs dans les avis

**Fichier :** `style.css`

```css
.review {
  position: relative;
  overflow: hidden;
}
.review::before {
  content: '\201C'; /* guillemet ouvrant typographique */
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

---

## 12. Premier avis mis en exergue

**Fichier :** `style.css` + `index.html`

Ajouter la classe `.review--featured` sur le premier `.review` dans le HTML :

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

---

## 13. Séparateurs ornementaux

**Fichier :** `index.html` + `style.css`

Deux séparateurs placés :
1. Entre la section `.hero` et `#le-salon`
2. Entre `#marques` et `#equipe`

Structure HTML :
```html
<div class="ornament-divider" aria-hidden="true">
  <span></span>
  <span class="diamond">◆</span>
  <span></span>
</div>
```

```css
.ornament-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 0 48px;
  height: 48px;
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

---

## 14. Suppression des placeholders de prix

**Fichier :** `index.html`

Retirer les 9 éléments `<div class="service-price">` de la section `#prestations`. Les cartes de prestations n'affichent plus que `.service-name` et `.service-desc`.

Retirer également les crochets `[tarif Planity]` dans la description de la section (ligne `.section-lede`).

---

## 15. CTA Planity enrichi

**Fichier :** `index.html` + `style.css`

Dans `.services-cta`, ajouter avant le bouton :

```html
<div class="services-cta-meta">9 prestations · Tarifs détaillés et disponibilités en ligne</div>
```

```css
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

---

## Périmètre hors scope

- Section équipe (photos/placeholders) : inchangée
- Page `blog.html` : seule la nav reçoit l'underline animé (cohérence)
- `blog.css` : aucune modification
- Structure HTML des pages : inchangée (sauf ajouts d'éléments décrits ci-dessus)
- Responsive mobile : les animations blur/stagger sont désactivées via `prefers-reduced-motion` media query

---

## Ordre d'implémentation suggéré

1. CSS global (grain, espacement, nav, boutons, transitions) — `style.css`
2. HTML (scroll-progress, ornements, classe featured, suppression prix, meta CTA) — `index.html`
3. JS (scroll-progress, parallaxe, stagger+blur, titre hero) — `script.js`
4. Cohérence nav blog — `blog.html` (underline actif uniquement)

---

## Accessibilité

- `prefers-reduced-motion: reduce` : désactiver blur, parallaxe, stagger et entrée titre hero — garder uniquement opacity
- Tous les pseudo-éléments décoratifs ont `aria-hidden="true"` ou `pointer-events: none`
- Le scroll-progress a `role="progressbar"` et `aria-hidden="true"`
