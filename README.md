# Prestige Coiffure — Site web

Site vitrine statique du salon Prestige Coiffure (12 boulevard de la République, 71100 Chalon-sur-Saône). Salon indépendant depuis 2009, ambassadeur Davines France. Aucun framework ni build tool : HTML5 + CSS3 + vanilla JS, déployable par drag-and-drop sur Netlify.

---

## Structure

```
prestige_site/
├── index.html                  # Page d'accueil (one-page principale)
├── blog.html                   # Liste des articles du journal
├── 404.html                    # Page d'erreur personnalisée
├── sitemap.xml                 # Sitemap XML pour Search Console
├── robots.txt                  # Directives robots
├── site.webmanifest            # Web App Manifest (PWA légère)
├── _headers                    # En-têtes HTTP Netlify (CSP, sécurité)
├── .editorconfig               # Conventions éditeur
├── .prettierrc                 # Config Prettier
├── .gitignore
│
├── css/
│   ├── style.css               # Styles globaux (variables, nav, footer, composants)
│   ├── blog.css                # Styles spécifiques au journal et aux cartes d'articles
│   ├── article.css             # Styles de la page article individuelle
│   ├── service.css             # Styles des pages de prestation
│   └── legal.css               # Styles des pages légales
│
├── js/
│   ├── script.js               # Menu mobile, scroll, animations générales
│   ├── mobile-cta.js           # Bandeau CTA sticky mobile (appel / RDV)
│   └── theme-toggle.js         # Basculement dark / light mode
│
├── assets/
│   ├── logo.png                # Logo officiel (PNG, fond transparent)
│   ├── og-image.jpg            # Image Open Graph (1200×630)
│   └── favicon.svg             # Favicon SVG (lettre P, fond encre)
│
├── articles/
│   └── head-spa.html           # Article : "Le head spa — une parenthèse qui change tout"
│
├── services/
│   ├── coupes-femme.html
│   ├── coupes-homme.html
│   ├── coupes-enfant.html
│   ├── barberie.html
│   ├── coloration.html
│   ├── balayage.html
│   ├── patine-gloss.html
│   ├── lissage-ybera.html
│   ├── extensions-great-lengths.html
│   ├── head-spa.html
│   └── coiffure-mariee.html
│
├── legal/
│   ├── mentions-legales.html
│   └── politique-confidentialite.html
│
└── photosalon/                 # Photos réelles du salon (à compléter)
```

---

## Stack

- **HTML5** — sémantique, JSON-LD Schema.org sur chaque page (HairSalon, Service, Article)
- **CSS3** — custom properties uniquement, pas de preprocesseur. Dark mode via `[data-theme="dark"]` sur `<html>`
- **Vanilla JS ES2018+** — trois fichiers distincts, chargés en `defer`
- **Google Fonts** — Cormorant Garamond (titres), Manrope (corps), JetBrains Mono (labels)
- **Aucun build** — ouvrir `index.html` dans un navigateur suffit en local

---

## Pages

| Fichier | Rôle |
|---|---|
| `index.html` | Page d'accueil : hero, le salon, prestations, marques, équipe, avis, contact |
| `blog.html` | Grille des articles du journal avec filtres par catégorie |
| `articles/head-spa.html` | Article long-format sur le head spa |
| `services/coupes-femme.html` | Page prestation : coupes femme |
| `services/coupes-homme.html` | Page prestation : coupes homme |
| `services/coupes-enfant.html` | Page prestation : coupes enfant |
| `services/barberie.html` | Page prestation : barberie |
| `services/coloration.html` | Page prestation : coloration & sans ammoniaque |
| `services/balayage.html` | Page prestation : balayage, mèches, ombré |
| `services/patine-gloss.html` | Page prestation : patine & gloss |
| `services/lissage-ybera.html` | Page prestation : soins profonds & lissage Ybera |
| `services/extensions-great-lengths.html` | Page prestation : extensions Great Lengths |
| `services/head-spa.html` | Page prestation : head spa |
| `services/coiffure-mariee.html` | Page prestation : coiffures de mariée & cérémonie |
| `legal/mentions-legales.html` | Mentions légales |
| `legal/politique-confidentialite.html` | Politique de confidentialité |
| `404.html` | Page d'erreur 404 personnalisée (noindex) |

---

## Comment ajouter un article au blog

1. **Dupliquer le template** : copier `articles/head-spa.html` → `articles/<slug>.html`
2. **Mettre à jour le `<head>`** : title, meta description, og:title, og:description, og:url, canonical, article:published_time, article:author
3. **Mettre à jour le JSON-LD** : `"headline"`, `"datePublished"`, `"description"`, `"url"`, `"author"`
4. **Écrire le contenu** : remplacer le texte dans `.article-body`, mettre à jour `.article-header` (titre, eyebrow, date, auteur, temps de lecture)
5. **Ajouter la carte dans `blog.html`** : copier un bloc `<article class="article-card">` existant, mettre à jour le titre, l'extrait, la date, les tags et le lien `href`
6. **Ajouter dans `sitemap.xml`** : copier un `<url>` existant, mettre à jour `<loc>` et `<lastmod>`

---

## Comment mettre à jour la note Google

La note apparaît à deux endroits dans `index.html` :

1. **Section hero** (ligne ~155) : `4,6</span>/5 · 185 avis`
2. **Section "Le salon"** (stat-cell) : `4,6<span class="small">/5</span>` + `Sur 185 avis Google`
3. **Section "Avis"** : `<div class="big-rating">4,6</div>` + `<div class="count">185 avis</div>`
4. **JSON-LD** (`<script type="application/ld+json">`) : `"ratingValue": "4.6"` et `"reviewCount": "185"`

Chercher `185 avis` dans `index.html` pour trouver rapidement tous les emplacements.

---

## Comment changer un prix de service

Chaque page `services/<slug>.html` contient un bloc de métriques (`.service-metrics` ou `.service-price`). Éditer la valeur correspondante directement dans le fichier HTML. Les tarifs détaillés sont aussi disponibles sur la fiche Planity — si vous pointez tout vers Planity, les balises `<meta>` de description suffisent.

---

## Déploiement

**Recommandation : Netlify**

- **Drag-and-drop** : aller sur [netlify.com/drop](https://app.netlify.com/drop), déposer le dossier entier. En ligne en 30 secondes.
- **Git connect** : relier le dépôt GitHub à Netlify → déploiement automatique à chaque `git push`.

Le fichier `_headers` à la racine est automatiquement lu par Netlify et applique les en-têtes HTTP de sécurité (CSP, HSTS, X-Frame-Options…).

Pour un domaine custom (`prestige-chalon.fr`), configurer le DNS dans Netlify → Settings → Domain management.

---

## Validation après déploiement

- **Google Search Console** : soumettre `sitemap.xml` après mise en ligne
- **Rich Results Test** : [search.google.com/test/rich-results](https://search.google.com/test/rich-results) — vérifier que le JSON-LD HairSalon est reconnu
- **OpenGraph** : [opengraph.xyz](https://www.opengraph.xyz) — vérifier les previews réseaux sociaux
- **PageSpeed Insights** : [pagespeed.web.dev](https://pagespeed.web.dev) — mesurer les Core Web Vitals

---

## Conventions de code

- **Variables CSS** : toutes les couleurs et espacements passent par les custom properties dans `:root` (`--bg`, `--ink`, `--sage`, `--wine`, `--gold-bright`…). Ne pas coder de couleur en dur dans les composants.
- **Classes HTML** : kebab-case strict (`service-page-link`, `hero-eyebrow`, `contact-info-block`)
- **`data-track`** : tous les CTAs cliquables portent un attribut `data-track="<identifiant>"` pour faciliter le suivi analytics (ex. `data-track="cta-book-hero"`)
- **Dark mode** : les surcharges dark se font via `:root[data-theme="dark"] .ma-classe` dans `style.css`, jamais via media query `prefers-color-scheme` (le JS gère la persistance)
- **Images** : toujours un `alt` descriptif ; les images décoratives portent `alt=""`
