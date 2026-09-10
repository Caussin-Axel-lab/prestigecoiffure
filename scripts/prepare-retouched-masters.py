#!/usr/bin/env python3
"""Prepare deterministic, non-generative premium salon photo masters."""

import argparse
import hashlib
from pathlib import Path
from typing import Iterable, NamedTuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent.parent


class RetouchTarget(NamedTuple):
    source: Path
    output: Path
    profile: str


class ValidationResult(NamedTuple):
    slug: str
    source: Path
    output: Path
    source_sha256: str
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    normalized_mean_absolute_error: float


def _target(slug: str) -> RetouchTarget:
    return RetouchTarget(
        source=ROOT / "photosalon" / f"{slug}.jpg",
        output=ROOT / "photosalon" / "retouched" / f"{slug}.png",
        profile="salon",
    )


RETOUCHES = {
    slug: _target(slug)
    for slug in (
        "hero-salon",
        "salon-lounge",
        "salon-barbier",
        "salon-headspa",
        "cabine-headspa",
    )
}


def prepare_graded_source(source: Image.Image) -> Image.Image:
    """Orient, gently smooth, and naturally grade a salon photograph."""
    original = ImageOps.exif_transpose(source).convert("RGB")
    median = original.filter(ImageFilter.MedianFilter(size=3))
    graded = Image.blend(original, median, 0.18)
    graded = ImageEnhance.Color(graded).enhance(0.98)
    graded = ImageEnhance.Contrast(graded).enhance(1.025)
    return ImageEnhance.Brightness(graded).enhance(1.005)


def render_master(source: Image.Image) -> Image.Image:
    """Create the exact 2x salon master from an open source image."""
    graded = prepare_graded_source(source)
    master = graded.resize(
        (graded.width * 2, graded.height * 2),
        Image.Resampling.LANCZOS,
    )
    return master.filter(ImageFilter.UnsharpMask(radius=1.15, percent=45, threshold=5))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_output(slug: str, target: RetouchTarget, source_sha256: str) -> ValidationResult:
    with Image.open(target.source) as source:
        oriented = ImageOps.exif_transpose(source).convert("RGB")
        source_size = oriented.size
        graded = prepare_graded_source(source)

    with Image.open(target.output) as output:
        if output.format != "PNG":
            raise RuntimeError(f"{slug}: expected PNG, got {output.format!r}")
        if output.mode != "RGB":
            raise RuntimeError(f"{slug}: expected RGB, got {output.mode!r}")
        expected_size = (source_size[0] * 2, source_size[1] * 2)
        if output.size != expected_size:
            raise RuntimeError(f"{slug}: expected {expected_size}, got {output.size}")
        if output.getexif():
            raise RuntimeError(f"{slug}: output unexpectedly contains EXIF metadata")
        output_size = output.size
        downscaled = output.resize(source_size, Image.Resampling.LANCZOS)

    difference = np.abs(
        np.asarray(downscaled, dtype=np.int16) - np.asarray(graded, dtype=np.int16)
    )
    normalized_error = float(difference.mean())
    if normalized_error > 4.0:
        raise RuntimeError(
            f"{slug}: normalized mean absolute pixel error "
            f"{normalized_error:.4f} exceeds 4.0"
        )

    with Image.open(target.output) as output:
        output.verify()

    return ValidationResult(
        slug=slug,
        source=target.source,
        output=target.output,
        source_sha256=source_sha256,
        source_size=source_size,
        output_size=output_size,
        normalized_mean_absolute_error=normalized_error,
    )


def select_slugs(slugs: Iterable[str] | None) -> list[str]:
    selected = [] if slugs is None else list(slugs)
    if not selected:
        selected = list(RETOUCHES)
    unknown = [slug for slug in selected if slug not in RETOUCHES]
    if unknown:
        choices = ", ".join(RETOUCHES)
        raise ValueError(f"Unknown slug(s): {', '.join(unknown)}. Expected one of: {choices}")
    return selected


def build(slugs: Iterable[str] | None = None) -> list[ValidationResult]:
    selected = select_slugs(slugs)

    before = {slug: sha256_file(RETOUCHES[slug].source) for slug in selected}
    reports: list[ValidationResult] = []
    try:
        for slug in selected:
            target = RETOUCHES[slug]
            target.output.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(target.source) as source:
                master = render_master(source)
            master.info.clear()
            master.save(target.output, format="PNG", optimize=True)
            reports.append(validate_output(slug, target, before[slug]))
    finally:
        changed = [
            slug
            for slug in selected
            if sha256_file(RETOUCHES[slug].source) != before[slug]
        ]
        if changed:
            raise RuntimeError(f"Source file changed unexpectedly: {', '.join(changed)}")

    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic 2x premium salon photo masters."
    )
    parser.add_argument(
        "slugs",
        nargs="*",
        metavar="SLUG",
        help="optional salon photo slug; omit to build all five",
    )
    args = parser.parse_args(argv)
    try:
        reports = build(args.slugs)
    except ValueError as error:
        parser.error(str(error))

    for report in reports:
        print(
            f"OK {report.slug}: {report.source_size[0]}x{report.source_size[1]} -> "
            f"{report.output_size[0]}x{report.output_size[1]} PNG RGB; "
            f"NMAE={report.normalized_mean_absolute_error:.4f}; "
            f"source_sha256={report.source_sha256}"
        )
    print(f"Validated {len(reports)} master(s); source SHA-256 unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
