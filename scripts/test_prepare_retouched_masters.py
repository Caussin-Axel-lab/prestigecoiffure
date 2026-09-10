import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps


SCRIPT_PATH = Path(__file__).with_name("prepare-retouched-masters.py")


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_retouched_masters", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_chunks(path):
    chunks = []
    with path.open("rb") as stream:
        if stream.read(8) != b"\x89PNG\r\n\x1a\n":
            return chunks
        while True:
            length_bytes = stream.read(4)
            if not length_bytes:
                break
            length = struct.unpack(">I", length_bytes)[0]
            chunk_type = stream.read(4).decode("ascii")
            stream.seek(length + 4, 1)
            chunks.append(chunk_type)
            if chunk_type == "IEND":
                break
    return chunks


def make_fixture(path, seed):
    image = Image.new("RGB", (13, 9))
    image.putdata(
        [
            (
                (x * 19 + y * 7 + seed) % 256,
                (x * 5 + y * 23 + seed * 3) % 256,
                (x * 11 + y * 13 + seed * 5) % 256,
            )
            for y in range(image.height)
            for x in range(image.width)
        ]
    )
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "fixture metadata must not escape"
    image.save(path, format="JPEG", quality=92, exif=exif)


def render_expected_master(source, profile):
    graded = ImageOps.exif_transpose(source).convert("RGB")
    median = graded.filter(ImageFilter.MedianFilter(size=3))
    graded = Image.blend(graded, median, profile.median_blend)
    graded = ImageEnhance.Color(graded).enhance(profile.color)
    graded = ImageEnhance.Contrast(graded).enhance(profile.contrast)
    graded = ImageEnhance.Brightness(graded).enhance(profile.brightness)
    master = graded.resize(
        (graded.width * 2, graded.height * 2), Image.Resampling.LANCZOS
    )
    return master.filter(
        ImageFilter.UnsharpMask(
            radius=profile.unsharp_radius,
            percent=profile.unsharp_percent,
            threshold=profile.unsharp_threshold,
        )
    )


def write_hash_manifest(path, targets, output_hashes=None):
    payload = {
        "sources": {slug: sha256(target.source) for slug, target in targets.items()},
        "outputs": output_hashes or {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class PrepareRetouchedMastersTests(unittest.TestCase):
    def test_service_profile_constants_and_targets_are_locked(self):
        module = load_module()
        self.assertEqual(
            module.PROFILES["service"],
            module.RetouchProfile(
                median_blend=0.10,
                color=0.96,
                contrast=1.06,
                brightness=0.99,
                unsharp_radius=1.10,
                unsharp_percent=50,
                unsharp_threshold=5,
            ),
        )
        service_slugs = (
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
        for slug in service_slugs:
            target = module.RETOUCHES[slug]
            self.assertEqual(target.profile, "service")
            self.assertEqual(target.source, module.ROOT / "photosalon" / f"{slug}.jpg")
            self.assertEqual(
                target.output,
                module.ROOT / "photosalon" / "retouched" / f"{slug}.png",
            )

    def test_process_target_applies_service_profile_to_generated_fixture(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "service-fixture.jpg"
            staged = root / "service-fixture.candidate.png"
            make_fixture(source, seed=3)
            before = sha256(source)
            target = module.RetouchTarget(source, root / "service-fixture.png", "service")

            report = module.process_target("service-fixture", target, staged, before)

            with Image.open(source) as original:
                expected = render_expected_master(
                    original, module.PROFILES["service"]
                )
            with Image.open(staged) as output:
                output.load()
                self.assertIsNone(ImageChops.difference(output, expected).getbbox())
            self.assertEqual(sha256(source), before)
            self.assertLessEqual(report.normalized_mean_absolute_error, 4.0)
            self.assertGreaterEqual(report.edge_energy_ratio, 0.85)
            self.assertLessEqual(report.edge_energy_ratio, 1.25)

    def test_build_supports_mixed_salon_and_service_profiles(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            photos = root / "photosalon"
            outputs = photos / "retouched"
            outputs.mkdir(parents=True)
            targets = {}
            for index, (slug, profile) in enumerate(
                (("salon-fixture", "salon"), ("service-fixture", "service")),
                start=1,
            ):
                source = photos / f"{slug}.jpg"
                make_fixture(source, seed=index)
                targets[slug] = module.RetouchTarget(
                    source, outputs / f"{slug}.png", profile
                )
            manifest = root / "photo-master-hashes.json"
            write_hash_manifest(manifest, targets)

            with (
                mock.patch.object(module, "RETOUCHES", targets),
                mock.patch.object(module, "HASHES_FILE", manifest),
            ):
                reports = module.build(["salon-fixture", "service-fixture"])

            self.assertEqual([report.slug for report in reports], list(targets))
            for slug, target in targets.items():
                with Image.open(target.source) as source:
                    expected = render_expected_master(
                        source, module.PROFILES[target.profile]
                    )
                with Image.open(target.output) as output:
                    output.load()
                    self.assertIsNone(
                        ImageChops.difference(output, expected).getbbox()
                    )

    def test_python_311_or_newer_is_required(self):
        module = load_module()
        self.assertTrue(
            hasattr(module, "require_supported_python"),
            "missing explicit Python version guard",
        )
        with self.assertRaisesRegex(RuntimeError, "Python 3.11 or newer"):
            module.require_supported_python((3, 10))

    def test_process_target_writes_exact_validated_metadata_free_2x_png(self):
        module = load_module()
        self.assertTrue(hasattr(module, "process_target"), "missing staged processor")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fixture.jpg"
            staged = root / "fixture.candidate.png"
            make_fixture(source, seed=3)
            before = sha256(source)
            target = module.RetouchTarget(source, root / "fixture.png", "salon")

            report = module.process_target("fixture", target, staged, before)

            self.assertEqual(sha256(source), before)
            with Image.open(source) as original:
                oriented_size = ImageOps.exif_transpose(original).size
                expected = module.render_master(original)
            with Image.open(staged) as output:
                self.assertEqual(output.format, "PNG")
                self.assertEqual(output.mode, "RGB")
                self.assertEqual(output.size, (oriented_size[0] * 2, oriented_size[1] * 2))
                self.assertEqual(output.info, {})
                self.assertFalse(output.getexif())
                output.load()
                self.assertIsNone(ImageChops.difference(output, expected).getbbox())
            chunks = png_chunks(staged)
            self.assertEqual(chunks[0], "IHDR")
            self.assertEqual(chunks[-1], "IEND")
            self.assertTrue(set(chunks) <= {"IHDR", "IDAT", "IEND"})
            self.assertLessEqual(report.normalized_mean_absolute_error, 4.0)
            self.assertGreaterEqual(report.edge_energy_ratio, 0.85)
            self.assertLessEqual(report.edge_energy_ratio, 1.25)

    def test_batch_rolls_back_every_destination_when_second_promotion_fails(self):
        module = load_module()
        self.assertTrue(hasattr(module, "HASHES_FILE"), "missing committed hash manifest")
        self.assertTrue(hasattr(module, "os"), "missing transactional promotion")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            photos = root / "photosalon"
            outputs = photos / "retouched"
            outputs.mkdir(parents=True)
            targets = {}
            previous = {}
            for index, slug in enumerate(("first", "second"), start=1):
                source = photos / f"{slug}.jpg"
                destination = outputs / f"{slug}.png"
                make_fixture(source, seed=index)
                destination.write_bytes(f"previous-{slug}".encode("ascii"))
                previous[slug] = destination.read_bytes()
                targets[slug] = module.RetouchTarget(source, destination, "salon")
            manifest = root / "photo-master-hashes.json"
            write_hash_manifest(manifest, targets)
            original_replace = os.replace
            promotion_count = 0
            all_destinations_live_at_first_promotion = False

            def fail_second_promotion(source, destination):
                nonlocal promotion_count, all_destinations_live_at_first_promotion
                source_path = Path(source)
                if source_path.name.endswith(".candidate.png"):
                    promotion_count += 1
                    if promotion_count == 1:
                        all_destinations_live_at_first_promotion = all(
                            target.output.exists() for target in targets.values()
                        )
                    if promotion_count == 2:
                        raise OSError("forced second promotion failure")
                return original_replace(source, destination)

            with (
                mock.patch.object(module, "RETOUCHES", targets),
                mock.patch.object(module, "HASHES_FILE", manifest),
                mock.patch.object(module.os, "replace", side_effect=fail_second_promotion),
            ):
                with self.assertRaisesRegex(OSError, "forced second promotion failure"):
                    module.build(["first", "second"])

            for slug, target in targets.items():
                self.assertEqual(target.output.read_bytes(), previous[slug])
            self.assertTrue(all_destinations_live_at_first_promotion)
            self.assertEqual(list(outputs.glob(".staging-*")), [])

    def test_restore_failure_preserves_recoverable_backup_and_staging_path(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            photos = root / "photosalon"
            outputs = photos / "retouched"
            outputs.mkdir(parents=True)
            targets = {}
            for index, slug in enumerate(("first", "second"), start=21):
                source = photos / f"{slug}.jpg"
                destination = outputs / f"{slug}.png"
                make_fixture(source, seed=index)
                destination.write_bytes(f"previous-{slug}".encode("ascii"))
                targets[slug] = module.RetouchTarget(source, destination, "salon")
            manifest = root / "photo-master-hashes.json"
            write_hash_manifest(manifest, targets)
            original_replace = os.replace
            promotion_count = 0

            def fail_promotion_then_restore(source, destination):
                nonlocal promotion_count
                source_path = Path(source)
                destination_path = Path(destination)
                if source_path.name.endswith(".candidate.png"):
                    promotion_count += 1
                    if promotion_count == 2:
                        raise OSError("forced second promotion failure")
                if (
                    source_path.name.endswith(".backup")
                    and destination_path == targets["first"].output
                ):
                    raise OSError("forced first restore failure")
                return original_replace(source, destination)

            with (
                mock.patch.object(module, "RETOUCHES", targets),
                mock.patch.object(module, "HASHES_FILE", manifest),
                mock.patch.object(
                    module.os, "replace", side_effect=fail_promotion_then_restore
                ),
            ):
                with self.assertRaises(BaseExceptionGroup) as caught:
                    module.build(["first", "second"])

            staging_directories = list(outputs.glob(".staging-*"))
            self.assertEqual(len(staging_directories), 1)
            backups = list(staging_directories[0].glob("first.*.backup"))
            self.assertEqual(len(backups), 1)
            message = str(caught.exception)
            self.assertIn(str(staging_directories[0]), message)
            self.assertIn(str(backups[0]), message)

    def test_committed_output_hash_mismatch_is_rejected(self):
        module = load_module()
        self.assertTrue(
            hasattr(module, "validate_committed_output_hashes"),
            "missing committed output verifier",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fixture.jpg"
            output = root / "fixture.png"
            manifest_path = root / "photo-master-hashes.json"
            make_fixture(source, seed=7)
            output.write_bytes(b"not-the-committed-output")
            previous = output.read_bytes()
            targets = {"fixture": module.RetouchTarget(source, output, "salon")}
            write_hash_manifest(manifest_path, targets, {"fixture": "0" * 64})
            with (
                mock.patch.object(module, "RETOUCHES", targets),
                mock.patch.object(module, "HASHES_FILE", manifest_path),
            ):
                manifest = module.load_hash_manifest()
                with self.assertRaisesRegex(
                    RuntimeError, "committed output SHA-256 mismatch"
                ):
                    module.validate_committed_output_hashes(["fixture"], manifest)
                with self.assertRaisesRegex(
                    RuntimeError, "committed output SHA-256 mismatch"
                ):
                    module.build(["fixture"], verify_committed=True)
            self.assertEqual(output.read_bytes(), previous)
            self.assertEqual(list(root.glob(".staging-*")), [])

    def test_primary_failure_and_source_rehash_failure_are_both_reported(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fixture.jpg"
            output = root / "retouched" / "fixture.png"
            manifest_path = root / "photo-master-hashes.json"
            make_fixture(source, seed=11)
            source_hash = sha256(source)
            targets = {"fixture": module.RetouchTarget(source, output, "salon")}
            write_hash_manifest(manifest_path, targets)

            with (
                mock.patch.object(module, "RETOUCHES", targets),
                mock.patch.object(module, "HASHES_FILE", manifest_path),
                mock.patch.object(
                    module,
                    "sha256_file",
                    side_effect=[source_hash, OSError("rehash unavailable")],
                ),
                mock.patch.object(
                    module,
                    "process_target",
                    side_effect=ValueError("primary processing failure"),
                ),
            ):
                with self.assertRaises(BaseExceptionGroup) as caught:
                    module.build(["fixture"])

            message = str(caught.exception)
            self.assertIn("primary processing failure", message)
            self.assertIn("rehash unavailable", message)
            self.assertEqual(list(output.parent.glob(".staging-*")), [])

    def test_unknown_slug_cli_exits_two_with_clear_error(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "unknown-fixture"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown slug(s): unknown-fixture", result.stderr)

    def test_duplicate_slugs_are_rejected(self):
        module = load_module()
        with self.assertRaisesRegex(ValueError, "Duplicate slug.*hero-salon"):
            module.select_slugs(["hero-salon", "hero-salon"])
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "hero-salon", "hero-salon"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Duplicate slug(s): hero-salon", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
