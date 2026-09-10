import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw, PngImagePlugin


SCRIPT = Path(__file__).with_name("build-photo-derivatives.py")


def load_builder():
    spec = importlib.util.spec_from_file_location("build_photo_derivatives", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = load_builder()


class PhotoDerivativeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        (self.root / "photosalon" / "retouched").mkdir(parents=True)
        source = Image.new("RGB", (400, 200), "black")
        draw = ImageDraw.Draw(source)
        draw.rectangle((0, 0, 99, 199), fill="red")
        draw.rectangle((100, 0, 299, 199), fill="green")
        draw.rectangle((300, 0, 399, 199), fill="blue")
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("comment", "must not survive")
        source.save(
            self.root / "photosalon" / "retouched" / "sample-role.png",
            pnginfo=metadata,
        )
        self.manifest_path = self.root / "scripts" / "photo-manifest.json"
        self.write_manifest(self.valid_manifest())

    def tearDown(self):
        self.temporary.cleanup()

    def valid_manifest(self):
        return {
            "sample-role": {
                "input": "photosalon/retouched/sample-role.png",
                "variants": {
                    "desktop": {
                        "width": 100,
                        "height": 100,
                        "focalX": 0.5,
                        "focalY": 0.5,
                    },
                    "mobile": {
                        "width": 80,
                        "height": 120,
                        "focalX": 0.0,
                        "focalY": 0.5,
                    },
                },
            }
        }

    def write_manifest(self, payload):
        self.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def test_crop_box_centers_and_clamps_focal_point(self):
        self.assertEqual(builder.crop_box((400, 200), (100, 100), 0.5, 0.5), (100, 0, 300, 200))
        self.assertEqual(builder.crop_box((400, 200), (100, 100), 0.0, 0.5), (0, 0, 200, 200))
        self.assertEqual(builder.crop_box((400, 200), (100, 100), 1.0, 0.5), (200, 0, 400, 200))

    def test_manifest_validation_rejects_invalid_shapes_and_paths(self):
        cases = {}

        payload = self.valid_manifest()
        payload["Bad_Slug"] = payload.pop("sample-role")
        cases["unsafe slug"] = payload

        payload = self.valid_manifest()
        payload["sample-role"]["input"] = "../outside.png"
        cases["escaping input"] = payload

        payload = self.valid_manifest()
        payload["sample-role"]["input"] = "photosalon/retouched/missing.png"
        cases["missing input"] = payload

        payload = self.valid_manifest()
        payload["sample-role"]["variants"].pop("mobile")
        cases["missing variant"] = payload

        payload = self.valid_manifest()
        payload["sample-role"]["variants"]["tablet"] = payload["sample-role"]["variants"]["desktop"]
        cases["extra variant"] = payload

        for bad_value in (0, -1, 1.5, True, "100"):
            payload = self.valid_manifest()
            payload["sample-role"]["variants"]["desktop"]["width"] = bad_value
            cases[f"bad dimension {bad_value!r}"] = payload

        for bad_value in (-0.1, 1.1, True, "0.5", None):
            payload = self.valid_manifest()
            payload["sample-role"]["variants"]["desktop"]["focalX"] = bad_value
            cases[f"bad focal {bad_value!r}"] = payload

        for label, payload in cases.items():
            with self.subTest(label=label):
                self.write_manifest(payload)
                with self.assertRaises(builder.ManifestError):
                    builder.load_manifest(self.manifest_path, self.root)

    def test_one_role_builds_four_clean_progressive_outputs(self):
        reports = builder.build([], manifest_path=self.manifest_path, root=self.root)
        outputs = sorted((self.root / "photosalon" / "web").iterdir())
        self.assertEqual(len(reports), 4)
        self.assertTrue(all(report.path.parent == outputs[0].parent for report in reports))
        self.assertEqual(
            [path.name for path in outputs],
            [
                "sample-role-desktop.jpg",
                "sample-role-desktop.webp",
                "sample-role-mobile.jpg",
                "sample-role-mobile.webp",
            ],
        )
        expected = {
            "sample-role-desktop.jpg": ("JPEG", (100, 100)),
            "sample-role-desktop.webp": ("WEBP", (100, 100)),
            "sample-role-mobile.jpg": ("JPEG", (80, 120)),
            "sample-role-mobile.webp": ("WEBP", (80, 120)),
        }
        for output in outputs:
            self.assertGreater(output.stat().st_size, 0)
            self.assertLessEqual(output.stat().st_size, 900 * 1024)
            with Image.open(output) as image:
                self.assertEqual((image.format, image.size), expected[output.name])
                self.assertEqual(image.mode, "RGB")
                self.assertFalse(image.getexif())
                self.assertNotIn("icc_profile", image.info)
                self.assertNotIn("xmp", image.info)
                self.assertNotIn("comment", image.info)
                if image.format == "JPEG":
                    self.assertEqual(image.info.get("progressive"), 1)

    def test_verify_checks_existing_outputs_without_rebuilding(self):
        builder.build([], manifest_path=self.manifest_path, root=self.root)
        output = self.root / "photosalon" / "web" / "sample-role-desktop.jpg"
        before = output.read_bytes()
        reports = builder.build(
            ["sample-role"],
            verify=True,
            manifest_path=self.manifest_path,
            root=self.root,
        )
        self.assertEqual(len(reports), 4)
        self.assertEqual(output.read_bytes(), before)
        output.write_bytes(b"broken")
        with self.assertRaises(builder.OutputValidationError):
            builder.build(
                ["sample-role"],
                verify=True,
                manifest_path=self.manifest_path,
                root=self.root,
            )

    def test_cli_duplicate_and_unknown_slugs_exit_two(self):
        for slugs, phrase in (
            (["sample-role", "sample-role"], "Duplicate"),
            (["unknown-role"], "Unknown"),
        ):
            with self.subTest(slugs=slugs):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT), *slugs],
                    cwd=SCRIPT.parent.parent,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 2)
                self.assertIn(phrase, completed.stderr)

    def test_promotion_failure_rolls_back_every_destination(self):
        builder.build([], manifest_path=self.manifest_path, root=self.root)
        output_dir = self.root / "photosalon" / "web"
        originals = {path.name: path.read_bytes() for path in output_dir.iterdir()}
        real_replace = os.replace

        def fail_second_candidate(source, destination):
            source = Path(source)
            destination = Path(destination)
            if source.name == destination.name == "sample-role-desktop.webp":
                raise OSError("injected promotion failure")
            return real_replace(source, destination)

        with mock.patch.object(builder.os, "replace", side_effect=fail_second_candidate):
            with self.assertRaises(OSError):
                builder.build([], manifest_path=self.manifest_path, root=self.root)

        self.assertEqual(
            {path.name: path.read_bytes() for path in output_dir.iterdir()}, originals
        )
        self.assertFalse(list(output_dir.glob(".staging-*")))

    def test_restore_failure_preserves_staging_and_backups(self):
        builder.build([], manifest_path=self.manifest_path, root=self.root)
        output_dir = self.root / "photosalon" / "web"
        real_replace = os.replace

        def fail_promotion_and_restore(source, destination):
            source = Path(source)
            destination = Path(destination)
            if source.name == destination.name == "sample-role-desktop.webp":
                raise OSError("injected promotion failure")
            if source.name.endswith(".backup") and destination.name == "sample-role-desktop.jpg":
                raise OSError("injected restore failure")
            return real_replace(source, destination)

        with mock.patch.object(builder.os, "replace", side_effect=fail_promotion_and_restore):
            with self.assertRaises(BaseExceptionGroup) as raised:
                builder.build([], manifest_path=self.manifest_path, root=self.root)

        self.assertTrue(getattr(raised.exception, "preserve_staging", False))
        staging = list(output_dir.glob(".staging-*"))
        self.assertEqual(len(staging), 1)
        self.assertIn(str(staging[0]), str(raised.exception))
        self.assertTrue(list(staging[0].glob("*.backup")))


if __name__ == "__main__":
    unittest.main()
