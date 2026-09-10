#!/usr/bin/env python3
"""Build responsive WebP and JPEG derivatives from retouched salon masters."""

import sys


def require_supported_python(version=sys.version_info) -> None:
    if version < (3, 11):
        detected = ".".join(str(part) for part in version[:3])
        raise RuntimeError(
            f"Python 3.11 or newer is required; detected Python {detected}"
        )


require_supported_python()

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_FILE = ROOT / "scripts" / "photo-manifest.json"
OUTPUT_DIRECTORY = Path("photosalon/web")
VARIANT_NAMES = ("desktop", "mobile")
FORMATS = (("jpg", "JPEG"), ("webp", "WEBP"))
MAX_OUTPUT_BYTES = 900 * 1024
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ManifestError(ValueError):
    """The photo manifest is malformed or unsafe."""


class OutputValidationError(RuntimeError):
    """A generated or committed derivative violates its output contract."""


class PromotionRecoveryError(BaseExceptionGroup):
    """Promotion failed and at least one rollback action also failed."""

    def __new__(cls, exceptions: list[BaseException], staging_directory: Path):
        instance = super().__new__(
            cls,
            "Derivative promotion and rollback failed",
            exceptions,
        )
        instance.preserve_staging = True
        instance.staging_directory = staging_directory
        return instance

    def __init__(
        self, exceptions: list[BaseException], staging_directory: Path
    ) -> None:
        pass

    def derive(self, exceptions):
        return type(self)(list(exceptions), self.staging_directory)

    def __str__(self) -> str:
        return (
            f"{super().__str__()}; preserved staging and backups at "
            f"{self.staging_directory}"
        )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _add_recovery_note(failure: BaseException, note_builder) -> None:
    try:
        note = note_builder()
    except BaseException:
        note = "Recovery diagnostics unavailable"
    try:
        failure.add_note(note)
    except BaseException:
        pass


@dataclass(frozen=True)
class Variant:
    width: int
    height: int
    focal_x: float
    focal_y: float


@dataclass(frozen=True)
class Role:
    slug: str
    source: Path
    variants: dict[str, Variant]


@dataclass(frozen=True)
class OutputSpec:
    slug: str
    variant: str
    extension: str
    format: str
    width: int
    height: int
    path: Path


@dataclass(frozen=True)
class ValidationResult:
    slug: str
    variant: str
    format: str
    path: Path
    width: int
    height: int
    size_bytes: int


def _mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ManifestError(f"{label}: expected an object")
    return value


def _positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManifestError(f"{label}: expected a positive integer")
    return value


def _focal(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{label}: expected a number from 0 to 1")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ManifestError(f"{label}: expected a number from 0 to 1")
    return value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def output_specs(role: Role, root: Path) -> list[OutputSpec]:
    directory = root / OUTPUT_DIRECTORY
    specs: list[OutputSpec] = []
    for variant_name in VARIANT_NAMES:
        variant = role.variants[variant_name]
        for extension, image_format in FORMATS:
            specs.append(
                OutputSpec(
                    slug=role.slug,
                    variant=variant_name,
                    extension=extension,
                    format=image_format,
                    width=variant.width,
                    height=variant.height,
                    path=directory / f"{role.slug}-{variant_name}.{extension}",
                )
            )
    return specs


def load_manifest(
    manifest_path: Path = MANIFEST_FILE, root: Path = ROOT
) -> dict[str, Role]:
    root = root.resolve()
    manifest_path = Path(manifest_path)
    try:
        payload = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"Cannot read photo manifest {manifest_path}: {error}") from error
    roles_payload = _mapping(payload, "manifest")
    if not roles_payload:
        raise ManifestError("manifest: expected at least one photo role")

    roles: dict[str, Role] = {}
    expected_paths: set[str] = set()
    for slug, role_value in roles_payload.items():
        if not isinstance(slug, str) or not SLUG_PATTERN.fullmatch(slug):
            raise ManifestError(f"Unsafe photo slug: {slug!r}")
        role_payload = _mapping(role_value, slug)
        if set(role_payload) != {"input", "variants"}:
            raise ManifestError(f"{slug}: expected exactly 'input' and 'variants'")
        input_value = role_payload["input"]
        if not isinstance(input_value, str) or not input_value:
            raise ManifestError(f"{slug}.input: expected a nonempty path string")
        source = (root / input_value).resolve()
        if not _is_within(source, root):
            raise ManifestError(f"{slug}.input escapes ROOT: {input_value}")
        if not source.is_file():
            raise ManifestError(f"{slug}.input does not exist: {source}")

        variants_payload = _mapping(role_payload["variants"], f"{slug}.variants")
        if set(variants_payload) != set(VARIANT_NAMES):
            raise ManifestError(
                f"{slug}.variants: expected exactly desktop and mobile"
            )
        variants: dict[str, Variant] = {}
        for variant_name in VARIANT_NAMES:
            label = f"{slug}.{variant_name}"
            variant_payload = _mapping(variants_payload[variant_name], label)
            if set(variant_payload) != {"width", "height", "focalX", "focalY"}:
                raise ManifestError(
                    f"{label}: expected width, height, focalX, and focalY"
                )
            variants[variant_name] = Variant(
                width=_positive_int(variant_payload["width"], f"{label}.width"),
                height=_positive_int(variant_payload["height"], f"{label}.height"),
                focal_x=_focal(variant_payload["focalX"], f"{label}.focalX"),
                focal_y=_focal(variant_payload["focalY"], f"{label}.focalY"),
            )
        role = Role(slug=slug, source=source, variants=variants)
        roles[slug] = role
        for spec in output_specs(role, root):
            normalized = os.path.normcase(str(spec.path.resolve(strict=False)))
            if normalized in expected_paths:
                raise ManifestError(f"Duplicate expected output path: {spec.path}")
            expected_paths.add(normalized)
    return roles


def select_slugs(slugs: Iterable[str] | None, roles: dict[str, Role]) -> list[str]:
    selected = list(slugs or roles)
    seen: set[str] = set()
    duplicates: list[str] = []
    for slug in selected:
        if slug in seen and slug not in duplicates:
            duplicates.append(slug)
        seen.add(slug)
    if duplicates:
        raise ValueError(f"Duplicate slug(s): {', '.join(duplicates)}")
    unknown = [slug for slug in selected if slug not in roles]
    if unknown:
        raise ValueError(
            f"Unknown slug(s): {', '.join(unknown)}. Expected one of: "
            + ", ".join(roles)
        )
    return selected


def crop_box(
    source_size: tuple[int, int],
    target_size: tuple[int, int],
    focal_x: float,
    focal_y: float,
) -> tuple[float, float, float, float]:
    source_width, source_height = source_size
    target_width, target_height = target_size
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_height = float(source_height)
        crop_width = crop_height * target_ratio
    else:
        crop_width = float(source_width)
        crop_height = crop_width / target_ratio
    left = min(max(focal_x * source_width - crop_width / 2, 0.0), source_width - crop_width)
    top = min(max(focal_y * source_height - crop_height / 2, 0.0), source_height - crop_height)
    return (left, top, left + crop_width, top + crop_height)


def render_variant(source: Image.Image, variant: Variant) -> Image.Image:
    oriented = ImageOps.exif_transpose(source).convert("RGB")
    box = crop_box(
        oriented.size,
        (variant.width, variant.height),
        variant.focal_x,
        variant.focal_y,
    )
    rendered = oriented.crop(box).resize(
        (variant.width, variant.height), Image.Resampling.LANCZOS
    )
    rendered.info.clear()
    return rendered


def save_output(image: Image.Image, spec: OutputSpec, path: Path) -> None:
    if spec.format == "WEBP":
        image.save(path, format="WEBP", quality=84, method=6)
    else:
        image.save(
            path,
            format="JPEG",
            quality=88,
            optimize=True,
            progressive=True,
        )


def _metadata_keys(image: Image.Image) -> set[str]:
    allowed = set()
    if image.format == "JPEG":
        allowed = {
            "jfif",
            "jfif_version",
            "jfif_unit",
            "jfif_density",
            "progressive",
            "progression",
        }
    elif image.format == "WEBP":
        # Pillow exposes these decoder defaults even for a static WebP with no
        # animation or metadata chunks.
        allowed = {"loop", "background"}
    return set(image.info) - allowed


def validate_output(path: Path, spec: OutputSpec) -> ValidationResult:
    try:
        size_bytes = path.stat().st_size
    except OSError as error:
        raise OutputValidationError(f"{path}: missing output: {error}") from error
    if size_bytes == 0:
        raise OutputValidationError(f"{path}: output is empty")
    if size_bytes > MAX_OUTPUT_BYTES:
        raise OutputValidationError(
            f"{path}: {size_bytes} bytes exceeds {MAX_OUTPUT_BYTES} bytes"
        )
    try:
        with Image.open(path) as image:
            if image.format != spec.format:
                raise OutputValidationError(
                    f"{path}: expected {spec.format}, got {image.format!r}"
                )
            if image.mode != "RGB":
                raise OutputValidationError(
                    f"{path}: expected RGB, got {image.mode!r}"
                )
            if image.size != (spec.width, spec.height):
                raise OutputValidationError(
                    f"{path}: expected {spec.width}x{spec.height}, got "
                    f"{image.width}x{image.height}"
                )
            if image.getexif():
                raise OutputValidationError(f"{path}: unexpected EXIF metadata")
            unexpected_metadata = _metadata_keys(image)
            if unexpected_metadata:
                raise OutputValidationError(
                    f"{path}: unexpected metadata: {sorted(unexpected_metadata)}"
                )
            if spec.format == "JPEG" and not (
                image.info.get("progressive") or image.info.get("progression")
            ):
                raise OutputValidationError(f"{path}: JPEG is not progressive")
            image.load()
        with Image.open(path) as image:
            image.verify()
    except OutputValidationError:
        raise
    except (OSError, SyntaxError) as error:
        raise OutputValidationError(f"{path}: invalid image: {error}") from error
    return ValidationResult(
        slug=spec.slug,
        variant=spec.variant,
        format=spec.format,
        path=path,
        width=spec.width,
        height=spec.height,
        size_bytes=size_bytes,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_directory_names(directory: Path, allowed: set[str]) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    unexpected = sorted(actual - allowed)
    if unexpected:
        raise OutputValidationError(
            f"{directory}: unexpected output name(s): {', '.join(unexpected)}"
        )


def validate_output_set(
    specs: list[OutputSpec], directory: Path, *, allowed_names: set[str] | None = None
) -> list[ValidationResult]:
    expected_names = {spec.path.name for spec in specs}
    _validate_directory_names(directory, allowed_names or expected_names)
    actual_names = {path.name for path in directory.iterdir() if path.is_file()}
    missing = sorted(expected_names - actual_names)
    if missing:
        raise OutputValidationError(
            f"{directory}: missing output(s): {', '.join(missing)}"
        )
    return [validate_output(directory / spec.path.name, spec) for spec in specs]


def stage_outputs(
    roles: dict[str, Role], selected: list[str], staging_directory: Path, root: Path
) -> tuple[list[OutputSpec], list[ValidationResult]]:
    specs: list[OutputSpec] = []
    for slug in selected:
        role = roles[slug]
        with Image.open(role.source) as source:
            for variant_name in VARIANT_NAMES:
                variant = role.variants[variant_name]
                rendered = render_variant(source, variant)
                for spec in output_specs(role, root):
                    if spec.variant != variant_name:
                        continue
                    staged_path = staging_directory / spec.path.name
                    save_output(rendered, spec, staged_path)
                    specs.append(spec)
    staged_reports = validate_output_set(specs, staging_directory)
    reports = [
        replace(report, path=spec.path)
        for report, spec in zip(staged_reports, specs, strict=True)
    ]
    return specs, reports


def promote_staged_outputs(specs: list[OutputSpec], staging_directory: Path) -> None:
    backups: dict[Path, Path] = {}
    attempted: list[Path] = []
    backup_directory = staging_directory
    try:
        destinations = [spec.path for spec in specs]
        for destination in destinations:
            if destination.exists():
                backup = backup_directory / (
                    f"{destination.name}.{uuid.uuid4().hex}.backup"
                )
                shutil.copy2(destination, backup)
                backups[destination] = backup
        for destination in destinations:
            attempted.append(destination)
            os.replace(staging_directory / destination.name, destination)
    except BaseException as primary_error:
        rollback_errors: list[BaseException] = []
        for destination in reversed(attempted):
            try:
                backup = backups.get(destination)
                if backup is not None and backup.exists():
                    os.replace(backup, destination)
                elif backup is None and destination.exists():
                    destination.unlink()
            except BaseException as error:
                rollback_errors.append(error)
        if rollback_errors:
            failure = PromotionRecoveryError(
                [primary_error, *rollback_errors],
                staging_directory,
            )
            try:
                recoverable = sorted(
                    str(path)
                    for path in staging_directory.rglob("*")
                    if path.is_file()
                )
            except BaseException as enumeration_error:
                _add_recovery_note(
                    failure,
                    lambda: (
                        "Recovery-file enumeration failure: "
                        + str(enumeration_error)
                    ),
                )
            else:
                _add_recovery_note(
                    failure,
                    lambda: (
                        "Recoverable files: "
                        + (", ".join(recoverable) if recoverable else "none found")
                    ),
                )
            raise failure
        raise


def build(
    slugs: Iterable[str] | None = None,
    *,
    verify: bool = False,
    manifest_path: Path = MANIFEST_FILE,
    root: Path = ROOT,
) -> list[ValidationResult]:
    root = Path(root).resolve()
    roles = load_manifest(Path(manifest_path), root)
    selected = select_slugs(slugs, roles)
    selected_specs = [
        spec for slug in selected for spec in output_specs(roles[slug], root)
    ]
    output_directory = root / OUTPUT_DIRECTORY
    all_expected_names = {
        spec.path.name for role in roles.values() for spec in output_specs(role, root)
    }
    if verify:
        if not output_directory.is_dir():
            raise OutputValidationError(f"{output_directory}: output directory is missing")
        verification_directory = output_directory / (
            f".verification-{os.getpid()}-{uuid.uuid4().hex}"
        )
        verification_directory.mkdir()
        try:
            expected_specs, _ = stage_outputs(
                roles, selected, verification_directory, root
            )
            live_reports = validate_output_set(
                selected_specs,
                output_directory,
                allowed_names=all_expected_names,
            )
            for spec in expected_specs:
                expected_path = verification_directory / spec.path.name
                expected_sha256 = sha256_file(expected_path)
                actual_sha256 = sha256_file(spec.path)
                if actual_sha256 != expected_sha256:
                    raise OutputValidationError(
                        f"{spec.path}: stale derivative; expected SHA-256 "
                        f"{expected_sha256}, got {actual_sha256}; rebuild outputs"
                    )
            return live_reports
        finally:
            shutil.rmtree(verification_directory, ignore_errors=True)

    output_directory.mkdir(parents=True, exist_ok=True)
    staging_directory = output_directory / f".staging-{os.getpid()}"
    staging_directory.mkdir(exist_ok=False)
    preserve_staging = False
    try:
        _validate_directory_names(output_directory, all_expected_names)
        specs, reports = stage_outputs(roles, selected, staging_directory, root)
        promote_staged_outputs(specs, staging_directory)
        return reports
    except BaseException as error:
        preserve_staging = bool(getattr(error, "preserve_staging", False))
        raise
    finally:
        if not preserve_staging:
            shutil.rmtree(staging_directory, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build responsive WebP and JPEG salon photo derivatives."
    )
    parser.add_argument(
        "slugs",
        nargs="*",
        metavar="SLUG",
        help="optional role slug; omit to process all roles",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="validate existing selected outputs without rebuilding",
    )
    args = parser.parse_args(argv)
    try:
        roles = load_manifest()
        selected = select_slugs(args.slugs, roles)
        reports = build(selected, verify=args.verify)
    except ValueError as error:
        parser.error(str(error))
    except RuntimeError as error:
        parser.exit(1, f"error: {error}\n")
    for report in reports:
        print(
            f"OK {report.path.relative_to(ROOT)}: {report.width}x{report.height} "
            f"{report.format} RGB, {report.size_bytes} bytes"
        )
    action = "Verified" if args.verify else "Built and validated"
    print(f"{action} {len(reports)} derivative(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
