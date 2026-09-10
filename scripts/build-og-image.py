#!/usr/bin/env python3
"""Build Prestige Coiffure's deterministic Open Graph image.

Run ``python scripts/build-og-image.py`` from any directory to rebuild the
default ``assets/og-image.jpg``. Use ``--source``, ``--logo`` and ``--output``
to override paths; relative overrides are resolved from the current directory.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import warnings
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError


OUTPUT_SIZE = (1200, 630)
FOCAL_POINT = (0.50, 0.48)
LOGO_WIDTH = 360
RIGHT_MARGIN = 72
CREAM = (239, 227, 204)
TARGET_BYTES = 500 * 1024
MAX_BYTES = 900 * 1024
MAX_SOURCE_PIXELS = 40_000_000
MAX_LOGO_PIXELS = 16_000_000
MIN_RENDERED_LOGO_HEIGHT = 48
MAX_RENDERED_LOGO_HEIGHT = 240


class OgImageError(RuntimeError):
    """Base error for an Open Graph build failure."""


class InputImageError(OgImageError):
    """Raised when a source asset cannot safely be used."""


class OutputImageError(OgImageError):
    """Raised when the encoded result does not meet the output contract."""


def default_paths(root: Path) -> tuple[Path, Path, Path]:
    """Return source, logo and output paths rooted at the repository."""
    root = Path(root)
    return (
        root / "photosalon" / "retouched" / "hero-salon.png",
        root / "assets" / "logo.png",
        root / "assets" / "og-image.jpg",
    )


def _normalized_path(path: Path, label: str) -> str:
    try:
        resolved = Path(path).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise InputImageError(f"Cannot resolve {label} path '{path}': {exc}") from exc
    return os.path.normcase(os.path.normpath(os.fspath(resolved)))


def _paths_alias(first: Path, second: Path) -> bool:
    if _normalized_path(first, "output") == _normalized_path(second, "input"):
        return True
    try:
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except OSError as exc:
        raise InputImageError(
            f"Cannot compare output path '{first}' with input path '{second}': {exc}"
        ) from exc


def _reject_output_aliases(source_path: Path, logo_path: Path, output_path: Path) -> None:
    for label, input_path in (("source", source_path), ("logo", logo_path)):
        if _paths_alias(output_path, input_path):
            raise InputImageError(
                f"Output path '{output_path}' aliases {label} image '{input_path}'; "
                "choose a distinct --output path"
            )


def _validate_input_dimensions(size: tuple[int, int], label: str) -> None:
    width, height = size
    if width < 2 or height < 2:
        raise InputImageError(
            f"Invalid {label} image dimensions {width}x{height}: minimum is 2x2"
        )
    limit = MAX_LOGO_PIXELS if label == "logo" else MAX_SOURCE_PIXELS
    pixels = width * height
    if pixels > limit:
        raise InputImageError(
            f"Invalid {label} image dimensions {width}x{height}: {pixels} pixels "
            f"exceed application pixel limit {limit}"
        )


def _load_image(path: Path, label: str, *, require_alpha: bool = False) -> Image.Image:
    path = Path(path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as opened:
                _validate_input_dimensions(opened.size, label)
                opened.load()
                oriented = ImageOps.exif_transpose(opened)
                _validate_input_dimensions(oriented.size, label)
                if require_alpha and "A" not in oriented.getbands():
                    raise InputImageError(
                        f"Invalid {label} image '{path}': an alpha channel is required"
                    )
                converted = oriented.convert("RGBA" if require_alpha else "RGB")
            converted.info.clear()
            return converted
    except InputImageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InputImageError(
            f"Cannot read {label} image '{path}': decompression bomb protection "
            f"triggered: {exc}"
        ) from exc
    except MemoryError as exc:
        raise InputImageError(
            f"Cannot read {label} image '{path}': insufficient memory while decoding"
        ) from exc
    except (FileNotFoundError, PermissionError, UnidentifiedImageError, OSError) as exc:
        raise InputImageError(f"Cannot read {label} image '{path}': {exc}") from exc


def _darken_right(image: Image.Image) -> Image.Image:
    """Apply a restrained warm veil that grows smoothly toward the right."""
    width, height = image.size
    alpha = Image.new("L", image.size)
    draw = ImageDraw.Draw(alpha)
    for x in range(width):
        progress = max(0.0, min(1.0, (x / (width - 1) - 0.24) / 0.76))
        smooth = progress * progress * (3.0 - 2.0 * progress)
        opacity = round(24 + 166 * smooth)
        draw.line((x, 0, x, height), fill=opacity)
    veil = Image.new("RGB", image.size, (24, 17, 12))
    return Image.composite(veil, image, alpha)


def _prepare_logo(logo: Image.Image) -> Image.Image:
    """Recolor visible logo pixels to cream while retaining original alpha."""
    alpha = logo.getchannel("A")
    visible_bounds = alpha.getbbox()
    if visible_bounds is None:
        raise InputImageError("Invalid logo image: alpha channel contains no visible pixels")
    alpha = alpha.crop(visible_bounds)
    target_height = max(1, round(alpha.height * LOGO_WIDTH / alpha.width))
    if not MIN_RENDERED_LOGO_HEIGHT <= target_height <= MAX_RENDERED_LOGO_HEIGHT:
        raise InputImageError(
            f"Invalid logo dimensions after alpha crop: {alpha.width}x{alpha.height} "
            f"would render at {LOGO_WIDTH}x{target_height}; allowed height is "
            f"{MIN_RENDERED_LOGO_HEIGHT}..{MAX_RENDERED_LOGO_HEIGHT}"
        )
    alpha = alpha.resize((LOGO_WIDTH, target_height), Image.Resampling.LANCZOS)
    cream_logo = Image.new("RGBA", alpha.size, (*CREAM, 0))
    cream_logo.putalpha(alpha)
    return cream_logo


def _compose(source: Image.Image, logo: Image.Image) -> Image.Image:
    background = ImageOps.fit(
        source,
        OUTPUT_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=FOCAL_POINT,
    )
    background = _darken_right(background)
    cream_logo = _prepare_logo(logo)
    position = (
        OUTPUT_SIZE[0] - RIGHT_MARGIN - cream_logo.width,
        round((OUTPUT_SIZE[1] - cream_logo.height) / 2),
    )
    background.paste(cream_logo, position, cream_logo)
    composed = background.convert("RGB")
    composed.info.clear()
    return composed


def _save_clean_jpeg(image: Image.Image, path: Path) -> None:
    for quality in (88, 85, 82, 78):
        image.save(
            path,
            format="JPEG",
            quality=quality,
            subsampling="4:2:0",
            optimize=True,
            progressive=True,
        )
        if path.stat().st_size <= TARGET_BYTES:
            break
    if path.stat().st_size > MAX_BYTES:
        raise OutputImageError(
            f"Encoded output is {path.stat().st_size} bytes; limit is {MAX_BYTES} bytes"
        )


def _validate_output(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "JPEG" or image.size != OUTPUT_SIZE or image.mode != "RGB":
                raise OutputImageError(
                    f"Invalid encoded output '{path}': expected 1200x630 RGB JPEG"
                )
            if image.info.get("progressive") != 1:
                raise OutputImageError(f"Invalid encoded output '{path}': not progressive")
            if image.getexif() or any(
                key in image.info
                for key in ("icc_profile", "exif", "xmp", "comment", "photoshop")
            ):
                raise OutputImageError(f"Invalid encoded output '{path}': metadata found")
    except OutputImageError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise OutputImageError(f"Cannot validate encoded output '{path}': {exc}") from exc


def build_og_image(
    *, source_path: Path, logo_path: Path, output_path: Path
) -> Path:
    """Build and atomically replace one deterministic Open Graph JPEG."""
    source_path = Path(source_path)
    logo_path = Path(logo_path)
    output_path = Path(output_path)
    _reject_output_aliases(source_path, logo_path, output_path)

    source = _load_image(source_path, "source")
    logo = _load_image(logo_path, "logo", require_alpha=True)
    composed = _compose(source, logo)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputImageError(
            f"Cannot create output directory '{output_path.parent}': {exc}"
        ) from exc

    temporary_path: Path | None = None
    failure: BaseException | None = None
    try:
        try:
            with tempfile.NamedTemporaryFile(
                dir=output_path.parent,
                prefix=".og-image-",
                suffix=".jpg",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
        except OSError as exc:
            raise OutputImageError(
                f"Cannot create temporary output beside '{output_path}': {exc}"
            ) from exc

        try:
            _save_clean_jpeg(composed, temporary_path)
        except OutputImageError:
            raise
        except OSError as exc:
            raise OutputImageError(
                f"Cannot encode temporary output '{temporary_path}': {exc}"
            ) from exc
        _validate_output(temporary_path)
        try:
            with temporary_path.open("r+b") as encoded:
                os.fsync(encoded.fileno())
        except OSError as exc:
            raise OutputImageError(
                f"Cannot sync temporary output '{temporary_path}': {exc}"
            ) from exc
        try:
            os.replace(temporary_path, output_path)
        except OSError as exc:
            raise OutputImageError(
                f"Cannot replace output '{output_path}': {exc}"
            ) from exc
        temporary_path = None
    except BaseException as exc:
        failure = exc

    if failure is not None:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                raise OutputImageError(
                    f"{failure}; cleanup failed for temporary file '{temporary_path}' "
                    f"(retained for manual recovery): {cleanup_error}"
                ) from failure
        raise failure
    return output_path


def _parser(root: Path) -> argparse.ArgumentParser:
    source, logo, output = default_paths(root)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=source, help=f"hero image (default: {source})")
    parser.add_argument("--logo", type=Path, default=logo, help=f"RGBA logo (default: {logo})")
    parser.add_argument("--output", type=Path, default=output, help=f"JPEG output (default: {output})")
    return parser


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    args = _parser(root).parse_args(argv)
    try:
        output = build_og_image(
            source_path=args.source,
            logo_path=args.logo,
            output_path=args.output,
        )
    except OgImageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Built 1200x630 RGB JPEG: {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
