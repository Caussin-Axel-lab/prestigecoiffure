# Pré-lancement : retrait du Journal + refonte de la section équipe

**Date :** 2026-07-20
**Contexte :** Mise en ligne imminente du site Prestige Coiffure. Le journal/blog n'est pas prêt et sera réactivé plus tard. La présentation de l'équipe doit être retravaillée pour être esthétique sans dépendre de photos. Un backup de l'état actuel existe déjà en dehors de ce projet.

## Objectifs

1. Rendre le journal/blog **inaccessible et invisible** sans supprimer les fichiers (réactivation rapide plus tard).
2. Remplacer la présentation de l'équipe (actuellement des « fausses cartes-photo » : initiale géante dans un cadre dégradé façon emplacement photo vide) par une présentation assumée sans photo, cohérente avec l'identité du site et fonctionnelle en dark mode.

## Non-objectifs (YAGNI)

- Ne pas supprimer `blog.html`, `articles/`, `css/blog.css`.
- Ne pas modifier le contenu de l'équipe (6 personnes, noms, rôles inchangés).
- Aucun refactoring non lié.

---

## Partie 1 — Retrait du Journal/blog

Décision : **garder les fichiers, couper tous les accès** ; **retirer complètement** l'entrée « Journal » du menu (pas de version grisée).

### Liens de navigation & footer à retirer

Retirer chaque lien pointant vers `blog.html` (`href="blog.html"` ou `href="../blog.html"`) dans la nav desktop, la nav mobile et le footer des pages suivantes :

- `index.html` — nav desktop (l.106), nav mobile (l.143), footer (l.763)
- `services/*.html` (les 10 pages : balayage, barberie, coiffure-mariee, coloration, coupes-enfant, coupes-femme, coupes-homme, extensions-great-lengths, head-spa, lissage-ybera, patine-gloss) — nav desktop + nav mobile + footer (3 liens par page)
- `404.html`
- `legal/mentions-legales.html`
- `legal/politique-confidentialite.html`
- `articles/head-spa.html` (le fichier reste, mais on nettoie ses liens de nav/footer par cohérence)

Résultat menu : `Le salon · Prestations · Marques · L'équipe · ~~Journal~~ · Avis · Contact`.

### Lien d'article dans une page service

- `services/head-spa.html` : retirer **tout le bloc** `.service-related` (≈ l.321-324) qui contient le label « Pour aller plus loin » + le lien `../articles/head-spa.html`. Ne pas laisser le label orphelin. Le bloc voisin `.service-related-services` (« autres prestations ») est **conservé**.
- Vérifier l'include `css/blog.css` (l.38) sur cette page : `.service-related-link` est stylé dans `service.css`, donc `blog.css` est probablement inutile ici → le retirer s'il n'est utilisé par aucune classe de la page.

### SEO & PWA

- `sitemap.xml` : retirer les entrées `<url>` de `blog.html` **et** `articles/head-spa.html` (éviter que Google indexe des pages devenues inaccessibles).
- `sw.js` : retirer `'/blog.html'` (l.10) et `'/css/blog.css'` (l.13) de `PRECACHE_URLS`, **et** bumper `CACHE_VERSION` (`v1.0.0` → `v1.1.0`). Sans le bump, les visiteurs ayant déjà le site en cache continueraient de voir l'ancien shell (liens Journal inclus) ; le bump force l'installation du nouveau SW et la purge des anciens caches.

---

## Partie 2 — Refonte de la section équipe

Direction validée visuellement : **cartes « filigrane »**, filigrane teinté **or**, sans bouton, alignées à gauche, adaptatives en dark mode.

### Structure (HTML — `index.html`, section `#equipe`)

Conserver l'en-tête existant (`section-eyebrow`, `section-title`, `section-lede`). Remplacer les 6 `.person-card` actuels (qui contiennent `.person-photo` + `.person-info`) par des cartes simplifiées, une par personne, contenant :

- l'**initiale** en filigrane décoratif (élément dédié, ex. `.person-mono`, `aria-hidden`) ;
- le **prénom** (`<h3>`) ;
- le **rôle** (`.role`).

Contenu conservé à l'identique :

| Prénom | Rôle |
|--------|------|
| Stéphane | Gérant · Depuis 2009 |
| Kelly | Manager · Conseil & accompagnement |
| Aurélie | Spécialiste femme · Technique |
| Camille | Coiffeuse polyvalente |
| Mathilde | Coiffeuse polyvalente |
| Axel | Coiffeur barbier |

### Style (CSS — `css/style.css`)

- `.equipe-grid` : conserver la grille responsive existante (3 → 2 → 1 colonnes aux breakpoints 800px / 500px).
- `.person-card` : fond `--bg-soft`, bordure `--line`, rayon 4px, `position: relative`, `overflow: hidden`, padding aligné à gauche ; conserver l'effet hover (translate + ombre douce).
- **Supprimer** l'ancien `.person-photo` (et son `::after`) — le bloc « fausse photo » disparaît.
- Filigrane : élément d'initiale en `position:absolute`, coin bas-droit, `font-family:'Cormorant Garamond'` italique, très grande taille, `pointer-events:none`.
  - Couleur/opacité **clair** : `--gold` à ~0.10 d'opacité.
  - Couleur/opacité **sombre** : `--gold-bright` à ~0.11 d'opacité (léger surcroît pour rester visible sur fond sombre).
  - Piloté via les variables de thème existantes (`:root` / `:root[data-theme="dark"]`), pas de media query couleur en dur.
- `.person-info h3` (prénom) et `.role` : réutiliser les styles typographiques déjà en place (Cormorant Garamond pour le prénom, JetBrains Mono uppercase pour le rôle en `--sage-deep`), placés au-dessus du filigrane (`position:relative` ou z-index).

### Accessibilité

- L'initiale en filigrane est purement décorative → `aria-hidden="true"`, non focusable, contraste non requis (opacité décorative).
- Le prénom reste un vrai `<h3>` lisible ; aucun texte porté uniquement par le filigrane.

---

## Portée des fichiers touchés

- **Modifiés :** `index.html`, les 11 `services/*.html`, `404.html`, `legal/mentions-legales.html`, `legal/politique-confidentialite.html`, `articles/head-spa.html`, `sitemap.xml`, `sw.js`, `css/style.css`.
- **Conservés (fichiers non supprimés) :** `blog.html`, `css/blog.css`, et le **contenu** de l'article dans `articles/head-spa.html` (seuls ses liens de nav/footer sont nettoyés).

## Vérification

- Parcourir le site en local : plus aucun lien « Journal » cliquable ; aucun lien mort vers `articles/`.
- Recharger avec le nouveau SW (nouvelle `CACHE_VERSION`) : l'ancien shell est purgé.
- Section équipe : rendu correct en **clair et sombre**, filigrane or discret, 3/2/1 colonnes selon la largeur, prénom toujours parfaitement lisible.
- `grep -rn "blog.html\|Journal\|articles/" .` sur les fichiers HTML de production ne renvoie plus de lien actif (hors fichiers conservés blog.html/articles/ eux-mêmes).
