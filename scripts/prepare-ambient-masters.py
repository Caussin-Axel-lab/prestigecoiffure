#!/usr/bin/env python3
"""Prepare native-size Canon salon masters with a restrained ambient grade.

The Canon captures already have enough resolution for the site. This pass only
develops their light and colour, crops them to the existing art-direction
frames, and writes metadata-free PNG masters for the responsive derivative
builder. No denoising, sharpening, or upscaling is applied.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import uuid
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "photosalon"
OUTPUT_DIR = SOURCE_DIR / "retouched"


# Keep the established master silhouettes so existing responsive crops and
# layout reservations remain stable while replacing their photographic source.
TARGETS: dict[str, tuple[int, int, float, float]] = {
    "hero-salon": (2400, 3000, 0.48, 0.52),
    "salon-lounge": (1600, 3200, 0.50, 0.50),
    "salon-barbier": (1600, 1600, 0.52, 0.50),
    "salon-headspa": (1600, 1600, 0.50, 0.50),
    "cabine-headspa": (2800, 1866, 0.52, 0.50),
    "service-head-spa": (3600, 2024, 0.52, 0.50),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def crop_box(
    source_size: tuple[int, int],
    target_size: tuple[int, int],
    focal_x: float,
    focal_y: float,
) -> tuple[int, int, int, int]:
    source_width, source_height = source_size
    target_width, target_height = target_size
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = round(crop_height * target_ratio)
    else:
        crop_width = source_width
        crop_height = round(crop_width / target_ratio)
    left = round(
        min(max(focal_x * source_width - crop_width / 2, 0), source_width - crop_width)
    )
    top = round(
        min(
            max(focal_y * source_height - crop_height / 2, 0),
            source_height - crop_height,
        )
    )
    return left, top, left + crop_width, top + crop_height


def ambient_grade(source: Image.Image) -> Image.Image:
    """Lift the salon's low light while preserving its warm, cinematic mood."""
    image = ImageOps.exif_transpose(source).convert("RGB")
    image = ImageEnhance.Brightness(image).enhance(1.055)
    image = ImageEnhance.Contrast(image).enhance(1.025)
    image = ImageEnhance.Color(image).enhance(1.02)

    # A very small channel bias keeps the wood, brass and olive tones coherent
    # with the site's warm editorial palette without making skin or whites orange.
    red, green, blue = image.split()
    red = red.point(lambda value: min(255, round(value * 1.018 + 1)))
    blue = blue.point(lambda value: max(0, round(value * 0.975)))
    return Image.merge("RGB", (red, green, blue))


def prepare(slug: str, staged_path: Path) -> None:
    target_width, target_height, focal_x, focal_y = TARGETS[slug]
    source_path = SOURCE_DIR / f"{slug}.jpg"
    with Image.open(source_path) as source:
        graded = ambient_grade(source)
        cropped = graded.crop(
            crop_box(graded.size, (target_width, target_height), focal_x, focal_y)
        )
        master = cropped.resize(
            (target_width, target_height), Image.Resampling.LANCZOS
        )
        master.info.clear()
        master.save(staged_path, format="PNG", optimize=True)

    with Image.open(staged_path) as output:
        output.load()
        if output.format != "PNG" or output.mode != "RGB":
            raise RuntimeError(f"{slug}: expected metadata-free RGB PNG")
        if output.size != (target_width, target_height):
            raise RuntimeError(
                f"{slug}: expected {(target_width, target_height)}, got {output.size}"
            )
        if output.info or output.getexif():
            raise RuntimeError(f"{slug}: output unexpectedly contains metadata")
    with Image.open(staged_path) as output:
        output.verify()


def build(slugs: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUTPUT_DIR / f".ambient-staging-{os.getpid()}"
    staging.mkdir()
    staged: dict[str, Path] = {}
    source_hashes: dict[str, str] = {}
    try:
        for slug in slugs:
            source = SOURCE_DIR / f"{slug}.jpg"
            if not source.is_file():
                raise RuntimeError(f"{slug}: missing source {source}")
            source_hashes[slug] = sha256_file(source)
            candidate = staging / f"{slug}.{uuid.uuid4().hex}.candidate.png"
            prepare(slug, candidate)
            staged[slug] = candidate

        for slug in slugs:
            if sha256_file(SOURCE_DIR / f"{slug}.jpg") != source_hashes[slug]:
                raise RuntimeError(f"{slug}: source changed during processing")
            os.replace(staged[slug], OUTPUT_DIR / f"{slug}.png")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    for slug in slugs:
        output = OUTPUT_DIR / f"{slug}.png"
        with Image.open(output) as image:
            print(
                f"OK {slug}: {image.width}x{image.height} PNG RGB; "
                f"source_sha256={source_hashes[slug]}; "
                f"output_sha256={sha256_file(output)}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*", choices=sorted(TARGETS))
    args = parser.parse_args()
    build(args.slugs or list(TARGETS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
