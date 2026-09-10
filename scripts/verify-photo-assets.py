#!/usr/bin/env python3
"""Verify committed premium photo delivery without modifying repository assets."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from PIL import Image, UnidentifiedImageError

try:
    import html5lib
    from html5lib import _tokenizer as html5_tokenizer
except ModuleNotFoundError:
    html5lib = None
    html5_tokenizer = None


ROOT = Path(__file__).resolve().parent.parent
MAX_IMAGE_BYTES = 900_000
MAX_DECODE_PIXELS = 40_000_000
MAX_IMAGE_DIMENSION = 10_000
MAX_MASTER_BYTES = 25_000_000
MAX_MASTER_PIXELS = 40_000_000
MAX_MASTER_DIMENSION = 10_000
MAX_VARIANT_PIXELS = 16_000_000
MAX_VARIANT_DIMENSION = 4_096
WORKER_TIMEOUT_SECONDS = 120
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
HTML_NAMESPACE = "http://www.w3.org/1999/xhtml"


class LocalPathError(ValueError):
    """A local URL path is unsafe or differs from the on-disk spelling."""


@dataclass
class Picture:
    sources: list[dict[str, str]] = field(default_factory=list)
    image: dict[str, str] | None = None
    images: list[dict[str, str]] = field(default_factory=list)
    parent_figure: Figure | None = None
    inert_ancestor: str | None = None


@dataclass
class Figure:
    attributes: dict[str, str]
    images: list[dict[str, str]] = field(default_factory=list)
    pictures: list[Picture] = field(default_factory=list)
    inert_ancestor: str | None = None


@dataclass(frozen=True)
class SrcsetCandidate:
    url: str
    descriptor: str


@dataclass
class ParsedHTML:
    references: list[str] = field(default_factory=list)
    pictures: list[Picture] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)


if html5lib is not None and html5_tokenizer is not None:

    class _DiagnosticTokenizer(html5_tokenizer.HTMLTokenizer):
        """Attach the discarded duplicate attribute name to html5lib errors."""

        def attributeNameState(self):
            token = self.currentToken
            raw_attributes = token.get("data")
            attribute_name = (
                raw_attributes[-1][0].lower()
                if isinstance(raw_attributes, list) and raw_attributes
                else ""
            )
            queue_size = len(self.tokenQueue)
            result = super().attributeNameState()
            for queued in list(self.tokenQueue)[queue_size:]:
                if queued.get("data") == "duplicate-attribute":
                    queued["datavars"] = {
                        "name": attribute_name,
                        "tag": token.get("name", "unknown"),
                    }
            return result


    class _DiagnosticHTMLParser(html5lib.HTMLParser):
        """Use html5lib's parser with duplicate-aware diagnostics."""

        def _parse(
            self,
            stream,
            innerHTML=False,
            container="div",
            scripting=False,
            **kwargs,
        ):
            self.innerHTMLMode = innerHTML
            self.container = container
            self.scripting = scripting
            self.tokenizer = _DiagnosticTokenizer(stream, parser=self, **kwargs)
            self.reset()
            try:
                self.mainLoop()
            except html5_tokenizer._ReparseException:
                self.reset()
                self.mainLoop()


else:
    _DiagnosticHTMLParser = None


def parse_srcset_candidates(value: str) -> list[SrcsetCandidate]:
    """Return srcset URLs and their unmodified descriptor text."""
    candidates: list[SrcsetCandidate] = []
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
                candidates.append(SrcsetCandidate(candidate, ""))
            continue

        descriptor_start = position
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
        if candidate:
            descriptor_end = position - 1 if position and value[position - 1] == "," else position
            candidates.append(
                SrcsetCandidate(candidate, value[descriptor_start:descriptor_end].strip())
            )
    return candidates


def parse_srcset(value: str) -> list[str]:
    """Return URLs from a srcset while retaining commas inside data URLs."""
    return [candidate.url for candidate in parse_srcset_candidates(value)]


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()


def _error_detail(root: Path, error: BaseException) -> str:
    return _sanitize_subprocess_output(root, str(error))


def _walk_case_sensitive(root: Path, start: Path, components: list[str]) -> Path:
    root = root.resolve()
    current = start
    for component in components:
        if component in {"", "."}:
            continue
        if component == "..":
            current = current.parent
        else:
            if current.is_dir():
                try:
                    entries = list(current.iterdir())
                except OSError as error:
                    raise LocalPathError(
                        f"cannot inspect path component {component!r}: {error}"
                    ) from error
                exact = next((entry for entry in entries if entry.name == component), None)
                if exact is not None:
                    current = exact
                else:
                    folded = [
                        entry.name
                        for entry in entries
                        if entry.name.casefold() == component.casefold()
                    ]
                    if folded:
                        raise LocalPathError(
                            f"case mismatch: requested {component!r}, actual {folded[0]!r}"
                        )
                    current = current / component
            else:
                current = current / component
        try:
            current.resolve(strict=False).relative_to(root)
        except (OSError, RuntimeError, ValueError) as error:
            raise LocalPathError("path escapes repository root") from error
    return current


def _repository_path(root: Path, relative_path: str) -> Path:
    try:
        parsed = urlsplit(relative_path)
    except ValueError as error:
        raise LocalPathError("must be a normalized relative POSIX path") from error
    raw_components = relative_path.split("/")
    posix_path = PurePosixPath(relative_path)
    if (
        not relative_path
        or "\\" in relative_path
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or posix_path.is_absolute()
        or any(component in {"", ".", ".."} for component in raw_components)
        or posix_path.as_posix() != relative_path
    ):
        raise LocalPathError("must be a normalized relative POSIX path")
    return _walk_case_sensitive(root, root, list(posix_path.parts))


def _local_path(root: Path, document: Path, reference: str) -> Path | None:
    stripped = reference.strip()
    try:
        parsed = urlsplit(stripped)
    except ValueError:
        return None
    if parsed.scheme.lower() in REMOTE_SCHEMES or parsed.netloc:
        return None
    if "\\" in stripped or "\\" in unquote(stripped):
        raise LocalPathError("backslash is not allowed in a local URL")
    url_path = unquote(parsed.path)
    if not url_path:
        return None
    if url_path.startswith("/"):
        start = root
        components = url_path.lstrip("/").split("/")
    else:
        start = document.parent
        components = url_path.split("/")
    return _walk_case_sensitive(root, start, components)


def _html_element_name(element) -> str | None:
    tag = getattr(element, "tag", None)
    if not isinstance(tag, str):
        return None
    if not tag.startswith("{"):
        return tag.lower()
    namespace, local_name = tag[1:].split("}", 1)
    return local_name if namespace == HTML_NAMESPACE else None


def _collect_html_dom(document) -> ParsedHTML:
    parsed = ParsedHTML()

    def visit(
        element,
        *,
        inside_template: bool,
        parent_figure: Figure | None,
        parent_picture: Picture | None,
    ) -> None:
        name = _html_element_name(element)
        attributes = dict(getattr(element, "attrib", {}))
        if not inside_template:
            source = attributes.get("src")
            if source:
                parsed.references.append(source)
            srcset = attributes.get("srcset")
            if srcset:
                parsed.references.extend(
                    candidate.url for candidate in parse_srcset_candidates(srcset)
                )

        current_figure = parent_figure
        current_picture = parent_picture
        if name == "figure":
            current_figure = Figure(
                attributes=attributes,
                inert_ancestor="template" if inside_template else None,
            )
            parsed.figures.append(current_figure)
        elif name == "picture":
            current_picture = Picture(
                parent_figure=current_figure,
                inert_ancestor="template" if inside_template else None,
            )
            parsed.pictures.append(current_picture)
            if current_figure is not None:
                current_figure.pictures.append(current_picture)
        elif name == "source" and current_picture is not None:
            current_picture.sources.append(attributes)
        elif name == "img":
            if current_picture is not None:
                current_picture.images.append(attributes)
                if current_picture.image is None:
                    current_picture.image = attributes
            if current_figure is not None:
                current_figure.images.append(attributes)

        child_inside_template = inside_template or name == "template"
        for child in element:
            visit(
                child,
                inside_template=child_inside_template,
                parent_figure=current_figure,
                parent_picture=current_picture,
            )

    visit(
        document,
        inside_template=False,
        parent_figure=None,
        parent_picture=None,
    )
    return parsed


def _parse_html(root: Path, relative_path: str, errors: list[str]) -> ParsedHTML | None:
    try:
        path = _repository_path(root, relative_path)
    except LocalPathError as error:
        errors.append(f"{relative_path}: {error}")
        return None
    if not path.is_file():
        errors.append(f"{relative_path}: missing HTML file")
        return None
    try:
        contents = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"{relative_path}: cannot read HTML: {_error_detail(root, error)}")
        return None
    try:
        parser = _DiagnosticHTMLParser(
            tree=html5lib.getTreeBuilder("etree"),
            namespaceHTMLElements=True,
        )
        document = parser.parse(contents, scripting=True)
    except (AssertionError, AttributeError, TypeError, ValueError) as error:
        errors.append(f"{relative_path}: invalid HTML: {error}")
        return None
    for (line, _column), code, details in parser.errors:
        if code == "duplicate-attribute":
            errors.append(
                f"{relative_path}:{line}: <{details.get('tag', 'unknown')}> "
                f"duplicate attribute {details.get('name', 'unknown')!r}"
            )
        elif code == "non-void-element-with-trailing-solidus":
            tag = details.get("name", "unknown")
            errors.append(
                f"{relative_path}:{line}: <{tag}/> self-closing syntax is invalid "
                "for a non-void HTML element"
            )
    return _collect_html_dom(document)


def _check_html_scope(root: Path, errors: list[str]) -> dict[str, ParsedHTML]:
    parsers: dict[str, ParsedHTML] = {}
    try:
        services_directory = _repository_path(root, "services")
    except LocalPathError as error:
        errors.append(f"services: {error}")
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
            try:
                local = _local_path(root, document, reference)
            except LocalPathError as error:
                errors.append(
                    f"{relative_path}: invalid local reference {reference}: {error}"
                )
                continue
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


def _load_manifest(
    root: Path,
    errors: list[str],
    sources: dict[str, Path] | None = None,
) -> dict[str, dict[str, tuple[int, int]]]:
    try:
        manifest_path = _repository_path(root, "scripts/photo-manifest.json")
    except LocalPathError as error:
        errors.append(f"scripts/photo-manifest.json: {error}")
        return {}
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
        input_path = role.get("input")
        if not isinstance(input_path, str) or not input_path:
            errors.append(
                f"scripts/photo-manifest.json: {slug}.input must be a nonempty path"
            )
        else:
            try:
                source = _repository_path(root, input_path)
            except LocalPathError as error:
                errors.append(
                    f"scripts/photo-manifest.json: {slug}.input: {error}"
                )
            else:
                if not source.is_file():
                    errors.append(
                        f"scripts/photo-manifest.json: {slug}.input: expected a file"
                    )
                elif sources is not None:
                    sources[slug] = source
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
            if width > MAX_VARIANT_DIMENSION or height > MAX_VARIANT_DIMENSION:
                errors.append(
                    f"scripts/photo-manifest.json: {slug}.{variant_name} dimensions "
                    f"{width}x{height} exceed variant dimension limit "
                    f"{MAX_VARIANT_DIMENSION}"
                )
                continue
            if width * height > MAX_VARIANT_PIXELS:
                errors.append(
                    f"scripts/photo-manifest.json: {slug}.{variant_name} has "
                    f"{width * height} pixels, exceeding variant pixel limit "
                    f"{MAX_VARIANT_PIXELS}"
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


def _enforce_decode_bounds(image: Image.Image) -> None:
    width, height = image.size
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValueError(
            f"dimensions {width}x{height} exceed dimension limit {MAX_IMAGE_DIMENSION}"
        )
    pixels = width * height
    if pixels > MAX_DECODE_PIXELS:
        raise ValueError(
            f"{pixels} pixels exceed pixel limit {MAX_DECODE_PIXELS}"
        )


def _enforce_master_bounds(image: Image.Image) -> None:
    width, height = image.size
    if width > MAX_MASTER_DIMENSION or height > MAX_MASTER_DIMENSION:
        raise ValueError(
            f"dimensions {width}x{height} exceed master dimension limit "
            f"{MAX_MASTER_DIMENSION}"
        )
    pixels = width * height
    if pixels > MAX_MASTER_PIXELS:
        raise ValueError(
            f"{pixels} pixels exceed master pixel limit {MAX_MASTER_PIXELS}"
        )


def _check_master(root: Path, slug: str, path: Path, errors: list[str]) -> bool:
    label = f"{slug} master {_relative(root, path)}"
    try:
        size = path.stat().st_size
    except OSError as error:
        errors.append(f"{label}: cannot stat image: {_error_detail(root, error)}")
        return False
    if size > MAX_MASTER_BYTES:
        errors.append(
            f"{label}: {size} bytes exceeds master byte limit {MAX_MASTER_BYTES}"
        )
        return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                _enforce_master_bounds(image)
                if image.format != "PNG":
                    raise ValueError(f"expected PNG, got {image.format!r}")
                if image.mode not in {"RGB", "RGBA"}:
                    raise ValueError(f"expected RGB or RGBA, got {image.mode!r}")
                image.verify()
            with Image.open(path) as image:
                _enforce_master_bounds(image)
                if image.format != "PNG":
                    raise ValueError(f"expected PNG, got {image.format!r}")
                if image.mode not in {"RGB", "RGBA"}:
                    raise ValueError(f"expected RGB or RGBA, got {image.mode!r}")
                image.load()
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        MemoryError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as error:
        errors.append(f"{label}: invalid image: {_error_detail(root, error)}")
        return False
    return True


def _check_masters(root: Path, sources: dict[str, Path], errors: list[str]) -> bool:
    valid = len(sources) == len(EXPECTED_ROLE_SLUGS)
    for slug in EXPECTED_ROLE_SLUGS:
        source = sources.get(slug)
        if source is not None and not _check_master(root, slug, source, errors):
            valid = False
    return valid


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
        return
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                _enforce_decode_bounds(image)
                image.verify()
            with Image.open(path) as image:
                _enforce_decode_bounds(image)
                image.load()
                actual_format = image.format
                actual_dimensions = image.size
                actual_mode = image.mode
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        MemoryError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as error:
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
    try:
        directory = _repository_path(root, "photosalon/web")
    except LocalPathError as error:
        errors.append(f"photosalon/web: {error}")
        return
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
    label = "assets/og-image.jpg"
    try:
        path = _repository_path(root, label)
    except LocalPathError as error:
        errors.append(f"{label}: {error}")
        return
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
        return
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                _enforce_decode_bounds(image)
                image.verify()
            with Image.open(path) as image:
                _enforce_decode_bounds(image)
                image.load()
                image_format = image.format
                dimensions = image.size
                mode = image.mode
                has_exif = bool(image.getexif()) or bool(image.info.get("exif"))
                has_icc = bool(image.info.get("icc_profile"))
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        MemoryError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as error:
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
        try:
            local = _local_path(root, document, reference)
        except LocalPathError:
            continue
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


def _check_source_candidate(
    root: Path,
    relative_path: str,
    source: dict[str, str],
    expected_path: str,
    label: str,
    errors: list[str],
) -> None:
    candidates = parse_srcset_candidates(source.get("srcset", ""))
    if len(candidates) != 1:
        errors.append(
            f"{relative_path}: {label} source must contain exactly one srcset candidate"
        )
        return
    candidate = candidates[0]
    if candidate.descriptor:
        errors.append(
            f"{relative_path}: {label} source must not use a srcset descriptor"
        )
    try:
        local = _local_path(root, root / relative_path, candidate.url)
    except LocalPathError as error:
        errors.append(f"{relative_path}: {label} source path is invalid: {error}")
        return
    if local is None:
        errors.append(f"{relative_path}: {label} source candidate must be local")
        return
    try:
        normalized = local.relative_to(root).as_posix()
    except ValueError:
        errors.append(f"{relative_path}: {label} source candidate escapes repository")
        return
    if normalized != expected_path:
        errors.append(
            f"{relative_path}: {label} source must reference {expected_path}, got {normalized}"
        )


def _check_picture(
    root: Path,
    relative_path: str,
    parser: ParsedHTML,
    slug: str,
    dimensions: tuple[int, int],
    errors: list[str],
    *,
    below_fold: bool,
    mobile_media: str,
    mobile_jpeg_type: str | None,
) -> Picture | None:
    expected_paths = _expected_role_paths(slug)
    matching = [
        picture
        for picture in parser.pictures
        if set(_picture_paths(root, relative_path, picture)) & set(expected_paths)
    ]
    for picture in matching:
        if picture.inert_ancestor:
            errors.append(
                f"{relative_path}: premium picture must not be inside "
                f"<{picture.inert_ancestor}>"
            )
    candidates = [picture for picture in matching if not picture.inert_ancestor]
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
        for source, expected_path, source_label in zip(
            picture.sources,
            expected_paths[:3],
            (f"{slug} mobile WebP", f"{slug} mobile JPEG", f"{slug} desktop WebP"),
            strict=True,
        ):
            _check_source_candidate(
                root,
                relative_path,
                source,
                expected_path,
                source_label,
                errors,
            )
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
    parsers: dict[str, ParsedHTML],
    roles: dict[str, dict[str, tuple[int, int]]],
    errors: list[str],
) -> None:
    index = parsers.get("index.html")
    if index is not None:
        active_pictures = [
            picture for picture in index.pictures if not picture.inert_ancestor
        ]
        if len(active_pictures) != 5:
            errors.append(
                "index.html: expected exactly 5 picture elements, got "
                f"{len(active_pictures)}"
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
        matching_hero_figures = [
            figure
            for figure in parser.figures
            if "service-hero-image" in figure.attributes.get("class", "").split()
        ]
        for figure in matching_hero_figures:
            if figure.inert_ancestor:
                errors.append(
                    f"{relative_path}: service hero figure must not be inside "
                    f"<{figure.inert_ancestor}>"
                )
        hero_figures = [
            figure for figure in matching_hero_figures if not figure.inert_ancestor
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
        matching_hero_figures = [
            figure
            for figure in child.figures
            if "service-hero-image" in figure.attributes.get("class", "").split()
        ]
        for figure in matching_hero_figures:
            if figure.inert_ancestor:
                errors.append(
                    f"{child_path}: service hero figure must not be inside "
                    f"<{figure.inert_ancestor}>"
                )
        hero_figures = [
            figure for figure in matching_hero_figures if not figure.inert_ancestor
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _derivative_snapshot(root: Path) -> dict[str, tuple[str, int, str]] | None:
    try:
        directory = _repository_path(root, "photosalon/web")
        entries = list(directory.iterdir())
        snapshot: dict[str, tuple[str, int, str]] = {}
        for entry in entries:
            if entry.is_file():
                snapshot[entry.name] = ("file", entry.stat().st_size, _sha256(entry))
            elif entry.is_dir():
                snapshot[entry.name] = ("directory", 0, "")
            else:
                snapshot[entry.name] = ("other", 0, "")
        return snapshot
    except (LocalPathError, OSError):
        return None


def _load_trusted_builder():
    path = Path(__file__).resolve().with_name("build-photo-derivatives.py")
    module_name = "_verify_photo_assets_trusted_builder"
    existing = sys.modules.get(module_name)
    if existing is not None and Path(existing.__file__).resolve() == path:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load trusted builder at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _run_trusted_worker(root: Path, staging: Path) -> dict[str, str]:
    try:
        staging.relative_to(root)
    except ValueError:
        pass
    else:
        raise RuntimeError("system temporary directory is inside audited root")
    if not staging.is_dir() or any(staging.iterdir()):
        raise RuntimeError("trusted worker staging directory must exist and be empty")

    errors: list[str] = []
    sources: dict[str, Path] = {}
    roles = _load_manifest(root, errors, sources)
    manifest_valid = (
        not errors
        and len(roles) == len(EXPECTED_ROLE_SLUGS)
        and len(sources) == len(EXPECTED_ROLE_SLUGS)
    )
    masters_valid = _check_masters(root, sources, errors)
    if not manifest_valid or not masters_valid or errors:
        raise RuntimeError("; ".join(errors))

    builder = _load_trusted_builder()
    manifest_path = _repository_path(root, "scripts/photo-manifest.json")
    trusted_roles = builder.load_manifest(manifest_path, root)
    selected = builder.select_slugs(EXPECTED_ROLE_SLUGS, trusted_roles)
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        specs, _reports = builder.stage_outputs(
            trusted_roles, selected, staging, root
        )
    generated_names = {spec.path.name for spec in specs}
    expected_names = set(_expected_derivatives(roles))
    if generated_names != expected_names or len(specs) != len(expected_names):
        raise RuntimeError("trusted builder generated an unexpected derivative name set")
    staged_names = {entry.name for entry in staging.iterdir() if entry.is_file()}
    if staged_names != expected_names:
        raise RuntimeError("trusted builder staged an unexpected derivative name set")
    return {name: _sha256(staging / name) for name in sorted(expected_names)}


def _decode_worker_result(
    root: Path,
    completed: subprocess.CompletedProcess[str],
    expected_names: set[str],
    staging: Path,
) -> dict[str, str]:
    try:
        payload = json.loads(completed.stdout.strip())
    except (AttributeError, json.JSONDecodeError) as error:
        detail = completed.stderr.strip() or completed.stdout.strip() or str(error)
        raise RuntimeError(
            f"trusted derivative worker returned invalid structured output: "
            f"{_sanitize_subprocess_output(root, detail)}"
        ) from error
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        detail = payload.get("error") if isinstance(payload, dict) else payload
        raise RuntimeError(
            "trusted derivative worker failed: "
            f"{_sanitize_subprocess_output(root, str(detail))}"
        )
    files = payload.get("files")
    if not isinstance(files, dict) or set(files) != expected_names:
        raise RuntimeError("trusted derivative worker returned an unexpected name set")
    staged_entries = list(staging.iterdir())
    if (
        {entry.name for entry in staged_entries} != expected_names
        or any(not entry.is_file() for entry in staged_entries)
    ):
        raise RuntimeError("trusted derivative worker staged an unexpected name set")
    for name, digest in files.items():
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise RuntimeError("trusted derivative worker returned an invalid hash")
        staged_path = staging / name
        if not staged_path.is_file() or _sha256(staged_path) != digest:
            raise RuntimeError("trusted derivative worker hash revalidation failed")
    if completed.returncode != 0:
        raise RuntimeError("trusted derivative worker exited unsuccessfully")
    return files


def _check_builder(
    root: Path,
    roles: dict[str, dict[str, tuple[int, int]]],
    errors: list[str],
    *,
    ready: bool,
) -> None:
    before = _derivative_snapshot(root)
    expected_names = set(_expected_derivatives(roles))
    try:
        if not ready:
            return
        with tempfile.TemporaryDirectory(prefix="verify-photo-assets-") as temporary:
            staging = Path(temporary).resolve()
            try:
                staging.relative_to(root)
            except ValueError:
                pass
            else:
                raise RuntimeError("system temporary directory is inside audited root")
            command = [
                sys.executable,
                "-I",
                "-B",
                str(Path(__file__).resolve()),
                "--worker-root",
                str(root),
                "--worker-staging",
                str(staging),
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(Path(__file__).resolve().parent),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=WORKER_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                errors.append(
                    "trusted derivative worker timed out after "
                    f"{WORKER_TIMEOUT_SECONDS} seconds"
                )
                return
            generated_hashes = _decode_worker_result(
                root, completed, expected_names, staging
            )
            for name, generated_hash in generated_hashes.items():
                live = root / "photosalon" / "web" / name
                if not live.is_file():
                    continue
                if _sha256(live) != generated_hash:
                    errors.append(
                        "trusted derivative verification: "
                        f"photosalon/web/{name}: stale derivative"
                    )
    except Exception as error:
        errors.append(
            "trusted derivative verification failed: "
            f"{_error_detail(root, error)}"
        )
    finally:
        after = _derivative_snapshot(root)
        if before != after:
            errors.append(
                "trusted derivative verification mutated photosalon/web contents"
            )
        if after is not None and len(expected_names) == 56 and set(after) != expected_names:
            errors.append(
                "trusted derivative verification post-scan found unexpected derivative names"
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
    if html5lib is None or _DiagnosticHTMLParser is None:
        return [
            "HTML5 parser: html5lib==1.1 is required; install requirements-photo.txt"
        ]
    errors: list[str] = []
    sources: dict[str, Path] = {}
    roles = _load_manifest(root, errors, sources)
    manifest_valid = (
        not errors
        and len(roles) == len(EXPECTED_ROLE_SLUGS)
        and len(sources) == len(EXPECTED_ROLE_SLUGS)
    )
    masters_valid = _check_masters(root, sources, errors)
    _check_derivatives(root, roles, errors)
    parsers = _check_html_scope(root, errors)
    _check_premium_html(root, parsers, roles, errors)
    _check_og_image(root, errors)
    _check_builder(
        root,
        roles,
        errors,
        ready=manifest_valid and masters_valid,
    )
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
    parser.add_argument("--worker-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-staging", type=Path, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.worker_root is not None or args.worker_staging is not None:
        if args.worker_root is None or args.worker_staging is None:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "worker root and staging must be provided together",
                    }
                )
            )
            return 1
        try:
            files = _run_trusted_worker(
                args.worker_root.resolve(), args.worker_staging.resolve()
            )
        except Exception as error:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": _error_detail(args.worker_root.resolve(), error),
                    }
                )
            )
            return 1
        print(json.dumps({"ok": True, "files": files}, sort_keys=True))
        return 0
    errors = audit_repository(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: 56 derivatives, 12 HTML files, 11 active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
