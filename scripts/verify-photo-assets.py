#!/usr/bin/env python3
"""Verify committed premium photo delivery without modifying repository assets."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError


ROOT = Path(__file__).resolve().parent.parent
MAX_IMAGE_BYTES = 900_000
EXPECTED_ROLE_SLUGS = (
    "hero-salon",
    "salon-lounge",
    "salon-barbier",
    "salon-headspa",
    "cabine-headspa",
    "service-balayage",
    "service-barberie",
    "service-coiffure-mariee",
    "service-coloration",
    "service-coupes-femme",
    "service-coupes-homme",
    "service-extensions-great-lengths",
    "service-head-spa",
    "service-patine-gloss",
)
INDEX_ROLES = EXPECTED_ROLE_SLUGS[:5]
INDEX_MOBILE_MEDIA = {
    "hero-salon": "(max-width: 900px)",
    "salon-lounge": "(max-width: 860px)",
    "salon-barbier": "(max-width: 860px)",
    "salon-headspa": "(max-width: 860px)",
    "cabine-headspa": "(max-width: 720px)",
}
LOCAL_SERVICE_SLUGS = (
    "balayage",
    "barberie",
    "coiffure-mariee",
    "coloration",
    "coupes-femme",
    "coupes-homme",
    "extensions-great-lengths",
    "head-spa",
    "patine-gloss",
)
SERVICE_FILES = tuple(
    f"services/{slug}.html"
    for slug in (
        "balayage",
        "barberie",
        "coiffure-mariee",
        "coloration",
        "coupes-enfant",
        "coupes-femme",
        "coupes-homme",
        "extensions-great-lengths",
        "head-spa",
        "lissage-ybera",
        "patine-gloss",
    )
)
HTML_FILES = ("index.html", *SERVICE_FILES)
ACTIVE_HTML_FILES = (
    "index.html",
    *(f"services/{slug}.html" for slug in LOCAL_SERVICE_SLUGS[:4]),
    "services/coupes-enfant.html",
    *(f"services/{slug}.html" for slug in LOCAL_SERVICE_SLUGS[4:]),
)
REMOTE_SCHEMES = {"http", "https", "data"}


@dataclass
class Picture:
    sources: list[dict[str, str]] = field(default_factory=list)
    image: dict[str, str] | None = None
    images: list[dict[str, str]] = field(default_factory=list)
    parent_figure: Figure | None = None


@dataclass
class Figure:
    attributes: dict[str, str]
    images: list[dict[str, str]] = field(default_factory=list)
    pictures: list[Picture] = field(default_factory=list)


class PhotoHTMLParser(HTMLParser):
    """Collect URL references and the small amount of responsive structure used here."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.pictures: list[Picture] = []
        self.figures: list[Figure] = []
        self._picture_stack: list[Picture] = []
        self._figure_stack: list[Figure] = []

    @staticmethod
    def _attributes(attributes: list[tuple[str, str | None]]) -> dict[str, str]:
        return {name.lower(): value or "" for name, value in attributes}

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attrs = self._attributes(attributes)
        source = attrs.get("src")
        if source:
            self.references.append(source)
        if attrs.get("srcset"):
            self.references.extend(parse_srcset(attrs["srcset"]))

        if tag == "figure":
            figure = Figure(attributes=attrs)
            self.figures.append(figure)
            self._figure_stack.append(figure)
        elif tag == "picture":
            parent = self._figure_stack[-1] if self._figure_stack else None
            picture = Picture(parent_figure=parent)
            self.pictures.append(picture)
            self._picture_stack.append(picture)
            if parent is not None:
                parent.pictures.append(picture)
        elif tag == "source" and self._picture_stack:
            self._picture_stack[-1].sources.append(attrs)
        elif tag == "img":
            if self._picture_stack:
                picture = self._picture_stack[-1]
                picture.images.append(attrs)
                if picture.image is None:
                    picture.image = attrs
            if self._figure_stack:
                self._figure_stack[-1].images.append(attrs)

    def handle_startendtag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attributes)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "picture" and self._picture_stack:
            self._picture_stack.pop()
        elif tag == "figure" and self._figure_stack:
            self._figure_stack.pop()


def parse_srcset(value: str) -> list[str]:
    """Return URLs from a srcset while retaining commas inside data URLs."""
    urls: list[str] = []
    position = 0
    length = len(value)
    whitespace = " \t\r\n\f"
    while position < length:
        while position < length and value[position] in whitespace + ",":
            position += 1
        if position >= length:
            break
        start = position
        while position < length and value[position] not in whitespace:
            position += 1
        candidate = value[start:position]
        if candidate.endswith(","):
            candidate = candidate.rstrip(",")
            if candidate:
                urls.append(candidate)
            continue
        if candidate:
            urls.append(candidate)

        parentheses = 0
        while position < length:
            character = value[position]
            if character == "(":
                parentheses += 1
            elif character == ")" and parentheses:
                parentheses -= 1
            elif character == "," and not parentheses:
                position += 1
                break
            position += 1
    return urls


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()


def _error_detail(root: Path, error: BaseException) -> str:
    return _sanitize_subprocess_output(root, str(error))


def _local_path(root: Path, document: Path, reference: str) -> Path | None:
    try:
        parsed = urlsplit(reference.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() in REMOTE_SCHEMES or parsed.netloc:
        return None
    url_path = unquote(parsed.path)
    if not url_path:
        return None
    if url_path.startswith("/"):
        candidate = root / url_path.lstrip("/")
    else:
        candidate = document.parent / url_path
    return candidate.resolve(strict=False)


def _parse_html(root: Path, relative_path: str, errors: list[str]) -> PhotoHTMLParser | None:
    path = root / relative_path
    if not path.is_file():
        errors.append(f"{relative_path}: missing HTML file")
        return None
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"{relative_path}: cannot read HTML: {_error_detail(root, error)}")
        return None
    parser = PhotoHTMLParser()
    try:
        parser.feed(contents)
        parser.close()
    except (ValueError, AssertionError) as error:
        errors.append(f"{relative_path}: invalid HTML: {error}")
        return None
    return parser


def _check_html_scope(root: Path, errors: list[str]) -> dict[str, PhotoHTMLParser]:
    parsers: dict[str, PhotoHTMLParser] = {}
    services_directory = root / "services"
    try:
        actual_services = {
            path.relative_to(root).as_posix()
            for path in services_directory.glob("*.html")
            if path.is_file()
        }
    except OSError as error:
        errors.append(f"services: cannot enumerate HTML files: {_error_detail(root, error)}")
        actual_services = set()
    expected_services = set(SERVICE_FILES)
    for unexpected in sorted(actual_services - expected_services):
        errors.append(f"{unexpected}: unexpected service HTML file")

    for relative_path in HTML_FILES:
        parser = _parse_html(root, relative_path, errors)
        if parser is None:
            continue
        parsers[relative_path] = parser
        document = root / relative_path
        for reference in parser.references:
            local = _local_path(root, document, reference)
            if local is None:
                continue
            try:
                local.relative_to(root)
            except ValueError:
                errors.append(
                    f"{relative_path}: local reference escapes repository: {reference}"
                )
                continue
            if not local.is_file():
                errors.append(
                    f"{relative_path}: missing local reference {_relative(root, local)}"
                )
    return parsers


def _positive_dimension(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _load_manifest(root: Path, errors: list[str]) -> dict[str, dict[str, tuple[int, int]]]:
    manifest_path = root / "scripts" / "photo-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(
            "scripts/photo-manifest.json: cannot load manifest: "
            f"{_error_detail(root, error)}"
        )
        return {}
    if not isinstance(payload, dict):
        errors.append("scripts/photo-manifest.json: manifest must be an object")
        return {}
    actual_roles = set(payload)
    expected_roles = set(EXPECTED_ROLE_SLUGS)
    if actual_roles != expected_roles:
        missing = ", ".join(sorted(expected_roles - actual_roles)) or "none"
        extra = ", ".join(sorted(actual_roles - expected_roles)) or "none"
        errors.append(
            "scripts/photo-manifest.json: expected exactly 14 photo roles "
            f"(missing: {missing}; extra: {extra})"
        )

    roles: dict[str, dict[str, tuple[int, int]]] = {}
    for slug in EXPECTED_ROLE_SLUGS:
        role = payload.get(slug)
        if not isinstance(role, dict):
            if slug in payload:
                errors.append(f"scripts/photo-manifest.json: {slug} must be an object")
            continue
        variants = role.get("variants")
        if not isinstance(variants, dict) or set(variants) != {"desktop", "mobile"}:
            errors.append(
                f"scripts/photo-manifest.json: {slug} must define exactly desktop and mobile variants"
            )
            continue
        dimensions: dict[str, tuple[int, int]] = {}
        for variant_name in ("desktop", "mobile"):
            variant = variants.get(variant_name)
            if not isinstance(variant, dict):
                errors.append(
                    f"scripts/photo-manifest.json: {slug}.{variant_name} must be an object"
                )
                continue
            width = variant.get("width")
            height = variant.get("height")
            if not _positive_dimension(width) or not _positive_dimension(height):
                errors.append(
                    f"scripts/photo-manifest.json: {slug}.{variant_name} has invalid dimensions"
                )
                continue
            dimensions[variant_name] = (width, height)
        if set(dimensions) == {"desktop", "mobile"}:
            roles[slug] = dimensions
    return roles


def _expected_derivatives(
    roles: dict[str, dict[str, tuple[int, int]]]
) -> dict[str, tuple[str, tuple[int, int]]]:
    expected: dict[str, tuple[str, tuple[int, int]]] = {}
    for slug in EXPECTED_ROLE_SLUGS:
        if slug not in roles:
            continue
        for variant in ("desktop", "mobile"):
            for extension, image_format in (("jpg", "JPEG"), ("webp", "WEBP")):
                expected[f"{slug}-{variant}.{extension}"] = (
                    image_format,
                    roles[slug][variant],
                )
    return expected


def _check_image(
    root: Path,
    path: Path,
    expected_format: str,
    expected_dimensions: tuple[int, int],
    errors: list[str],
) -> None:
    label = _relative(root, path)
    if not path.is_file():
        errors.append(f"{label}: expected a file")
        return
    try:
        size = path.stat().st_size
    except OSError as error:
        errors.append(f"{label}: cannot stat image: {_error_detail(root, error)}")
        return
    if size > MAX_IMAGE_BYTES:
        errors.append(f"{label}: {size} bytes exceeds 900000 bytes")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            actual_format = image.format
            actual_dimensions = image.size
            actual_mode = image.mode
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        errors.append(f"{label}: invalid image: {_error_detail(root, error)}")
        return
    if actual_format != expected_format:
        errors.append(f"{label}: expected {expected_format}, got {actual_format!r}")
    if actual_dimensions != expected_dimensions:
        expected_width, expected_height = expected_dimensions
        errors.append(
            f"{label}: expected {expected_width}x{expected_height}, got "
            f"{actual_dimensions[0]}x{actual_dimensions[1]}"
        )
    if actual_mode != "RGB":
        errors.append(f"{label}: expected RGB, got {actual_mode!r}")


def _check_derivatives(
    root: Path,
    roles: dict[str, dict[str, tuple[int, int]]],
    errors: list[str],
) -> None:
    expected = _expected_derivatives(roles)
    if len(expected) != 56:
        return
    directory = root / "photosalon" / "web"
    if not directory.is_dir():
        errors.append("photosalon/web: missing derivative directory")
        return
    try:
        entries = {path.name: path for path in directory.iterdir()}
    except OSError as error:
        errors.append(
            "photosalon/web: cannot enumerate derivative directory: "
            f"{_error_detail(root, error)}"
        )
        return
    for name in sorted(set(expected) - set(entries)):
        errors.append(f"photosalon/web/{name}: missing derivative")
    for name in sorted(set(entries) - set(expected)):
        errors.append(f"photosalon/web/{name}: unexpected derivative entry")
    for name in sorted(set(expected) & set(entries)):
        image_format, dimensions = expected[name]
        _check_image(root, entries[name], image_format, dimensions, errors)


def _check_og_image(root: Path, errors: list[str]) -> None:
    path = root / "assets" / "og-image.jpg"
    label = "assets/og-image.jpg"
    if not path.is_file():
        errors.append(f"{label}: missing Open Graph image")
        return
    try:
        size = path.stat().st_size
    except OSError as error:
        errors.append(f"{label}: cannot stat image: {_error_detail(root, error)}")
        return
    if size > MAX_IMAGE_BYTES:
        errors.append(f"{label}: {size} bytes exceeds 900000 bytes")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            image_format = image.format
            dimensions = image.size
            mode = image.mode
            has_exif = bool(image.getexif()) or bool(image.info.get("exif"))
            has_icc = bool(image.info.get("icc_profile"))
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        errors.append(f"{label}: invalid image: {_error_detail(root, error)}")
        return
    if image_format != "JPEG" or dimensions != (1200, 630) or mode != "RGB":
        errors.append(
            f"{label}: expected 1200x630 RGB JPEG, got "
            f"{dimensions[0]}x{dimensions[1]} {mode} {image_format}"
        )
    if has_exif:
        errors.append(f"{label}: unexpected EXIF metadata")
    if has_icc:
        errors.append(f"{label}: unexpected ICC profile")


def _normalized_references(
    root: Path, relative_path: str, references: list[str]
) -> list[str]:
    document = root / relative_path
    result: list[str] = []
    for reference in references:
        local = _local_path(root, document, reference)
        if local is None:
            continue
        try:
            result.append(local.relative_to(root).as_posix())
        except ValueError:
            continue
    return result


def _expected_role_paths(slug: str) -> list[str]:
    return [
        f"photosalon/web/{slug}-mobile.webp",
        f"photosalon/web/{slug}-mobile.jpg",
        f"photosalon/web/{slug}-desktop.webp",
        f"photosalon/web/{slug}-desktop.jpg",
    ]


def _picture_paths(root: Path, relative_path: str, picture: Picture) -> list[str]:
    references: list[str] = []
    for source in picture.sources:
        references.extend(parse_srcset(source.get("srcset", "")))
    if picture.image and picture.image.get("src"):
        references.append(picture.image["src"])
    return _normalized_references(root, relative_path, references)


def _check_picture(
    root: Path,
    relative_path: str,
    parser: PhotoHTMLParser,
    slug: str,
    dimensions: tuple[int, int],
    errors: list[str],
    *,
    below_fold: bool,
    mobile_media: str,
    mobile_jpeg_type: str | None,
) -> Picture | None:
    expected_paths = _expected_role_paths(slug)
    candidates = [
        picture
        for picture in parser.pictures
        if set(_picture_paths(root, relative_path, picture)) & set(expected_paths)
    ]
    if len(candidates) != 1:
        errors.append(
            f"{relative_path}: {slug} must have exactly one premium picture"
        )
        return None
    picture = candidates[0]
    actual_paths = _picture_paths(root, relative_path, picture)
    if actual_paths != expected_paths:
        errors.append(
            f"{relative_path}: {slug} picture mapping must be mobile WebP/JPEG then desktop WebP/JPEG"
        )
    if len(picture.sources) != 3:
        errors.append(f"{relative_path}: {slug} picture must contain three sources")
    else:
        first, second, third = picture.sources
        if first.get("media") != mobile_media or second.get("media") != mobile_media:
            errors.append(
                f"{relative_path}: {slug} mobile source media must be exactly {mobile_media}"
            )
        if first.get("type") != "image/webp":
            errors.append(
                f"{relative_path}: {slug} mobile WebP source type must be image/webp"
            )
        if mobile_jpeg_type is None:
            if "type" in second:
                errors.append(
                    f"{relative_path}: {slug} mobile JPEG source must not declare type"
                )
        elif second.get("type") != mobile_jpeg_type:
            errors.append(
                f"{relative_path}: {slug} mobile JPEG source type must be {mobile_jpeg_type}"
            )
        if third.get("type") != "image/webp":
            errors.append(
                f"{relative_path}: {slug} desktop WebP source type must be image/webp"
            )
        if "media" in third:
            errors.append(
                f"{relative_path}: {slug} desktop WebP source must not declare media"
            )
    image = picture.image
    if image is None:
        errors.append(f"{relative_path}: {slug} picture is missing its img fallback")
        return picture
    if picture.images != [image]:
        errors.append(
            f"{relative_path}: {slug} picture must contain exactly one img fallback"
        )
    expected_width, expected_height = dimensions
    if image.get("width") != str(expected_width):
        errors.append(
            f"{relative_path}: {slug} img width must be {expected_width}"
        )
    if image.get("height") != str(expected_height):
        errors.append(
            f"{relative_path}: {slug} img height must be {expected_height}"
        )
    if not image.get("alt", "").strip():
        errors.append(f"{relative_path}: {slug} img alt must be nonempty")
    if below_fold:
        if image.get("loading", "").lower() != "lazy":
            errors.append(f"{relative_path}: {slug} below-fold img must be lazy")
        if image.get("decoding", "").lower() != "async":
            errors.append(f"{relative_path}: {slug} below-fold img decoding must be async")
    else:
        if image.get("fetchpriority", "").lower() != "high":
            if relative_path.startswith("services/"):
                errors.append(f"{relative_path}: premium hero fetchpriority must be high")
            else:
                errors.append(f"{relative_path}: {slug} hero fetchpriority must be high")
        if relative_path.startswith("services/") and image.get("loading", "").lower() != "eager":
            errors.append(f"{relative_path}: premium hero loading must be eager")
        if image.get("loading", "").lower() == "lazy":
            errors.append(f"{relative_path}: {slug} hero must not be lazy")
    return picture


def _check_premium_html(
    root: Path,
    parsers: dict[str, PhotoHTMLParser],
    roles: dict[str, dict[str, tuple[int, int]]],
    errors: list[str],
) -> None:
    index = parsers.get("index.html")
    if index is not None:
        if len(index.pictures) != 5:
            errors.append(
                f"index.html: expected exactly 5 picture elements, got {len(index.pictures)}"
            )
        references = _normalized_references(root, "index.html", index.references)
        premium = [path for path in references if path.startswith("photosalon/web/")]
        expected = [path for slug in INDEX_ROLES for path in _expected_role_paths(slug)]
        if Counter(premium) != Counter(expected):
            errors.append(
                "index.html: premium photo references must be exactly the 20 expected responsive paths"
            )
        if any(
            path.startswith("photosalon/") and not path.startswith("photosalon/web/")
            for path in references
        ):
            errors.append("index.html: legacy root photo references must not be used")
        for position, slug in enumerate(INDEX_ROLES):
            if slug in roles:
                _check_picture(
                    root,
                    "index.html",
                    index,
                    slug,
                    roles[slug]["desktop"],
                    errors,
                    below_fold=position > 0,
                    mobile_media=INDEX_MOBILE_MEDIA[slug],
                    mobile_jpeg_type=None,
                )

    for service_slug in LOCAL_SERVICE_SLUGS:
        relative_path = f"services/{service_slug}.html"
        parser = parsers.get(relative_path)
        role_slug = f"service-{service_slug}"
        if parser is None or role_slug not in roles:
            continue
        references = _normalized_references(root, relative_path, parser.references)
        premium = [path for path in references if path.startswith("photosalon/web/")]
        expected = _expected_role_paths(role_slug)
        if Counter(premium) != Counter(expected):
            errors.append(
                f"{relative_path}: premium photo references must be exactly the four expected responsive paths"
            )
        hero_figures = [
            figure
            for figure in parser.figures
            if "service-hero-image" in figure.attributes.get("class", "").split()
        ]
        if len(hero_figures) != 1:
            errors.append(
                f"{relative_path}: expected exactly one service hero figure, got {len(hero_figures)}"
            )
        hero = hero_figures[0] if len(hero_figures) == 1 else None
        if hero is not None and "service-hero-image--cinematic" not in hero.attributes.get(
            "class", ""
        ).split():
            errors.append(
                f"{relative_path}: service hero figure must be cinematic"
            )
        picture = _check_picture(
            root,
            relative_path,
            parser,
            role_slug,
            roles[role_slug]["desktop"],
            errors,
            below_fold=False,
            mobile_media="(max-width: 720px)",
            mobile_jpeg_type="image/jpeg",
        )
        if hero is not None and picture is not None:
            if picture.parent_figure is not hero or hero.pictures != [picture]:
                errors.append(
                    f"{relative_path}: premium picture must be inside the unique hero figure"
                )
            if hero.images != [picture.image]:
                errors.append(
                    f"{relative_path}: hero figure must contain exactly the premium fallback img"
                )

    child_path = "services/coupes-enfant.html"
    child = parsers.get(child_path)
    if child is not None:
        references = _normalized_references(root, child_path, child.references)
        hero_figures = [
            figure
            for figure in child.figures
            if "service-hero-image" in figure.attributes.get("class", "").split()
        ]
        if len(hero_figures) != 1:
            errors.append(
                f"{child_path}: expected exactly one service hero figure, got {len(hero_figures)}"
            )
            return
        hero = hero_figures[0]
        classes = set(hero.attributes.get("class", "").split())
        if "service-hero-image--temporary" not in classes:
            errors.append(
                f"{child_path}: hero must retain class service-hero-image--temporary"
            )
        if "service-hero-image--cinematic" not in classes:
            errors.append(
                f"{child_path}: hero must retain class service-hero-image--cinematic"
            )
        invalid_temporary_hero = False
        if hero.pictures:
            errors.append(f"{child_path}: temporary hero must not contain a picture")
            invalid_temporary_hero = True
        if len(hero.images) != 1:
            errors.append(f"{child_path}: temporary hero must contain exactly one img")
            invalid_temporary_hero = True
        elif urlsplit(hero.images[0].get("src", "")).scheme.lower() not in {
            "http",
            "https",
        }:
            errors.append(f"{child_path}: temporary hero img must be external")
            invalid_temporary_hero = True
        if any(path.startswith("photosalon/web/") for path in references):
            invalid_temporary_hero = True
        if invalid_temporary_hero:
            errors.append(f"{child_path}: must remain external and temporary")


def _sanitize_subprocess_output(root: Path, output: str) -> str:
    sanitized = output.strip()
    root_text = str(root)
    escaped_root = root_text.replace("\\", "\\\\")
    for root_variant, separator in (
        (escaped_root, "\\\\"),
        (root_text, "\\"),
        (root_text, "/"),
    ):
        sanitized = sanitized.replace(root_variant + separator, "")
        sanitized = sanitized.replace(root_variant, ".")
    return sanitized.replace("\\\\", "/").replace("\\", "/")


def _check_builder(root: Path, errors: list[str]) -> None:
    script = root / "scripts" / "build-photo-derivatives.py"
    if not script.is_file():
        errors.append("scripts/build-photo-derivatives.py: missing builder")
        return
    try:
        completed = subprocess.run(
            [sys.executable, str(script), "--verify"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as error:
        errors.append(
            "build-photo-derivatives.py --verify: cannot run: "
            f"{_error_detail(root, error)}"
        )
        return
    if completed.returncode:
        details = completed.stderr.strip() or completed.stdout.strip()
        details = _sanitize_subprocess_output(root, details)
        errors.append(
            "build-photo-derivatives.py --verify failed"
            + (f": {details}" if details else f" with exit {completed.returncode}")
        )


def _check_service_worker(root: Path, errors: list[str]) -> None:
    path = root / "sw.js"
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"sw.js: cannot read service worker: {_error_detail(root, error)}")
        return
    versions = re.findall(
        r"^const\s+CACHE_VERSION\s*=\s*['\"]([^'\"]+)['\"]\s*;\s*$",
        contents,
        flags=re.MULTILINE,
    )
    if versions != ["v1.2.0"]:
        errors.append("sw.js: CACHE_VERSION must be exactly v1.2.0")
    precache = re.search(
        r"const\s+PRECACHE_URLS\s*=\s*\[(.*?)\]\s*;",
        contents,
        flags=re.DOTALL,
    )
    if precache and "photosalon/web/" in precache.group(1):
        errors.append("sw.js: responsive derivatives must not be precached")


def audit_repository(root: Path) -> list[str]:
    """Return every detected contract violation using repository-relative paths."""
    root = Path(root).resolve()
    if not root.is_dir():
        return ["repository root: directory does not exist"]
    errors: list[str] = []
    roles = _load_manifest(root, errors)
    _check_derivatives(root, roles, errors)
    parsers = _check_html_scope(root, errors)
    _check_premium_html(root, parsers, roles, errors)
    _check_og_image(root, errors)
    _check_builder(root, errors)
    _check_service_worker(root, errors)
    return errors


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root (default: directory above this script)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    errors = audit_repository(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: 56 derivatives, 12 HTML files, 11 active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
