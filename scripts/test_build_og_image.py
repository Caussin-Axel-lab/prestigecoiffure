import hashlib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
