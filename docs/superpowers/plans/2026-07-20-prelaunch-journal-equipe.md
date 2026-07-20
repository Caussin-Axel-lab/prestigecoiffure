# Pré-lancement : retrait Journal + refonte équipe — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le journal/blog inaccessible sans supprimer ses fichiers, et remplacer la section équipe par des cartes « filigrane » sans photo, puis pousser sur GitHub.

**Architecture:** Site statique HTML/CSS multi-pages. Les liens « Journal » sont dupliqués dans la nav/footer de chaque page ; on les retire par script + vérification grep. La section équipe est refondue en HTML (`index.html`) + CSS (`css/style.css`), filigrane piloté par les variables de thème existantes (dark mode inclus).

**Tech Stack:** HTML5, CSS custom-properties (thème clair/sombre), service worker (cache-busting par version). Pas de framework, pas de suite de tests automatisée → la vérification se fait par assertions `grep` et contrôle visuel navigateur.

**Spec de référence:** `docs/superpowers/specs/2026-07-20-prelaunch-journal-equipe-design.md`

**Note environnement:** commandes shell = Git Bash (outil Bash). `sed -i` fonctionne. Chemin projet : `/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test`.

---

## File Structure

- `index.html` — retrait 3 liens Journal (nav desktop, nav mobile, footer) **+** refonte de la section `#equipe`.
- `services/*.html` (11 pages) — retrait des liens Journal (nav desktop, nav mobile, footer).
- `services/head-spa.html` — en plus : retrait du bloc `.service-related` (lien article) + de l'include `css/blog.css` devenu inutile.
- `404.html`, `legal/mentions-legales.html`, `legal/politique-confidentialite.html`, `articles/head-spa.html` — retrait des liens Journal nav/footer.
- `sitemap.xml` — retrait des entrées `blog.html` et `articles/head-spa.html`.
- `sw.js` — retrait de `/blog.html` et `/css/blog.css` du précache + bump `CACHE_VERSION`.
- `css/style.css` — remplacement des styles `.person-card` / `.person-photo` / `.person-info` par les cartes filigrane.
- **Conservés intacts :** `blog.html`, `css/blog.css`, contenu de `articles/head-spa.html`.

---

## Task 1 : Retirer tous les liens « Journal » (nav + footer, toutes pages)

**Files:**
- Modify: `index.html`, `404.html`, `articles/head-spa.html`, `legal/mentions-legales.html`, `legal/politique-confidentialite.html`, `services/*.html`

Chaque lien Journal est sur sa propre ligne et contient à la fois `blog.html` et `Journal` (y compris la variante `class="active"` de `services/head-spa.html` et le lien mobile autonome de `index.html`). On supprime donc toute ligne contenant ces deux motifs.

- [ ] **Step 1 : État avant (doit lister les liens à supprimer)**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -rn "blog.html" index.html 404.html articles/head-spa.html legal/ services/ | grep "Journal"
```
Expected: ~40 lignes listées (3 sur index, 3 par page service, 3 sur 404/legal/articles…).

- [ ] **Step 2 : Supprimer les lignes de lien Journal**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
for f in index.html 404.html articles/head-spa.html legal/mentions-legales.html legal/politique-confidentialite.html services/*.html; do
  sed -i '/blog\.html/{/Journal/d;}' "$f"
done
```

- [ ] **Step 3 : Vérifier qu'il ne reste aucun lien Journal**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -rn "Journal" index.html 404.html articles/ legal/ services/
```
Expected: aucune sortie (exit code 1). Si une ligne subsiste, la retirer à la main avec Edit.

- [ ] **Step 4 : Vérifier qu'aucune balise n'a été cassée (comptage `<li>` cohérent)**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -c "nav-links" index.html && grep -n "Prendre RDV" index.html | head -1
```
Expected: la nav desktop existe toujours, le CTA « Prendre RDV » est intact. (Contrôle rapide de non-régression structurelle.)

- [ ] **Step 5 : Commit**

```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git add -A
git commit -m "feat(prelaunch): retire les liens Journal de la nav et du footer"
```

---

## Task 2 : `services/head-spa.html` — retrait du bloc article + include blog.css

**Files:**
- Modify: `services/head-spa.html`

Après Task 1, le lien Journal de cette page est déjà retiré. Il reste : (a) le bloc « Pour aller plus loin » qui pointe vers l'article devenu inaccessible, (b) l'include `css/blog.css` désormais inutilisé (vérifié : aucune classe blog.css présente sur la page hormis `.active` du lien Journal supprimé).

- [ ] **Step 1 : Retirer le bloc `.service-related` (lien article)**

Edit — supprimer ces lignes (le commentaire + le bloc complet) :
```html
<!-- Pour aller plus loin -->
<div class="service-related">
  <p class="service-related-label">Pour aller plus loin</p>
  <a href="../articles/head-spa.html" class="service-related-link">Lire notre article : Le head spa, une parenthèse qui change tout →</a>
</div>
```
La section suivante `<section class="service-related-services">` (« Vous aimerez aussi ») est **conservée**.

- [ ] **Step 2 : Retirer l'include blog.css**

Edit — supprimer cette ligne :
```html
<link rel="stylesheet" href="../css/blog.css">
```
Conserver `../css/style.css` et `../css/service.css`.

- [ ] **Step 3 : Vérifier**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -n "articles/\|blog.css\|service-related-label" services/head-spa.html
```
Expected: aucune sortie (plus de lien article, plus d'include blog.css, plus de label orphelin). La classe `service-related-services` peut rester (c'est l'autre bloc, conservé) — vérifier qu'elle est bien encore là :
```bash
grep -c "service-related-services" services/head-spa.html
```
Expected: `1` (ou plus), section conservée.

- [ ] **Step 4 : Commit**

```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git add services/head-spa.html
git commit -m "feat(prelaunch): retire le lien article et l'include blog.css sur head-spa"
```

---

## Task 3 : Nettoyer `sitemap.xml`

**Files:**
- Modify: `sitemap.xml`

- [ ] **Step 1 : Repérer les entrées à retirer**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -n "blog.html\|articles/head-spa.html" sitemap.xml
```
Expected: 2 lignes `<loc>` (blog.html ~l.10, articles/head-spa.html ~l.16).

- [ ] **Step 2 : Supprimer les deux blocs `<url>…</url>` correspondants**

Edit — pour chacune des deux URLs, supprimer le bloc `<url>` entier qui la contient (typiquement `<url>`, `<loc>`, `<lastmod>`/`<priority>`, `</url>`). Lire la zone autour de chaque `<loc>` pour supprimer le bloc complet sans casser le XML.

- [ ] **Step 3 : Vérifier**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -c "blog.html\|articles/" sitemap.xml
```
Expected: `0`. Vérifier aussi l'équilibre des balises :
```bash
grep -c "<url>" sitemap.xml && grep -c "</url>" sitemap.xml
```
Expected: les deux comptes sont égaux.

- [ ] **Step 4 : Commit**

```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git add sitemap.xml
git commit -m "feat(prelaunch): retire blog et article du sitemap"
```

---

## Task 4 : Mettre à jour `sw.js` (précache + bump version)

**Files:**
- Modify: `sw.js`

- [ ] **Step 1 : Retirer les deux entrées du précache**

Edit — dans `PRECACHE_URLS`, supprimer ces deux lignes :
```js
  '/blog.html',
```
```js
  '/css/blog.css',
```

- [ ] **Step 2 : Bumper la version de cache**

Edit — remplacer :
```js
const CACHE_VERSION = 'v1.0.0';
```
par :
```js
const CACHE_VERSION = 'v1.1.0';
```

- [ ] **Step 3 : Vérifier**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -n "blog" sw.js; grep -n "CACHE_VERSION" sw.js
```
Expected: plus aucune occurrence `blog` ; `CACHE_VERSION = 'v1.1.0'`.

- [ ] **Step 4 : Commit**

```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git add sw.js
git commit -m "feat(prelaunch): purge blog du service worker + bump cache v1.1.0"
```

---

## Task 5 : Refonte HTML de la section équipe (`index.html`)

**Files:**
- Modify: `index.html` (section `#equipe`, actuellement ~l.553-605)

Conserver l'en-tête (`section-eyebrow`, `section-title`, `section-lede`). Remplacer les 6 `.person-card` (qui contiennent `.person-photo`) par des cartes avec initiale en filigrane. Noms et rôles **inchangés**.

- [ ] **Step 1 : Remplacer le contenu de `.equipe-grid`**

Edit — remplacer le bloc `<div class="equipe-grid"> … </div>` par :
```html
    <div class="equipe-grid">
      <div class="person-card">
        <span class="person-mono" aria-hidden="true">S</span>
        <div class="person-info">
          <h3>Stéphane</h3>
          <div class="role">Gérant · Depuis 2009</div>
        </div>
      </div>
      <div class="person-card">
        <span class="person-mono" aria-hidden="true">K</span>
        <div class="person-info">
          <h3>Kelly</h3>
          <div class="role">Manager · Conseil & accompagnement</div>
        </div>
      </div>
      <div class="person-card">
        <span class="person-mono" aria-hidden="true">A</span>
        <div class="person-info">
          <h3>Aurélie</h3>
          <div class="role">Spécialiste femme · Technique</div>
        </div>
      </div>
      <div class="person-card">
        <span class="person-mono" aria-hidden="true">C</span>
        <div class="person-info">
          <h3>Camille</h3>
          <div class="role">Coiffeuse polyvalente</div>
        </div>
      </div>
      <div class="person-card">
        <span class="person-mono" aria-hidden="true">M</span>
        <div class="person-info">
          <h3>Mathilde</h3>
          <div class="role">Coiffeuse polyvalente</div>
        </div>
      </div>
      <div class="person-card">
        <span class="person-mono" aria-hidden="true">A</span>
        <div class="person-info">
          <h3>Axel</h3>
          <div class="role">Coiffeur barbier</div>
        </div>
      </div>
    </div>
```

- [ ] **Step 2 : Vérifier la structure**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -c "person-card" index.html; grep -c "person-mono" index.html; grep -c "person-photo" index.html
```
Expected: `person-card` = 6, `person-mono` = 6, `person-photo` = **0** (plus aucune fausse-photo dans le HTML).

- [ ] **Step 3 : Commit**

```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git add index.html
git commit -m "feat(equipe): remplace les fausses cartes-photo par des cartes filigrane"
```

---

## Task 6 : Styles des cartes filigrane (`css/style.css`)

**Files:**
- Modify: `css/style.css` (bloc équipe ~l.997-1048)

Remplacer `.person-photo` (fausse photo) par le filigrane, adapter `.person-card` et `.person-info`. Conserver `.equipe-grid` et les styles typographiques `h3` / `.role`.

- [ ] **Step 1 : Remplacer le bloc CSS de l'équipe**

Edit — remplacer les règles depuis `.person-card {` jusqu'à la fin de `.person-info .role { … }` par :
```css
  .person-card {
    position: relative;
    overflow: hidden;
    background: var(--bg-soft);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 28px 26px;
    transition: all 0.3s ease;
  }
  .person-card:hover { transform: translateY(-3px); box-shadow: 0 10px 30px -10px rgba(0,0,0,0.12); }
  .person-mono {
    position: absolute;
    right: -6px;
    bottom: -34px;
    font-family: 'Cormorant Garamond', serif;
    font-size: 150px;
    line-height: 1;
    font-style: italic;
    font-weight: 600;
    color: var(--gold);
    opacity: 0.10;
    pointer-events: none;
    user-select: none;
  }
  :root[data-theme="dark"] .person-mono {
    color: var(--gold-bright);
    opacity: 0.11;
  }
  .person-info { position: relative; }
  .person-info h3 {
    font-family: 'Cormorant Garamond', serif;
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 4px;
    color: var(--ink);
  }
  .person-info .role {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--sage-deep);
  }
```
(`.equipe-grid` et ses media-queries juste au-dessus restent inchangés.)

- [ ] **Step 2 : Vérifier qu'il ne reste aucune trace de l'ancienne fausse photo**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -n "person-photo" css/style.css; grep -n "person-mono" css/style.css
```
Expected: `person-photo` → aucune sortie ; `person-mono` → présent (2 occurrences : règle de base + override dark).

- [ ] **Step 3 : Commit**

```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git add css/style.css
git commit -m "feat(equipe): styles cartes filigrane or, clair et dark mode"
```

---

## Task 7 : Vérification visuelle & sweep final

**Files:** aucun (vérification)

- [ ] **Step 1 : Servir le site en local**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
python -m http.server 8080
```
(ou toute autre méthode de serveur statique). Ouvrir `http://localhost:8080`.

- [ ] **Step 2 : Contrôles navigateur**

Vérifier manuellement :
- Menu (desktop + mobile) et footer : **aucun** lien « Journal ».
- Section équipe : 6 cartes, initiale en filigrane or discrète, prénom nettement lisible par-dessus.
- Bascule thème (bouton lune/soleil) : en **dark mode**, filigrane or clair visible mais discret, prénom lisible.
- Réduire la fenêtre : grille passe 3 → 2 → 1 colonnes (breakpoints 800px / 500px).
- Page `services/head-spa.html` : plus de bloc « Pour aller plus loin », section « Vous aimerez aussi » toujours présente, mise en page intacte.

- [ ] **Step 3 : Sweep grep final (aucun lien mort)**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
grep -rn "Journal" *.html services/ legal/ articles/ ; echo "---" ; grep -rn "articles/head-spa" *.html services/ sitemap.xml
```
Expected: aucune sortie des deux côtés (le fichier `blog.html` et le contenu de `articles/head-spa.html` restent sur le disque mais ne sont plus référencés par une page de production).

- [ ] **Step 4 : Arrêter le serveur** (Ctrl-C).

---

## Task 8 : Push GitHub (après validation utilisateur)

**Files:** aucun

> ⚠️ Ne lancer cette tâche qu'après validation explicite de l'utilisateur sur le rendu (Task 7).

- [ ] **Step 1 : Vérifier l'état et la branche**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git status && git log --oneline -8 && git remote -v && git branch --show-current
```
Expected: working tree clean, les commits des Tasks 1-6 présents, un remote `origin` configuré.

- [ ] **Step 2 : Push**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git push origin HEAD
```
Expected: push accepté. Si la branche courante n'a pas d'upstream : `git push -u origin <branche>`.

- [ ] **Step 3 : Confirmer**

Run:
```bash
cd "/c/Users/ozone/OneDrive/Bureau/prestige_site - projet test"
git status -sb
```
Expected: `## <branche>...origin/<branche>` sans « ahead ».

---

## Self-review (couverture spec)

- Retrait liens Journal nav/footer toutes pages → Task 1 ✓
- Bloc article + include blog.css sur head-spa → Task 2 ✓
- sitemap.xml (blog + article) → Task 3 ✓
- sw.js précache + bump version → Task 4 ✓
- Refonte HTML équipe (contenu conservé) → Task 5 ✓
- CSS filigrane or + dark mode + suppression person-photo → Task 6 ✓
- Vérif clair/sombre/responsive + sweep → Task 7 ✓
- Fichiers conservés (blog.html, blog.css, contenu article) → jamais supprimés ✓
- Push GitHub après validation → Task 8 ✓
