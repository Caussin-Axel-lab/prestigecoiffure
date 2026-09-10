import hashlib
import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw, PngImagePlugin


SCRIPT = Path(__file__).with_name("build-og-image.py")


def load_builder():
    spec = importlib.util.spec_from_file_location("build_og_image", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = load_builder()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_png_header(path, width, height):
    def chunk(kind, payload):
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")
    )


class OgImageBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "hero.png"
        self.logo = self.root / "logo.png"
        self.output = self.root / "og-image.jpg"

        source = Image.new("RGB", (800, 1000))
        draw = ImageDraw.Draw(source)
        for y in range(source.height):
            draw.line(
                (0, y, source.width, y),
                fill=(35 + y // 15, 45 + y // 18, 38 + y // 22),
            )
        draw.rectangle((60, 260, 360, 760), fill=(45, 95, 62))
        draw.ellipse((170, 350, 550, 730), fill=(190, 145, 105))
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("comment", "source metadata must not survive")
        source.save(self.source, pnginfo=metadata)

        logo = Image.new("RGBA", (400, 140), (0, 0, 0, 0))
        logo_draw = ImageDraw.Draw(logo)
        logo_draw.rectangle((20, 18, 379, 64), fill=(0, 0, 0, 255))
        for x in range(45, 356, 42):
            logo_draw.rectangle((x, 92, x + 18, 119), fill=(0, 0, 0, 220))
        logo.save(self.logo)

    def tearDown(self):
        self.temporary.cleanup()

    def build(self, output=None):
        return builder.build_og_image(
            source_path=self.source,
            logo_path=self.logo,
            output_path=output or self.output,
        )

    def test_default_paths_are_relative_to_repository_root(self):
        root = self.root / "repo"
        self.assertEqual(
            builder.default_paths(root),
            (
                root / "photosalon" / "retouched" / "hero-salon.png",
                root / "assets" / "logo.png",
                root / "assets" / "og-image.jpg",
            ),
        )

    def test_output_is_clean_progressive_rgb_jpeg_at_social_dimensions(self):
        result = self.build()

        self.assertEqual(result, self.output)
        self.assertGreater(self.output.stat().st_size, 0)
        self.assertLess(self.output.stat().st_size, 900 * 1024)
        with Image.open(self.output) as image:
            image.load()
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (1200, 630))
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.info.get("progressive"), 1)
            self.assertFalse(image.getexif())
            for key in ("icc_profile", "exif", "xmp", "comment", "photoshop"):
                self.assertNotIn(key, image.info)

    def test_build_is_deterministic_and_does_not_modify_inputs(self):
        source_before = digest(self.source)
        logo_before = digest(self.logo)

        self.build()
        first_output = digest(self.output)
        self.build()

        self.assertEqual(digest(self.output), first_output)
        self.assertEqual(digest(self.source), source_before)
        self.assertEqual(digest(self.logo), logo_before)

    def test_source_pixels_affect_output(self):
        self.build()
        before = digest(self.output)
        with Image.open(self.source) as image:
            changed = image.copy()
        ImageDraw.Draw(changed).rectangle((250, 300, 650, 700), fill="magenta")
        changed.save(self.source)

        self.build()

        self.assertNotEqual(digest(self.output), before)

    def test_logo_alpha_affects_output(self):
        self.build()
        before = digest(self.output)
        with Image.open(self.logo) as image:
            changed = image.copy()
        ImageDraw.Draw(changed).ellipse((120, 20, 300, 125), fill=(0, 0, 0, 255))
        changed.save(self.logo)

        self.build()

        self.assertNotEqual(digest(self.output), before)

    def test_invalid_input_does_not_corrupt_existing_output(self):
        sentinel = b"keep this existing image"
        self.output.write_bytes(sentinel)
        self.logo.write_bytes(b"not an image")

        with self.assertRaisesRegex(builder.InputImageError, "logo"):
            self.build()

        self.assertEqual(self.output.read_bytes(), sentinel)
        self.assertFalse(list(self.root.glob(".og-image-*")))

    def test_output_cannot_alias_source_or_logo(self):
        for label, aliased_output in (("source", self.source), ("logo", self.logo)):
            with self.subTest(label=label):
                source_before = digest(self.source)
                logo_before = digest(self.logo)

                with self.assertRaisesRegex(builder.InputImageError, label):
                    self.build(output=aliased_output)

                self.assertEqual(digest(self.source), source_before)
                self.assertEqual(digest(self.logo), logo_before)

    def test_relative_output_alias_is_rejected_before_inputs_are_opened(self):
        relative_alias = Path(os.path.relpath(self.source, Path.cwd()))
        self.assertFalse(relative_alias.is_absolute())
        source_before = digest(self.source)

        with mock.patch.object(
            builder.Image,
            "open",
            side_effect=AssertionError("input was opened before alias validation"),
        ):
            with self.assertRaisesRegex(builder.InputImageError, "source"):
                self.build(output=relative_alias)

        self.assertEqual(digest(self.source), source_before)

    def test_hardlink_output_alias_is_rejected(self):
        hardlink = self.root / "hero-hardlink.jpg"
        try:
            os.link(self.source, hardlink)
        except OSError as exc:
            self.skipTest(f"hardlinks unavailable: {exc}")
        source_before = digest(self.source)

        with self.assertRaisesRegex(builder.InputImageError, "source"):
            self.build(output=hardlink)

        self.assertEqual(digest(self.source), source_before)

    def test_alias_identity_check_failure_fails_closed(self):
        sentinel = b"existing destination"
        self.output.write_bytes(sentinel)

        with mock.patch.object(
            builder.os.path,
            "samefile",
            side_effect=OSError("identity check denied"),
        ):
            with self.assertRaisesRegex(builder.InputImageError, "identity check denied"):
                self.build()

        self.assertEqual(self.output.read_bytes(), sentinel)

    def test_exif_orientation_is_applied_before_cropping(self):
        oriented = self.root / "oriented.jpg"
        physical = self.root / "physically-oriented.png"
        oriented_output = self.root / "oriented-output.jpg"
        physical_output = self.root / "physical-output.jpg"
        pixels = Image.new("RGB", (900, 500), "black")
        pixels_draw = ImageDraw.Draw(pixels)
        pixels_draw.rectangle((0, 0, 449, 249), fill="red")
        pixels_draw.rectangle((450, 0, 899, 249), fill="green")
        pixels_draw.rectangle((0, 250, 449, 499), fill="blue")
        pixels_draw.rectangle((450, 250, 899, 499), fill="yellow")
        exif = Image.Exif()
        exif[274] = 6
        pixels.save(oriented, quality=100, subsampling=0, exif=exif)
        with Image.open(oriented) as encoded:
            encoded.load()
            transposed = encoded.transpose(Image.Transpose.ROTATE_270).convert("RGB")
        transposed.info.clear()
        transposed.save(physical)

        builder.build_og_image(
            source_path=oriented,
            logo_path=self.logo,
            output_path=oriented_output,
        )
        builder.build_og_image(
            source_path=physical,
            logo_path=self.logo,
            output_path=physical_output,
        )

        self.assertEqual(oriented_output.read_bytes(), physical_output.read_bytes())
        with Image.open(oriented_output) as result:
            self.assertFalse(result.getexif())
            self.assertNotIn("icc_profile", result.info)

    def test_application_pixel_limit_is_checked_before_decode(self):
        oversized = self.root / "oversized.png"
        write_png_header(oversized, 8_000, 8_000)

        with self.assertRaisesRegex(builder.InputImageError, "source.*pixel limit"):
            builder.build_og_image(
                source_path=oversized,
                logo_path=self.logo,
                output_path=self.output,
            )

        self.assertFalse(self.output.exists())

    def test_pillow_decompression_bomb_is_reported_as_input_error(self):
        bomb = self.root / "bomb.png"
        write_png_header(bomb, 20_000, 20_000)

        with self.assertRaisesRegex(builder.InputImageError, "source.*decompression bomb"):
            builder.build_og_image(
                source_path=bomb,
                logo_path=self.logo,
                output_path=self.output,
            )

        self.assertFalse(self.output.exists())

    def test_pathological_logo_bounds_are_rejected_before_large_resize(self):
        narrow_logo = Image.new("RGBA", (4, 40), (0, 0, 0, 255))
        narrow_logo.save(self.logo)

        with self.assertRaisesRegex(builder.InputImageError, "logo.*dimensions"):
            self.build()

        self.assertFalse(self.output.exists())

    def test_replace_failure_is_wrapped_and_preserves_existing_output(self):
        sentinel = b"existing output"
        self.output.write_bytes(sentinel)

        with mock.patch.object(builder.os, "replace", side_effect=OSError("locked")):
            with self.assertRaisesRegex(builder.OutputImageError, "locked"):
                self.build()

        self.assertEqual(self.output.read_bytes(), sentinel)
        self.assertFalse(list(self.root.glob(".og-image-*")))

    def test_output_directory_failure_is_wrapped(self):
        with mock.patch.object(Path, "mkdir", side_effect=OSError("mkdir denied")):
            with self.assertRaisesRegex(builder.OutputImageError, "mkdir denied"):
                self.build()

        self.assertFalse(self.output.exists())

    def test_encode_failure_is_wrapped_and_temporary_file_is_cleaned(self):
        with mock.patch.object(
            builder,
            "_save_clean_jpeg",
            side_effect=OSError("encode failed"),
        ):
            with self.assertRaisesRegex(builder.OutputImageError, "encode failed"):
                self.build()

        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".og-image-*")))

    def test_fsync_failure_is_wrapped_and_temporary_file_is_cleaned(self):
        with mock.patch.object(builder.os, "fsync", side_effect=OSError("sync failed")):
            with self.assertRaisesRegex(builder.OutputImageError, "sync failed"):
                self.build()

        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".og-image-*")))

    def test_cleanup_failure_does_not_mask_primary_error(self):
        with mock.patch.object(
            builder.os,
            "replace",
            side_effect=OSError("promotion blocked"),
        ), mock.patch.object(
            Path,
            "unlink",
            side_effect=PermissionError("cleanup blocked"),
        ):
            with self.assertRaises(builder.OutputImageError) as caught:
                self.build()

        message = str(caught.exception)
        self.assertIn("promotion blocked", message)
        self.assertIn("cleanup blocked", message)
        retained = list(self.root.glob(".og-image-*"))
        self.assertEqual(len(retained), 1)
        retained[0].unlink()

    def test_committed_asset_matches_a_fresh_build(self):
        root = SCRIPT.parent.parent
        source, logo, committed = builder.default_paths(root)
        rebuilt = self.root / "rebuilt.jpg"

        builder.build_og_image(
            source_path=source,
            logo_path=logo,
            output_path=rebuilt,
        )

        self.assertTrue(committed.is_file())
        self.assertEqual(rebuilt.read_bytes(), committed.read_bytes())

    def test_cli_accepts_explicit_paths(self):
        cli_output = self.root / "from-cli.jpg"
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source",
                str(self.source),
                "--logo",
                str(self.logo),
                "--output",
                str(cli_output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(cli_output.is_file())
        self.assertIn("1200x630", process.stdout)

    def test_cli_rejects_output_alias_without_traceback(self):
        source_before = digest(self.source)
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source",
                str(self.source),
                "--logo",
                str(self.logo),
                "--output",
                str(self.source),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(process.returncode, 0)
        self.assertIn("source", process.stderr)
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(digest(self.source), source_before)


if __name__ == "__main__":
    unittest.main()
