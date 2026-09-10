# Intégration photographique premium — Prestige Coiffure

**Date :** 2026-09-10

**Statut :** validé pour planification

**Direction :** luxe organique chaleureux, enrichi de touches cinématographiques sur les prestations

## 1. Objectif

Transformer les images actuelles en une collection visuelle cohérente et haut de gamme, sans modifier l'architecture, l'ordre des sections ni l'identité éditoriale du site. Le rendu doit être convaincant sur ordinateur et téléphone, en mode clair comme en mode sombre, et préparer le remplacement progressif des images par les futurs originaux Canon.

Le dosage retenu est d'environ **80 % collection éditoriale cohérente / 20 % mise en scène cinématographique**.

## 2. Principes directeurs

- Conserver l'atmosphère chaleureuse du salon : crème, sauge, bois, lumière enveloppante et or discret.
- Traiter les lieux et les personnes de façon naturelle : fidélité des couleurs, des volumes, des visages, de la peau, des cheveux et du mobilier.
- Donner aux pages prestations une présence plus cinématographique : noirs plus profonds, relief maîtrisé, couleurs contenues, cadrages immersifs et vignettage très léger si utile.
- Ne pas inventer de réalisations, de personnes, de décors ou de détails techniques absents des photographies sources.
- Préserver tous les originaux. Les fichiers intégrés au site sont des dérivés versionnés et clairement nommés.

## 3. Périmètre

### Inclus

- Page d'accueil : hero, galerie du salon et bloc de la cabine head spa.
- Pages prestations actives utilisant les images locales de `photosalon/`.
- Page coupe enfant : maintien temporaire du visuel externe actuel, avec une intégration cohérente, jusqu'à l'arrivée d'une photo Canon appropriée.
- Image Open Graph principale, dérivée d'une photographie réelle du salon et de l'identité existante.
- Ajustements HTML et CSS strictement nécessaires aux cadrages responsives, aux thèmes, à l'accessibilité et aux performances.
- Préparation d'une convention simple permettant de substituer ultérieurement les photos Canon sans refaire les composants.

### Exclus

- Refonte des textes, de la navigation, de l'ordre des sections ou des fonctionnalités.
- Réactivation ou refonte du blog et de l'article actuellement retirés du parcours public.
- Réactivation de prestations retirées du parcours public.
- Création de faux portraits, de fausses coiffures ou de faux espaces par IA.

## 4. Carte d'utilisation des images

### Accueil

- `hero-salon` reste l'image signature grâce à l'olivier et à l'identité immédiatement reconnaissable du lieu.
- `salon-lounge`, `salon-barbier` et `salon-headspa` forment un triptyque cohérent, traité comme une visite courte du salon.
- `cabine-headspa` conserve son rôle immersif dans le bloc consacré à la cabine privée.
- Les cartes équipe restent typographiques jusqu'à la livraison de portraits Canon adaptés.

### Prestations

- Chaque page conserve son image métier locale lorsqu'elle existe.
- Les images prestations reçoivent un étalonnage plus éditorial que les images du salon, sans modifier les sujets.
- Chaque image possède un point focal explicite pour empêcher qu'un visage, une chevelure ou un geste important soit coupé sur mobile.
- Les visuels externes encore nécessaires restent identifiés comme temporaires et ne deviennent pas la référence de la nouvelle direction artistique.

### Partage social

- L'image Open Graph doit utiliser une photographie réelle du salon, une composition lisible au format 1200 × 630 et le marquage Prestige existant.
- Elle doit rester lisible dans les aperçus réduits et ne pas dépendre du mode clair ou sombre du site.

## 5. Traitement photographique

### Base naturelle premium

- Correction mesurée de l'exposition, des hautes lumières et des ombres.
- Balance des blancs harmonisée autour de tons chauds neutres, sans jaunissement excessif.
- Correction des perspectives pour les photographies d'intérieur lorsqu'elle améliore la perception du lieu.
- Réduction du bruit de luminance et de chrominance en préservant les textures fines.
- Netteté de sortie adaptée à la taille d'affichage, sans halos ni sur-accentuation.
- Nettoyage limité aux petites distractions qui ne caractérisent pas le salon.

### Signature prestations

- Contraste local légèrement renforcé dans les cheveux et les matières.
- Ombres plus profondes mais non bouchées.
- Saturation contenue et carnations protégées.
- Vignettage ou assombrissement périphérique uniquement lorsqu'il guide utilement le regard.
- Aucun changement d'identité, de coiffure, de couleur de cheveux, de morphologie ou de décor.

### Débruitage et augmentation de résolution

- Évaluer chaque source à sa taille d'affichage réelle avant tout agrandissement.
- Agrandir uniquement les images qui manquent réellement de définition pour leur usage cible.
- Limiter l'agrandissement à un niveau visuellement crédible ; privilégier un cadrage moins agressif si l'upscale produit des détails artificiels.
- Comparer la version traitée à l'original à 100 % et à la taille réelle d'affichage.
- Rejeter toute variante qui lisse la peau, transforme les mèches, déforme les textes présents dans la scène ou invente des textures.

## 6. Système responsive

- Utiliser `<picture>` lorsque des cadrages réellement différents sont nécessaires entre desktop et mobile.
- Prévoir une variante paysage pour les grands écrans et une variante verticale ou recentrée pour les petits écrans.
- Définir `width` et `height` afin de réserver l'espace et limiter le décalage de mise en page.
- Utiliser `srcset` et `sizes` pour éviter de télécharger une image surdimensionnée sur téléphone.
- Conserver le chargement immédiat de l'image hero et le chargement différé des images sous la ligne de flottaison.
- Employer WebP comme format principal et JPEG comme solution de repli lorsque la compatibilité ou le partage l'exige.

## 7. Modes clair et sombre

- Ne pas appliquer de filtre CSS global aux photographies.
- Ajuster plutôt les overlays, bordures, légendes et ombres selon le thème.
- En mode clair, conserver des images ouvertes, chaleureuses et naturelles.
- En mode sombre, renforcer légèrement la séparation entre l'image et le fond sans écraser les noirs.
- Vérifier le contraste de tout texte superposé dans les deux thèmes.

## 8. Convention des dérivés

Les originaux existants restent inchangés. Les nouvelles versions utilisent des noms explicites :

- `<sujet>-desktop.webp`
- `<sujet>-mobile.webp`
- `<sujet>-desktop.jpg`
- `<sujet>-mobile.jpg`

Lors de l'arrivée des fichiers Canon, leurs masters seront conservés dans un dossier source distinct non utilisé directement par les pages. Les dérivés reprendront la même convention afin de permettre une substitution simple.

## 9. Accessibilité et contenu

- Conserver ou améliorer les textes alternatifs selon la fonction réelle de chaque image.
- Utiliser `alt=""` uniquement pour une image strictement décorative et redondante.
- Ne pas porter une information essentielle uniquement dans une photographie.
- Respecter les droits à l'image confirmés par le propriétaire du site pour les personnes reconnaissables.

## 10. Validation

- Inspection visuelle des images traitées face aux originaux.
- Contrôle des détails sensibles : visages, peau, cheveux, mains, miroirs, mobilier, logos et texte photographié.
- Vérification aux largeurs mobiles et desktop représentatives.
- Vérification complète en mode clair et sombre.
- Vérification des chemins, fallbacks, attributs `alt`, dimensions et absence de liens cassés.
- Contrôle du poids des fichiers et de la stabilité de mise en page.
- Comparaison avant/après du hero, du triptyque salon et d'au moins trois pages prestations représentatives.

## 11. Critères d'acceptation

- Le site conserve sa structure et reste immédiatement reconnaissable.
- Les photographies paraissent appartenir à une même collection de marque.
- Le salon reste chaleureux et authentique ; les prestations gagnent en présence éditoriale.
- Aucun sujet ni élément identitaire n'est altéré de manière trompeuse.
- Les cadrages restent pertinents sur téléphone et ordinateur.
- Les images fonctionnent dans les deux thèmes sans perte de lisibilité.
- Les dérivés sont plus propres et suffisamment définis pour leur usage, sans aspect artificiel.
- Les futurs fichiers Canon pourront remplacer les sources actuelles sans refonte du système d'intégration.
