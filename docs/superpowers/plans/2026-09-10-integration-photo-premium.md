# Premium Photo Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retoucher les meilleures photographies existantes, produire des variantes responsives légères et les intégrer au site sans changer sa structure ni son contenu.

**Architecture:** Les fichiers actuels de `photosalon/` restent les masters intacts. Les retouches haute fidélité sont enregistrées sous `photosalon/retouched/`, puis un script déterministe piloté par manifeste fabrique les cadrages WebP/JPEG sous `photosalon/web/`; les pages utilisent `<picture>` et des classes de point focal partagées. Le salon conserve une signature naturelle et chaleureuse, tandis que les héros de prestations reçoivent un traitement cinématographique modéré.

**Tech Stack:** HTML5 statique, CSS3, JavaScript existant, outil intégré `image_gen` pour les retouches, Python 3 + Pillow 12.2 pour les cadrages/exports, PowerShell et Git pour la validation.

---

## File map

- Create: `scripts/photo-manifest.json` — inventaire, rôles, ratios, dimensions et points focaux.
- Create: `scripts/build-photo-derivatives.py` — génération reproductible des WebP/JPEG.
- Create: `scripts/build-og-image.py` — composition sociale déterministe à partir du salon et du logo.
- Create: `scripts/verify-photo-assets.py` — contrôle des fichiers, dimensions, poids et références HTML.
- Create: `photosalon/retouched/*.png` — masters retouchés non destructifs issus de l'outil d'image.
- Create: `photosalon/web/*-desktop.webp`, `*-desktop.jpg`, `*-mobile.webp`, `*-mobile.jpg` — fichiers servis par le site.
- Modify: `index.html` — `<picture>` du hero, du triptyque et de la cabine.
- Modify: `css/style.css` — cadrages responsives, overlays clair/sombre et focales de l'accueil.
- Modify: `services/balayage.html`, `services/barberie.html`, `services/coiffure-mariee.html`, `services/coloration.html`, `services/coupes-femme.html`, `services/coupes-homme.html`, `services/extensions-great-lengths.html`, `services/head-spa.html`, `services/patine-gloss.html` — héros locaux responsives.
- Modify: `services/coupes-enfant.html` — intégration cinématographique temporaire du visuel externe, sans prétendre qu'il s'agit d'une réalisation du salon.
- Modify: `css/service.css` — composant hero de prestation responsive et compatible avec les deux thèmes.
- Modify: `assets/og-image.jpg` — composition sociale réelle au format 1200 × 630.
- Modify: `sw.js` — invalidation du cache après changement des images et du shell.

Les pages et fichiers retirés du parcours public (`blog.html`, `articles/`, `services/lissage-ybera.html`) ne sont pas modifiés.

### Task 1: Baseline and image manifest

**Files:**
- Create: `scripts/photo-manifest.json`
- Test: `scripts/photo-manifest.json`

- [ ] **Step 1: Record the current working tree without altering user changes**

Run:

```powershell
git status --short
git diff -- index.html css/style.css css/service.css services
```

Expected: existing user changes are visible and remain unstaged; the implementation must edit around them rather than overwrite them.

- [ ] **Step 2: Create the exact processing manifest**

Create `scripts/photo-manifest.json` with:

```json
{
  "hero-salon": {
    "input": "photosalon/retouched/hero-salon.png",
    "variants": {
      "desktop": { "width": 960, "height": 1200, "focalX": 0.48, "focalY": 0.52 },
      "mobile": { "width": 1200, "height": 750, "focalX": 0.48, "focalY": 0.48 }
    }
  },
  "salon-lounge": {
    "input": "photosalon/retouched/salon-lounge.png",
    "variants": {
      "desktop": { "width": 800, "height": 1200, "focalX": 0.50, "focalY": 0.48 },
      "mobile": { "width": 720, "height": 960, "focalX": 0.50, "focalY": 0.50 }
    }
  },
  "salon-barbier": {
    "input": "photosalon/retouched/salon-barbier.png",
    "variants": {
      "desktop": { "width": 800, "height": 800, "focalX": 0.52, "focalY": 0.50 },
      "mobile": { "width": 720, "height": 720, "focalX": 0.52, "focalY": 0.50 }
    }
  },
  "salon-headspa": {
    "input": "photosalon/retouched/salon-headspa.png",
    "variants": {
      "desktop": { "width": 800, "height": 800, "focalX": 0.50, "focalY": 0.50 },
      "mobile": { "width": 720, "height": 720, "focalX": 0.50, "focalY": 0.50 }
    }
  },
  "cabine-headspa": {
    "input": "photosalon/retouched/cabine-headspa.png",
    "variants": {
      "desktop": { "width": 1440, "height": 960, "focalX": 0.52, "focalY": 0.50 },
      "mobile": { "width": 900, "height": 1125, "focalX": 0.58, "focalY": 0.50 }
    }
  },
  "service-balayage": { "input": "photosalon/retouched/service-balayage.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.58, "focalY": 0.46 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.60, "focalY": 0.44 } } },
  "service-barberie": { "input": "photosalon/retouched/service-barberie.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.52, "focalY": 0.44 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.52, "focalY": 0.42 } } },
  "service-coiffure-mariee": { "input": "photosalon/retouched/service-coiffure-mariee.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.52, "focalY": 0.43 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.52, "focalY": 0.40 } } },
  "service-coloration": { "input": "photosalon/retouched/service-coloration.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.50, "focalY": 0.44 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.50, "focalY": 0.42 } } },
  "service-coupes-femme": { "input": "photosalon/retouched/service-coupes-femme.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.50, "focalY": 0.42 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.50, "focalY": 0.40 } } },
  "service-coupes-homme": { "input": "photosalon/retouched/service-coupes-homme.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.50, "focalY": 0.42 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.50, "focalY": 0.40 } } },
  "service-extensions-great-lengths": { "input": "photosalon/retouched/service-extensions-great-lengths.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.52, "focalY": 0.45 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.52, "focalY": 0.42 } } },
  "service-head-spa": { "input": "photosalon/retouched/service-head-spa.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.55, "focalY": 0.50 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.58, "focalY": 0.50 } } },
  "service-patine-gloss": { "input": "photosalon/retouched/service-patine-gloss.png", "variants": { "desktop": { "width": 1920, "height": 1080, "focalX": 0.50, "focalY": 0.44 }, "mobile": { "width": 1080, "height": 1350, "focalX": 0.50, "focalY": 0.42 } } }
}
```

- [ ] **Step 3: Validate the manifest syntax**

Run:

```powershell
Get-Content -Raw scripts/photo-manifest.json | ConvertFrom-Json | Out-Null
```

Expected: exit code 0 and no output.

- [ ] **Step 4: Commit the manifest**

```powershell
git add scripts/photo-manifest.json
git commit -m "chore: define responsive photo variants"
```

### Task 2: Retouch the salon collection

**Files:**
- Create: `photosalon/retouched/hero-salon.png`
- Create: `photosalon/retouched/salon-lounge.png`
- Create: `photosalon/retouched/salon-barbier.png`
- Create: `photosalon/retouched/salon-headspa.png`
- Create: `photosalon/retouched/cabine-headspa.png`

- [ ] **Step 1: Load each local source into the conversation**

Use the image viewer on these edit targets before each edit:

```text
photosalon/hero-salon.jpg
photosalon/salon-lounge.jpg
photosalon/salon-barbier.jpg
photosalon/salon-headspa.jpg
photosalon/cabine-headspa.jpg
```

Expected: each image is visibly inspected at high detail before editing.

- [ ] **Step 2: Edit the five salon images with the built-in image tool**

Issue one built-in edit call per source with this prompt, replacing only the bracketed filename in `Input images`:

```text
Use case: precise-object-edit
Asset type: premium responsive website photography
Primary request: improve technical image quality, reduce visible luminance and chroma noise, recover natural micro-contrast, and upscale gently while preserving the exact photographed salon.
Input images: Image 1: the single salon edit target loaded immediately before this call
Style/medium: high-end natural interior photography with warm organic editorial finishing
Lighting/mood: warm neutral whites, soft cream, true sage and wood tones, controlled highlights, open shadows
Constraints: preserve the exact room geometry, furniture, olive tree, products, mirrors, fixtures, logos and all real details; preserve the original viewpoint and composition; remove only sensor noise and tiny non-characteristic distractions; no invented detail; no object replacement; no text alteration; no watermark
Avoid: HDR look, orange cast, crushed blacks, plastic smoothing, oversharpening halos, warped straight lines, altered branding, generated objects
```

Expected: five high-fidelity outputs with no structural drift.

- [ ] **Step 3: Save outputs non-destructively**

Copy the selected built-in outputs from their generated-image locations to the five exact `photosalon/retouched/*.png` paths listed above. Do not overwrite any file in `photosalon/` root.

- [ ] **Step 4: Validate invariants side by side**

Inspect original and retouched versions at original detail. If any geometry, product label, mirror reflection, furniture edge or light fixture changes, name that exact element in a single corrective edit and require it to remain unchanged; change only noise, tonal balance and technical clarity.

- [ ] **Step 5: Commit the salon masters**

```powershell
git add photosalon/retouched/hero-salon.png photosalon/retouched/salon-lounge.png photosalon/retouched/salon-barbier.png photosalon/retouched/salon-headspa.png photosalon/retouched/cabine-headspa.png
git commit -m "feat: retouch premium salon photography"
```

### Task 3: Retouch the cinematic service collection

**Files:**
- Create: `photosalon/retouched/service-balayage.png`
- Create: `photosalon/retouched/service-barberie.png`
- Create: `photosalon/retouched/service-coiffure-mariee.png`
- Create: `photosalon/retouched/service-coloration.png`
- Create: `photosalon/retouched/service-coupes-femme.png`
- Create: `photosalon/retouched/service-coupes-homme.png`
- Create: `photosalon/retouched/service-extensions-great-lengths.png`
- Create: `photosalon/retouched/service-head-spa.png`
- Create: `photosalon/retouched/service-patine-gloss.png`

- [ ] **Step 1: Load each local service source into the conversation**

Use the image viewer at high detail on each matching JPG in `photosalon/` before its edit.

- [ ] **Step 2: Edit each service image separately**

Issue one built-in edit call per source with this prompt:

```text
Use case: precise-object-edit
Asset type: cinematic service-page hero for a premium French hair salon
Primary request: reduce visible noise, improve resolution and technical clarity, then apply a restrained cinematic finish with deeper open shadows, controlled highlights, refined local contrast in hair and materials, and contained color.
Input images: Image 1: the single service-photo edit target loaded immediately before this call
Style/medium: authentic high-end editorial hair photography, not synthetic campaign art
Composition/framing: preserve the photographed subject, pose, camera angle and scene; retain usable crop area for both 16:9 desktop and 4:5 mobile
Lighting/mood: elegant and immersive, slightly dramatic, natural skin and accurate hair color
Constraints: preserve identity, face, body, hands, hairstyle, hair length, strand direction, hair color, clothing, tools, background and salon details exactly; change only noise, tonal finishing and technical clarity; no text; no watermark
Avoid: beauty-filter skin, face changes, extra hair, invented strands, reshaped body, altered hands, fake bokeh, crushed blacks, color shifts, halos, excessive vignette
```

Expected: nine outputs that remain faithful when toggled against the sources.

- [ ] **Step 3: Save and inspect every output**

Save to the exact `photosalon/retouched/service-*.png` paths. At 100 %, inspect face, skin, hairline, individual locks, hands, jewelry, clothing edges and background. Reject any output that invents or removes these details.

- [ ] **Step 4: Commit the service masters**

```powershell
git add photosalon/retouched/service-*.png
git commit -m "feat: create cinematic service photography"
```

### Task 4: Build deterministic responsive derivatives

**Files:**
- Create: `scripts/build-photo-derivatives.py`
- Create: `photosalon/web/*`
- Test: `scripts/build-photo-derivatives.py`

- [ ] **Step 1: Write the derivative builder**

Create `scripts/build-photo-derivatives.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "photo-manifest.json"
OUTPUT_DIR = ROOT / "photosalon" / "web"


def focal_crop(image: Image.Image, width: int, height: int, focal_x: float, focal_y: float) -> Image.Image:
    target_ratio = width / height
    source_ratio = image.width / image.height
    if source_ratio > target_ratio:
        crop_width = round(image.height * target_ratio)
        left = round((image.width - crop_width) * focal_x)
        left = max(0, min(left, image.width - crop_width))
        box = (left, 0, left + crop_width, image.height)
    else:
        crop_height = round(image.width / target_ratio)
        top = round((image.height - crop_height) * focal_y)
        top = max(0, min(top, image.height - crop_height))
        box = (0, top, image.width, top + crop_height)
    cropped = image.crop(box)
    return cropped.resize((width, height), Image.Resampling.LANCZOS)


def build() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for slug, config in manifest.items():
        source_path = ROOT / config["input"]
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        with Image.open(source_path) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            for variant, spec in config["variants"].items():
                output = focal_crop(
                    source,
                    spec["width"],
                    spec["height"],
                    spec["focalX"],
                    spec["focalY"],
                )
                base = OUTPUT_DIR / f"{slug}-{variant}"
                output.save(base.with_suffix(".webp"), "WEBP", quality=84, method=6)
                output.save(base.with_suffix(".jpg"), "JPEG", quality=88, optimize=True, progressive=True)


if __name__ == "__main__":
    build()
```

- [ ] **Step 2: Run the builder**

Run:

```powershell
$photoPython = 'C:\Users\ozone\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $photoPython scripts/build-photo-derivatives.py
```

Expected: 56 files under `photosalon/web/` — 14 image roles × 2 responsive variants × 2 formats.

- [ ] **Step 3: Check dimensions and visual crop quality**

Run:

```powershell
$photoPython = 'C:\Users\ozone\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $photoPython -c "from PIL import Image; from pathlib import Path; files=list(Path('photosalon/web').glob('*')); assert len(files)==56; [Image.open(p).verify() for p in files]; print('56 derivatives valid')"
```

Expected: `56 derivatives valid`.

Inspect all desktop/mobile pairs. Adjust only the relevant `focalX` or `focalY` in the manifest and rebuild if a face, hairstyle, chair, olive tree or key architectural line is poorly framed.

- [ ] **Step 4: Commit the builder and outputs**

```powershell
git add scripts/build-photo-derivatives.py photosalon/web
git commit -m "feat: build responsive photo derivatives"
```

### Task 5: Integrate the home-page collection

**Files:**
- Modify: `index.html`
- Modify: `css/style.css`

- [ ] **Step 1: Replace the hero image with responsive sources**

In `index.html`, replace the image inside `.hero-image` with:

```html
<picture>
  <source media="(max-width: 900px)" type="image/webp" srcset="photosalon/web/hero-salon-mobile.webp">
  <source media="(max-width: 900px)" srcset="photosalon/web/hero-salon-mobile.jpg">
  <source type="image/webp" srcset="photosalon/web/hero-salon-desktop.webp">
  <img src="photosalon/web/hero-salon-desktop.jpg" width="960" height="1200" alt="L'olivier au cœur du salon Prestige Coiffure à Chalon-sur-Saône" fetchpriority="high">
</picture>
```

- [ ] **Step 2: Replace the three salon images**

Use this exact structure for each `.salon-img`, changing the slug, dimensions and existing alt text:

```html
<picture>
  <source media="(max-width: 860px)" type="image/webp" srcset="photosalon/web/salon-lounge-mobile.webp">
  <source media="(max-width: 860px)" srcset="photosalon/web/salon-lounge-mobile.jpg">
  <source type="image/webp" srcset="photosalon/web/salon-lounge-desktop.webp">
  <img src="photosalon/web/salon-lounge-desktop.jpg" width="800" height="1200" alt="L'espace lounge du salon Prestige Coiffure" loading="lazy" decoding="async">
</picture>
```

For `salon-barbier` and `salon-headspa`, use `width="800" height="800"` and preserve their existing alt texts.

- [ ] **Step 3: Replace the cabin image**

Use:

```html
<picture>
  <source media="(max-width: 720px)" type="image/webp" srcset="photosalon/web/cabine-headspa-mobile.webp">
  <source media="(max-width: 720px)" srcset="photosalon/web/cabine-headspa-mobile.jpg">
  <source type="image/webp" srcset="photosalon/web/cabine-headspa-desktop.webp">
  <img src="photosalon/web/cabine-headspa-desktop.jpg" width="1440" height="960" alt="La cabine privée de soin head spa du salon Prestige Coiffure" loading="lazy" decoding="async">
</picture>
```

- [ ] **Step 4: Add shared picture and theme-aware image styling**

Add to the existing image component sections in `css/style.css`:

```css
.hero-image picture,
.salon-img picture,
.feature-cabine-img picture {
  display: block;
  width: 100%;
  height: 100%;
}

.hero-image picture > img,
.salon-img picture > img,
.feature-cabine-img picture > img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero-image {
  box-shadow: 0 28px 70px rgba(20, 17, 12, 0.16);
}

:root[data-theme="dark"] .hero-image {
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.38);
}

:root[data-theme="dark"] .hero-image::after {
  background: linear-gradient(180deg, rgba(13, 11, 8, 0.02) 34%, rgba(13, 11, 8, 0.42));
}

@media (max-width: 900px) {
  .hero-image {
    width: 100%;
    max-height: none;
    aspect-ratio: 8 / 5;
  }
}
```

Do not add filters to the photographs.

- [ ] **Step 5: Validate and commit the home integration**

Run:

```powershell
rg -n "photosalon/(hero-salon|salon-lounge|salon-barbier|salon-headspa|cabine-headspa)\.jpg" index.html
git diff --check -- index.html css/style.css
```

Expected: the first command returns no old root-image references; `git diff --check` passes.

```powershell
git add index.html css/style.css
git commit -m "feat: integrate responsive salon photography"
```

### Task 6: Integrate cinematic service heroes

**Files:**
- Modify: the ten active files listed in the file map
- Modify: `css/service.css`

- [ ] **Step 1: Replace each local service hero with `<picture>`**

Replace each existing service figure with its exact block below.

`services/balayage.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-balayage-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-balayage-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-balayage-desktop.webp">
    <img src="../photosalon/web/service-balayage-desktop.jpg" width="1920" height="1080" alt="Balayage réalisé chez Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/barberie.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-barberie-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-barberie-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-barberie-desktop.webp">
    <img src="../photosalon/web/service-barberie-desktop.jpg" width="1920" height="1080" alt="Taille de barbe réalisée chez Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/coiffure-mariee.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-coiffure-mariee-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-coiffure-mariee-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-coiffure-mariee-desktop.webp">
    <img src="../photosalon/web/service-coiffure-mariee-desktop.jpg" width="1920" height="1080" alt="Coiffure de mariée réalisée chez Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/coloration.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-coloration-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-coloration-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-coloration-desktop.webp">
    <img src="../photosalon/web/service-coloration-desktop.jpg" width="1920" height="1080" alt="Coloration rousse réalisée au salon Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/coupes-femme.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-coupes-femme-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-coupes-femme-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-coupes-femme-desktop.webp">
    <img src="../photosalon/web/service-coupes-femme-desktop.jpg" width="1920" height="1080" alt="Coupe femme réalisée chez Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/coupes-homme.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-coupes-homme-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-coupes-homme-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-coupes-homme-desktop.webp">
    <img src="../photosalon/web/service-coupes-homme-desktop.jpg" width="1920" height="1080" alt="Coupe homme réalisée chez Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/extensions-great-lengths.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-extensions-great-lengths-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-extensions-great-lengths-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-extensions-great-lengths-desktop.webp">
    <img src="../photosalon/web/service-extensions-great-lengths-desktop.jpg" width="1920" height="1080" alt="Cheveux longs et extensions chez Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/head-spa.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-head-spa-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-head-spa-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-head-spa-desktop.webp">
    <img src="../photosalon/web/service-head-spa-desktop.jpg" width="1920" height="1080" alt="Cabine privée head spa du salon Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

`services/patine-gloss.html`:

```html
<figure class="service-hero-image service-hero-image--cinematic">
  <picture>
    <source media="(max-width: 720px)" type="image/webp" srcset="../photosalon/web/service-patine-gloss-mobile.webp">
    <source media="(max-width: 720px)" srcset="../photosalon/web/service-patine-gloss-mobile.jpg">
    <source type="image/webp" srcset="../photosalon/web/service-patine-gloss-desktop.webp">
    <img src="../photosalon/web/service-patine-gloss-desktop.jpg" width="1920" height="1080" alt="Patine et gloss réalisés chez Prestige Coiffure" loading="eager" fetchpriority="high">
  </picture>
</figure>
```

- [ ] **Step 2: Mark the child-service hero as temporary without changing its source**

In `services/coupes-enfant.html`, add only the cinematic modifier to the existing figure:

```html
<figure class="service-hero-image service-hero-image--cinematic service-hero-image--temporary">
```

Keep its existing external URL and its current truthful alt text.

- [ ] **Step 3: Implement the restrained cinematic frame**

Replace the current `.service-hero-image` image rules in `css/service.css` with:

```css
.service-hero-image {
  position: relative;
  width: 100%;
  height: clamp(360px, 48vw, 620px);
  overflow: hidden;
  margin: 0;
  padding: 0;
  background: var(--bg-dark);
}

.service-hero-image picture {
  display: block;
  width: 100%;
  height: 100%;
}

.service-hero-image img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.service-hero-image--cinematic::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(15, 15, 15, 0.02) 55%, rgba(15, 15, 15, 0.18));
}

:root[data-theme="dark"] .service-hero-image--cinematic::after {
  background: linear-gradient(180deg, rgba(13, 11, 8, 0.04) 42%, rgba(13, 11, 8, 0.34));
}

@media (max-width: 720px) {
  .service-hero-image {
    height: min(125vw, 620px);
  }
}
```

- [ ] **Step 4: Verify every active service reference**

Run:

```powershell
rg -L "service-hero-image--cinematic" services/balayage.html services/barberie.html services/coiffure-mariee.html services/coloration.html services/coupes-enfant.html services/coupes-femme.html services/coupes-homme.html services/extensions-great-lengths.html services/head-spa.html services/patine-gloss.html
rg -n "photosalon/service-.*\.jpg" services/balayage.html services/barberie.html services/coiffure-mariee.html services/coloration.html services/coupes-femme.html services/coupes-homme.html services/extensions-great-lengths.html services/head-spa.html services/patine-gloss.html
git diff --check -- css/service.css services
```

Expected: both `rg` commands return no output; diff check passes.

- [ ] **Step 5: Commit service integration**

```powershell
git add css/service.css services/balayage.html services/barberie.html services/coiffure-mariee.html services/coloration.html services/coupes-enfant.html services/coupes-femme.html services/coupes-homme.html services/extensions-great-lengths.html services/head-spa.html services/patine-gloss.html
git commit -m "feat: add cinematic responsive service heroes"
```

### Task 7: Create the real salon Open Graph image

**Files:**
- Create: `scripts/build-og-image.py`
- Modify: `assets/og-image.jpg`

- [ ] **Step 1: Write the deterministic social-image builder**

Create `scripts/build-og-image.py`:

```python
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "photosalon" / "retouched" / "hero-salon.png"
LOGO = ROOT / "assets" / "logo.png"
OUTPUT = ROOT / "assets" / "og-image.jpg"
SIZE = (1200, 630)


def build() -> None:
    with Image.open(SOURCE) as source:
        canvas = ImageOps.fit(
            ImageOps.exif_transpose(source).convert("RGB"),
            SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.50, 0.48),
        ).convert("RGBA")

    gradient = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    pixels = gradient.load()
    for x in range(SIZE[0]):
        progress = max(0.0, (x / SIZE[0] - 0.34) / 0.66)
        alpha = round(188 * progress)
        for y in range(SIZE[1]):
            pixels[x, y] = (17, 15, 12, alpha)
    canvas = Image.alpha_composite(canvas, gradient)

    with Image.open(LOGO) as source_logo:
        source_logo = source_logo.convert("RGBA")
        logo_width = 360
        logo_height = round(source_logo.height * logo_width / source_logo.width)
        source_logo = source_logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
        alpha = source_logo.getchannel("A")
        cream_logo = Image.new("RGBA", source_logo.size, (241, 235, 224, 255))
        cream_logo.putalpha(alpha)

    position = (SIZE[0] - logo_width - 72, (SIZE[1] - logo_height) // 2)
    canvas.alpha_composite(cream_logo, position)
    canvas.convert("RGB").save(OUTPUT, "JPEG", quality=90, optimize=True, progressive=True)


if __name__ == "__main__":
    build()
```

- [ ] **Step 2: Build the 1200 × 630 composition**

Run:

```powershell
$photoPython = 'C:\Users\ozone\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $photoPython scripts/build-og-image.py
```

Expected: the olive tree remains visible, the right side receives a restrained dark gradient, and the existing logo appears in cream without generated text.

- [ ] **Step 3: Validate the social asset**

Run:

```powershell
$photoPython = 'C:\Users\ozone\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $photoPython -c "from PIL import Image; im=Image.open('assets/og-image.jpg'); assert im.size==(1200,630); assert im.mode=='RGB'; print(im.size, im.mode)"
```

Expected: `(1200, 630) RGB`.

- [ ] **Step 4: Commit the social asset**

```powershell
git add scripts/build-og-image.py assets/og-image.jpg
git commit -m "feat: refresh salon social preview"
```

### Task 8: Add automated asset verification and refresh cache

**Files:**
- Create: `scripts/verify-photo-assets.py`
- Modify: `sw.js`

- [ ] **Step 1: Write the asset verifier**

Create `scripts/verify-photo-assets.py`:

```python
from __future__ import annotations

import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = [ROOT / "index.html", *sorted((ROOT / "services").glob("*.html"))]
LOCAL_IMAGE = re.compile(r'(?:src|srcset)="([^" ]+)')
errors: list[str] = []

for html_path in HTML_FILES:
    text = html_path.read_text(encoding="utf-8")
    for reference in LOCAL_IMAGE.findall(text):
        if reference.startswith(("http://", "https://", "data:")):
            continue
        resolved = (html_path.parent / reference).resolve()
        if not resolved.exists():
            errors.append(f"missing: {html_path.relative_to(ROOT)} -> {reference}")

web_files = sorted((ROOT / "photosalon" / "web").glob("*"))
if len(web_files) != 56:
    errors.append(f"expected 56 photo derivatives, found {len(web_files)}")

for image_path in web_files:
    try:
        with Image.open(image_path) as image:
            image.verify()
    except Exception as exc:
        errors.append(f"invalid image: {image_path.relative_to(ROOT)}: {exc}")
    if image_path.stat().st_size > 900_000:
        errors.append(f"oversized: {image_path.relative_to(ROOT)} exceeds 900 KB")

if errors:
    raise SystemExit("\n".join(errors))
print(f"photo assets valid: {len(web_files)} derivatives, {len(HTML_FILES)} HTML files")
```

- [ ] **Step 2: Run the verifier before cache changes**

Run:

```powershell
$photoPython = 'C:\Users\ozone\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $photoPython scripts/verify-photo-assets.py
```

Expected: `photo assets valid: 56 derivatives, 12 HTML files`.

- [ ] **Step 3: Bump the service-worker cache version**

In `sw.js`, change:

```js
const CACHE_VERSION = 'v1.2.0';
```

Keep runtime caching for the new image files; do not precache all 56 derivatives because that would make first installation unnecessarily heavy.

- [ ] **Step 4: Run static verification**

Run:

```powershell
git diff --check
rg -n "<img(?![^>]*(width=|height=))" index.html services --pcre2
rg -n "photosalon/web/" index.html services
```

Expected: diff check passes; the missing-dimension search is reviewed and returns no newly introduced image lacking explicit dimensions; local responsive references appear on the home page and nine local service pages.

- [ ] **Step 5: Commit verification and cache invalidation**

```powershell
git add scripts/verify-photo-assets.py sw.js
git commit -m "test: verify premium photo delivery"
```

### Task 9: Visual and performance acceptance

**Files:**
- Test: `index.html`
- Test: ten active service pages
- Test: `css/style.css`
- Test: `css/service.css`

- [ ] **Step 1: Start a local static server**

Run:

```powershell
$photoPython = 'C:\Users\ozone\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $photoPython -m http.server 4173
```

Expected: the site is available at `http://localhost:4173/`.

- [ ] **Step 2: Capture representative pages at exact viewport sizes**

Use browser automation to capture:

```text
index.html — 390×844 light
index.html — 390×844 dark
index.html — 1440×1000 light
index.html — 1440×1000 dark
services/balayage.html — 390×844 light and dark
services/head-spa.html — 390×844 light and dark
services/coupes-homme.html — 1440×1000 light and dark
```

Expected: no face, hairstyle, olive tree or main salon feature is accidentally cropped; overlays remain restrained; all text is readable.

- [ ] **Step 3: Inspect key crops at original detail**

Compare the displayed hero, salon triptych, cabin, balayage, head spa and men’s cut with their retouched masters. Reject any derivative showing halos, waxy skin, invented strands, warped lines or unreadable photographed labels.

- [ ] **Step 4: Verify responsive delivery in the browser**

At 390 px width, confirm the selected image request ends in `-mobile.webp` in a WebP-capable browser. At 1440 px, confirm it ends in `-desktop.webp`. Confirm lazy images below the fold are not requested before scrolling.

- [ ] **Step 5: Run the final checks**

Run:

```powershell
$photoPython = 'C:\Users\ozone\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $photoPython scripts/verify-photo-assets.py
git diff --check
git status --short
```

Expected: verifier passes, diff check passes, and `git status` contains only pre-existing user-owned changes outside the committed photo work.

- [ ] **Step 6: Commit any focal-point-only acceptance corrections**

If visual review required manifest focal adjustments, rebuild and commit only the manifest plus regenerated derivatives:

```powershell
git add scripts/photo-manifest.json photosalon/web
git commit -m "fix: refine responsive photo focal points"
```

If no focal correction was needed, skip this commit.
