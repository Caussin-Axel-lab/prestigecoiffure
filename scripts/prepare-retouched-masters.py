#!/usr/bin/env python3
"""Prepare deterministic salon photo masters. Requires Python 3.11 or newer."""

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
import os
import shutil
import struct
import uuid
from pathlib import Path
from typing import Iterable, NamedTuple

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageStat


ROOT = Path(__file__).resolve().parent.parent
HASHES_FILE = ROOT / "scripts" / "photo-master-hashes.json"


class RetouchTarget(NamedTuple):
    source: Path
    output: Path
    profile: str


class RetouchProfile(NamedTuple):
    median_blend: float
    color: float
    contrast: float
    brightness: float
    unsharp_radius: float
    unsharp_percent: int
    unsharp_threshold: int


class ValidationResult(NamedTuple):
    slug: str
    source: Path
    output: Path
    source_sha256: str
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    normalized_mean_absolute_error: float
    edge_energy_ratio: float


PROFILES = {
    "salon": RetouchProfile(
        median_blend=0.18,
        color=0.98,
        contrast=1.025,
        brightness=1.005,
        unsharp_radius=1.15,
        unsharp_percent=45,
        unsharp_threshold=5,
    ),
    "service": RetouchProfile(
        median_blend=0.10,
        color=0.96,
        contrast=1.06,
        brightness=0.99,
        unsharp_radius=1.10,
        unsharp_percent=50,
        unsharp_threshold=5,
    ),
}


def _target(slug: str, profile: str) -> RetouchTarget:
    return RetouchTarget(
        source=ROOT / "photosalon" / f"{slug}.jpg",
        output=ROOT / "photosalon" / "retouched" / f"{slug}.png",
        profile=profile,
    )


RETOUCHES = {
    slug: _target(slug, "salon")
    for slug in (
        "hero-salon",
        "salon-lounge",
        "salon-barbier",
        "salon-headspa",
        "cabine-headspa",
    )
}
RETOUCHES.update(
    {
        slug: _target(slug, "service")
        for slug in (
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
    }
)


def prepare_graded_source(
    source: Image.Image, profile_name: str = "salon"
) -> Image.Image:
    """Orient, gently smooth, and naturally grade a salon photograph."""
    profile = PROFILES[profile_name]
    original = ImageOps.exif_transpose(source).convert("RGB")
    median = original.filter(ImageFilter.MedianFilter(size=3))
    graded = Image.blend(original, median, profile.median_blend)
    graded = ImageEnhance.Color(graded).enhance(profile.color)
    graded = ImageEnhance.Contrast(graded).enhance(profile.contrast)
    return ImageEnhance.Brightness(graded).enhance(profile.brightness)


def render_master(source: Image.Image, profile_name: str = "salon") -> Image.Image:
    """Create the exact 2x salon master from an open source image."""
    graded = prepare_graded_source(source, profile_name)
    return render_graded_master(graded, profile_name)


def render_graded_master(
    graded: Image.Image, profile_name: str = "salon"
) -> Image.Image:
    profile = PROFILES[profile_name]
    master = graded.resize(
        (graded.width * 2, graded.height * 2),
        Image.Resampling.LANCZOS,
    )
    return master.filter(
        ImageFilter.UnsharpMask(
            radius=profile.unsharp_radius,
            percent=profile.unsharp_percent,
            threshold=profile.unsharp_threshold,
        )
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_chunk_types(path: Path) -> list[str]:
    chunks: list[str] = []
    with path.open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"{path}: invalid PNG signature")
        while True:
            length_bytes = stream.read(4)
            if not length_bytes:
                raise RuntimeError(f"{path}: missing PNG IEND chunk")
            length = struct.unpack(">I", length_bytes)[0]
            chunk_type_bytes = stream.read(4)
            if len(chunk_type_bytes) != 4:
                raise RuntimeError(f"{path}: truncated PNG chunk")
            chunk_type = chunk_type_bytes.decode("ascii")
            if len(stream.read(length + 4)) != length + 4:
                raise RuntimeError(f"{path}: truncated PNG chunk {chunk_type}")
            chunks.append(chunk_type)
            if chunk_type == "IEND":
                break
    return chunks


def mean_absolute_pixel_error(left: Image.Image, right: Image.Image) -> float:
    difference = ImageChops.difference(left, right)
    means = ImageStat.Stat(difference).mean
    return float(sum(means) / len(means))


def edge_energy_ratio(reference: Image.Image, candidate: Image.Image) -> float:
    reference_edges = reference.convert("L").filter(ImageFilter.FIND_EDGES)
    candidate_edges = candidate.convert("L").filter(ImageFilter.FIND_EDGES)
    reference_energy = float(ImageStat.Stat(reference_edges).mean[0])
    candidate_energy = float(ImageStat.Stat(candidate_edges).mean[0])
    if reference_energy == 0.0:
        return 1.0 if candidate_energy == 0.0 else float("inf")
    return candidate_energy / reference_energy


def validate_staged_output(
    slug: str,
    target: RetouchTarget,
    staged_path: Path,
    source_sha256: str,
    graded: Image.Image,
    rendered: Image.Image,
) -> ValidationResult:
    source_size = graded.size
    with Image.open(staged_path) as output:
        if output.format != "PNG":
            raise RuntimeError(f"{slug}: expected PNG, got {output.format!r}")
        if output.mode != "RGB":
            raise RuntimeError(f"{slug}: expected RGB, got {output.mode!r}")
        expected_size = (source_size[0] * 2, source_size[1] * 2)
        if output.size != expected_size:
            raise RuntimeError(f"{slug}: expected {expected_size}, got {output.size}")
        if output.info:
            raise RuntimeError(f"{slug}: output unexpectedly contains metadata: {output.info}")
        if output.getexif():
            raise RuntimeError(f"{slug}: output unexpectedly contains EXIF")
        output_size = output.size
        output.load()
        if ImageChops.difference(output, rendered).getbbox() is not None:
            raise RuntimeError(f"{slug}: saved PNG pixels differ from in-memory render")
        downscaled = output.resize(source_size, Image.Resampling.LANCZOS)

    chunks = png_chunk_types(staged_path)
    if not chunks or chunks[0] != "IHDR" or chunks[-1] != "IEND":
        raise RuntimeError(f"{slug}: invalid PNG chunk order: {chunks}")
    unexpected_chunks = sorted(set(chunks) - {"IHDR", "IDAT", "IEND"})
    if unexpected_chunks:
        raise RuntimeError(f"{slug}: unexpected PNG chunks: {unexpected_chunks}")

    normalized_error = mean_absolute_pixel_error(downscaled, graded)
    if normalized_error > 4.0:
        raise RuntimeError(
            f"{slug}: normalized mean absolute pixel error "
            f"{normalized_error:.4f} exceeds 4.0"
        )
    energy_ratio = edge_energy_ratio(graded, downscaled)
    if not 0.85 <= energy_ratio <= 1.25:
        raise RuntimeError(
            f"{slug}: edge-energy ratio {energy_ratio:.4f} is outside 0.85..1.25"
        )

    with Image.open(staged_path) as output:
        output.verify()

    return ValidationResult(
        slug=slug,
        source=target.source,
        output=target.output,
        source_sha256=source_sha256,
        source_size=source_size,
        output_size=output_size,
        normalized_mean_absolute_error=normalized_error,
        edge_energy_ratio=energy_ratio,
    )


def process_target(
    slug: str,
    target: RetouchTarget,
    staged_path: Path,
    source_sha256: str,
) -> ValidationResult:
    with Image.open(target.source) as source:
        graded = prepare_graded_source(source, target.profile)
    rendered = render_graded_master(graded, target.profile)
    rendered.info.clear()
    rendered.save(staged_path, format="PNG", optimize=True)
    report = validate_staged_output(
        slug,
        target,
        staged_path,
        source_sha256,
        graded,
        rendered,
    )
    if sha256_file(target.source) != source_sha256:
        raise RuntimeError(f"{slug}: source file changed during processing")
    return report


def load_hash_manifest() -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(HASHES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read photo hash manifest {HASHES_FILE}: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid photo hash manifest {HASHES_FILE}: expected object")
    for section in ("sources", "outputs"):
        if not isinstance(payload.get(section), dict):
            raise RuntimeError(
                f"Invalid photo hash manifest {HASHES_FILE}: missing {section!r} object"
            )
    return payload


def validate_source_hashes(
    selected: list[str], manifest: dict[str, dict[str, str]]
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for slug in selected:
        expected = manifest["sources"].get(slug)
        if not isinstance(expected, str):
            raise RuntimeError(f"{slug}: source SHA-256 is missing from {HASHES_FILE}")
        actual = sha256_file(RETOUCHES[slug].source)
        if actual != expected:
            raise RuntimeError(
                f"{slug}: source SHA-256 mismatch; expected {expected}, got {actual}"
            )
        hashes[slug] = actual
    return hashes


def validate_committed_output_hashes(
    selected: list[str],
    manifest: dict[str, dict[str, str]],
    paths: dict[str, Path] | None = None,
) -> None:
    for slug in selected:
        expected = manifest["outputs"].get(slug)
        if not isinstance(expected, str):
            raise RuntimeError(f"{slug}: output SHA-256 is missing from {HASHES_FILE}")
        output_path = RETOUCHES[slug].output if paths is None else paths[slug]
        actual = sha256_file(output_path)
        if actual != expected:
            raise RuntimeError(
                f"{slug}: committed output SHA-256 mismatch; "
                f"expected {expected}, got {actual}"
            )


def source_integrity_issues(before: dict[str, str]) -> list[Exception]:
    issues: list[Exception] = []
    for slug, expected in before.items():
        try:
            actual = sha256_file(RETOUCHES[slug].source)
        except Exception as error:
            issue = RuntimeError(f"{slug}: source re-hash failed: {error}")
            issue.__cause__ = error
            issues.append(issue)
            continue
        if actual != expected:
            issues.append(
                RuntimeError(
                    f"{slug}: source file changed; expected SHA-256 {expected}, got {actual}"
                )
            )
    return issues


def promote_staged_outputs(
    selected: list[str], staged: dict[str, Path], staging_directory: Path
) -> None:
    backups: dict[str, Path] = {}
    attempted: list[str] = []
    try:
        for slug in selected:
            destination = RETOUCHES[slug].output
            if destination.exists():
                backup = staging_directory / f"{slug}.{uuid.uuid4().hex}.backup"
                shutil.copy2(destination, backup)
                backups[slug] = backup

        for slug in selected:
            attempted.append(slug)
            os.replace(staged[slug], RETOUCHES[slug].output)
    except BaseException as primary_error:
        rollback_errors: list[BaseException] = []
        for slug in reversed(attempted):
            destination = RETOUCHES[slug].output
            try:
                backup = backups.get(slug)
                if backup is not None and backup.exists():
                    os.replace(backup, destination)
                elif backup is None and destination.exists():
                    destination.unlink()
            except BaseException as error:
                rollback_errors.append(error)
        if rollback_errors:
            recoverable_paths = [
                path
                for path in [*backups.values(), *staged.values()]
                if path.exists()
            ]
            recovery_error = BaseExceptionGroup(
                f"Photo promotion failed: {primary_error}; rollback also failed: "
                + "; ".join(str(error) for error in rollback_errors)
                + f"; preserved staging directory: {staging_directory}; "
                + "recoverable paths: "
                + ", ".join(str(path) for path in recoverable_paths),
                [primary_error, *rollback_errors],
            )
            recovery_error.preserve_staging = True
            raise recovery_error
        raise


def select_slugs(slugs: Iterable[str] | None) -> list[str]:
    selected = [] if slugs is None else list(slugs)
    if not selected:
        selected = list(RETOUCHES)
    seen: set[str] = set()
    duplicates: list[str] = []
    for slug in selected:
        if slug in seen and slug not in duplicates:
            duplicates.append(slug)
        seen.add(slug)
    if duplicates:
        raise ValueError(f"Duplicate slug(s): {', '.join(duplicates)}")
    unknown = [slug for slug in selected if slug not in RETOUCHES]
    if unknown:
        choices = ", ".join(RETOUCHES)
        raise ValueError(f"Unknown slug(s): {', '.join(unknown)}. Expected one of: {choices}")
    return selected


def build(
    slugs: Iterable[str] | None = None,
    *,
    verify_committed: bool = False,
) -> list[ValidationResult]:
    selected = select_slugs(slugs)
    manifest = load_hash_manifest()
    before = validate_source_hashes(selected, manifest)
    output_directories = {RETOUCHES[slug].output.parent for slug in selected}
    if len(output_directories) != 1:
        raise RuntimeError("All retouched outputs must share one staging filesystem")
    output_directory = output_directories.pop()
    output_directory.mkdir(parents=True, exist_ok=True)
    staging_directory = output_directory / f".staging-{os.getpid()}"
    staging_directory.mkdir(exist_ok=False)
    reports: list[ValidationResult] = []
    staged: dict[str, Path] = {}
    preserve_staging = False
    try:
        try:
            for slug in selected:
                staged_path = staging_directory / (
                    f"{slug}.{uuid.uuid4().hex}.candidate.png"
                )
                staged[slug] = staged_path
                reports.append(
                    process_target(slug, RETOUCHES[slug], staged_path, before[slug])
                )
            if verify_committed:
                validate_committed_output_hashes(selected, manifest, staged)
            promote_staged_outputs(selected, staged, staging_directory)
        except BaseException as primary_error:
            preserve_staging = bool(
                getattr(primary_error, "preserve_staging", False)
            )
            integrity_issues = source_integrity_issues(before)
            if integrity_issues:
                build_error = BaseExceptionGroup(
                    f"Photo build failed: {primary_error}; "
                    "source integrity recheck also failed: "
                    + "; ".join(str(error) for error in integrity_issues),
                    [primary_error, *integrity_issues],
                )
                build_error.preserve_staging = preserve_staging
                raise build_error
            raise
        integrity_issues = source_integrity_issues(before)
        if integrity_issues:
            if len(integrity_issues) == 1:
                raise integrity_issues[0]
            raise ExceptionGroup("Source integrity checks failed", integrity_issues)
    finally:
        if not preserve_staging:
            shutil.rmtree(staging_directory, ignore_errors=True)

    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic 2x premium salon photo masters."
    )
    parser.add_argument(
        "slugs",
        nargs="*",
        metavar="SLUG",
        help="optional salon or service photo slug; omit to build all fourteen",
    )
    parser.add_argument(
        "--verify-committed",
        action="store_true",
        help="require rebuilt output hashes to match photo-master-hashes.json",
    )
    args = parser.parse_args(argv)
    try:
        reports = build(args.slugs, verify_committed=args.verify_committed)
    except ValueError as error:
        parser.error(str(error))

    for report in reports:
        print(
            f"OK {report.slug}: {report.source_size[0]}x{report.source_size[1]} -> "
            f"{report.output_size[0]}x{report.output_size[1]} PNG RGB; "
            f"NMAE={report.normalized_mean_absolute_error:.4f}; "
            f"edge_ratio={report.edge_energy_ratio:.4f}; "
            f"source_sha256={report.source_sha256}"
        )
    if args.verify_committed:
        print("Committed output SHA-256 values verified.")
    print(f"Validated {len(reports)} master(s); source SHA-256 unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
