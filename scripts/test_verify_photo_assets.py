import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).with_name("verify-photo-assets.py")


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_photo_assets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = load_verifier()


ROLE_SLUGS = (
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

LOCAL_SERVICES = (
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


def picture_markup(slug, prefix="", *, below_fold=False):
    loading = ' loading="lazy" decoding="async"' if below_fold else ' loading="eager" fetchpriority="high"'
    return f"""
      <picture>
        <source media="(max-width: 720px)" type="image/webp" srcset="{prefix}photosalon/web/{slug}-mobile.webp">
        <source media="(max-width: 720px)" type="image/jpeg" srcset="{prefix}photosalon/web/{slug}-mobile.jpg">
        <source type="image/webp" srcset="{prefix}photosalon/web/{slug}-desktop.webp">
        <img src="{prefix}photosalon/web/{slug}-desktop.jpg" width="4" height="4" alt="Description utile"{loading}>
      </picture>
    """


def write_exif_jpeg(path):
    exif = Image.Exif()
    exif[274] = 1
    Image.new("RGB", (1200, 630)).save(path, format="JPEG", exif=exif)


class RepositoryFixture:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "scripts").mkdir()
        (self.root / "services").mkdir()
        (self.root / "photosalon" / "web").mkdir(parents=True)
        (self.root / "assets").mkdir()
        self.write_manifest()
        self.write_derivatives()
        self.write_html()
        self.write_og()
        self.write_builder()
        self.write_service_worker()

    def write_manifest(self):
        manifest = {
            slug: {
                "input": f"photosalon/retouched/{slug}.png",
                "variants": {
                    "desktop": {"width": 4, "height": 4, "focalX": 0.5, "focalY": 0.5},
                    "mobile": {"width": 4, "height": 4, "focalX": 0.5, "focalY": 0.5},
                },
            }
            for slug in ROLE_SLUGS
        }
        (self.root / "scripts" / "photo-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def write_derivatives(self):
        output = self.root / "photosalon" / "web"
        for slug in ROLE_SLUGS:
            for variant in ("desktop", "mobile"):
                for extension, image_format in (("jpg", "JPEG"), ("webp", "WEBP")):
                    Image.new("RGB", (4, 4), "tan").save(
                        output / f"{slug}-{variant}.{extension}", format=image_format
                    )

    def write_html(self):
        index_roles = ROLE_SLUGS[:5]
        index = ["<!doctype html><html><body>"]
        for position, slug in enumerate(index_roles):
            index.append(picture_markup(slug, below_fold=position > 0))
        index.append("</body></html>")
        (self.root / "index.html").write_text("".join(index), encoding="utf-8")

        for service in LOCAL_SERVICES:
            body = picture_markup(f"service-{service}", prefix="../")
            (self.root / "services" / f"{service}.html").write_text(
                f'<!doctype html><figure class="service-hero-image service-hero-image--cinematic">{body}</figure>',
                encoding="utf-8",
            )
        (self.root / "services" / "coupes-enfant.html").write_text(
            '<!doctype html><figure class="service-hero-image service-hero-image--cinematic service-hero-image--temporary">'
            '<img src="https://images.example/kid.jpg" alt="Coupe enfant" loading="eager" fetchpriority="high">'
            "</figure>",
            encoding="utf-8",
        )
        (self.root / "services" / "lissage-ybera.html").write_text(
            '<!doctype html><img src="https://images.example/retired.jpg" alt="Retiré">',
            encoding="utf-8",
        )

    def write_og(self, **save_options):
        Image.new("RGB", (1200, 630), "black").save(
            self.root / "assets" / "og-image.jpg", format="JPEG", **save_options
        )

    def write_builder(self, *, exit_code=0, message="Verified 56 derivative(s)."):
        (self.root / "scripts" / "build-photo-derivatives.py").write_text(
            "import pathlib, sys\n"
            "if '--verify' not in sys.argv or pathlib.Path.cwd() != pathlib.Path(__file__).resolve().parent.parent:\n"
            "    print('wrong invocation', file=sys.stderr); raise SystemExit(9)\n"
            f"print({message!r}, file=sys.stderr if {exit_code} else sys.stdout)\n"
            f"raise SystemExit({exit_code})\n",
            encoding="utf-8",
        )

    def write_service_worker(self, precache="'/assets/og-image.jpg'"):
        (self.root / "sw.js").write_text(
            "const CACHE_VERSION = 'v1.2.0';\n"
            "const CACHE_NAME = 'prestige-' + CACHE_VERSION;\n"
            f"const PRECACHE_URLS = [{precache}];\n",
            encoding="utf-8",
        )


class PhotoAssetVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = RepositoryFixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def errors(self):
        return verifier.audit_repository(self.root)

    def test_srcset_parser_supports_candidates_descriptors_and_data_urls(self):
        self.assertEqual(
            verifier.parse_srcset(
                "photos/a.jpg 480w, photos/a@2x.jpg 2x, data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA== 1x"
            ),
            [
                "photos/a.jpg",
                "photos/a@2x.jpg",
                "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==",
            ],
        )

    def test_valid_repository_and_cli_report_concise_scope_counts(self):
        self.assertEqual(self.errors(), [])
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout.strip(),
            "OK: 56 derivatives, 12 HTML files, 11 active.",
        )
        self.assertEqual(completed.stderr, "")

    def test_missing_and_extra_derivative_entries_are_both_reported(self):
        missing = self.root / "photosalon" / "web" / "hero-salon-mobile.webp"
        missing.unlink()
        (self.root / "photosalon" / "web" / "unexpected").mkdir()

        errors = "\n".join(self.errors())

        self.assertIn("photosalon/web/hero-salon-mobile.webp: missing", errors)
        self.assertIn("photosalon/web/unexpected: unexpected", errors)

    def test_local_src_and_srcset_references_are_resolved_per_html_file(self):
        service = self.root / "services" / "lissage-ybera.html"
        service.write_text(
            '<img src="../assets/missing.jpg">'
            '<source srcset="../assets/also-missing.webp 1x, https://example.test/remote.webp 2x, data:image/gif;base64,AAAA 3x">',
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("services/lissage-ybera.html: missing local reference assets/missing.jpg", errors)
        self.assertIn("services/lissage-ybera.html: missing local reference assets/also-missing.webp", errors)
        self.assertNotIn("example.test", errors)
        self.assertNotIn("base64", errors)

    def test_invalid_derivative_decode_is_reported_without_stopping_other_checks(self):
        target = self.root / "photosalon" / "web" / "hero-salon-desktop.jpg"
        target.write_bytes(b"not an image")
        (self.root / "assets" / "og-image.jpg").unlink()

        errors = "\n".join(self.errors())

        self.assertIn("photosalon/web/hero-salon-desktop.jpg: invalid image", errors)
        self.assertIn("assets/og-image.jpg: missing", errors)

    def test_derivative_dimensions_format_mode_and_size_are_enforced(self):
        cases = (
            ("dimensions", lambda path: Image.new("RGB", (5, 4)).save(path, format="JPEG"), "expected 4x4"),
            ("format", lambda path: Image.new("RGB", (4, 4)).save(path, format="WEBP"), "expected JPEG"),
            ("mode", lambda path: Image.new("L", (4, 4)).save(path, format="JPEG"), "expected RGB"),
            ("size", lambda path: path.write_bytes(path.read_bytes() + b"x" * 900_001), "exceeds 900000 bytes"),
        )
        target = self.root / "photosalon" / "web" / "hero-salon-desktop.jpg"
        original = target.read_bytes()
        for label, mutate, expected in cases:
            with self.subTest(label=label):
                target.write_bytes(original)
                mutate(target)
                self.assertIn(expected, "\n".join(self.errors()))

    def test_stale_builder_failure_is_aggregated_and_repo_relative(self):
        self.fixture.write_builder(exit_code=1, message=str(self.root / "photosalon" / "web" / "hero-salon-desktop.jpg") + ": stale derivative")

        errors = "\n".join(self.errors())

        self.assertIn("build-photo-derivatives.py --verify", errors)
        self.assertIn("photosalon/web/hero-salon-desktop.jpg: stale derivative", errors)
        self.assertNotIn(str(self.root), errors)

    def test_og_contract_rejects_dimensions_mode_and_metadata(self):
        og = self.root / "assets" / "og-image.jpg"
        cases = (
            ("dimensions", lambda: Image.new("RGB", (1199, 630)).save(og, format="JPEG"), "1200x630"),
            ("mode", lambda: Image.new("L", (1200, 630)).save(og, format="JPEG"), "RGB JPEG"),
            ("EXIF", lambda: write_exif_jpeg(og), "EXIF"),
            ("ICC", lambda: Image.new("RGB", (1200, 630)).save(og, format="JPEG", icc_profile=b"fake-profile"), "ICC"),
        )
        for label, mutate, expected in cases:
            with self.subTest(label=label):
                mutate()
                self.assertIn(expected, "\n".join(self.errors()))

    def test_active_premium_contract_rejects_bad_mapping_attrs_and_kid_claim(self):
        index = self.root / "index.html"
        index.write_text(
            index.read_text(encoding="utf-8")
            .replace("hero-salon-mobile.webp", "hero-salon.webp", 1)
            .replace('width="4"', 'width=""', 1),
            encoding="utf-8",
        )
        balayage = self.root / "services" / "balayage.html"
        balayage.write_text(
            balayage.read_text(encoding="utf-8").replace('fetchpriority="high"', ""),
            encoding="utf-8",
        )
        kid = self.root / "services" / "coupes-enfant.html"
        kid.write_text(
            '<figure class="service-hero-image"><picture></picture><img src="../photosalon/web/service-balayage-desktop.jpg"></figure>',
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("index.html: premium photo references", errors)
        self.assertIn("index.html: hero-salon img width", errors)
        self.assertIn("services/balayage.html: premium hero fetchpriority", errors)
        self.assertIn("services/coupes-enfant.html: must remain external", errors)
        self.assertIn("service-hero-image--temporary", errors)
        self.assertIn("service-hero-image--cinematic", errors)

    def test_retired_page_is_existence_checked_but_exempt_from_premium_contract(self):
        retired = self.root / "services" / "lissage-ybera.html"
        retired.write_text('<img src="https://example.test/legacy.jpg">', encoding="utf-8")

        self.assertEqual(self.errors(), [])

        retired.write_text('<img src="../assets/gone.jpg">', encoding="utf-8")
        errors = "\n".join(self.errors())
        self.assertIn("services/lissage-ybera.html: missing local reference assets/gone.jpg", errors)
        self.assertNotIn("premium", errors)

    def test_cache_version_and_no_derivative_precache_are_enforced(self):
        self.fixture.write_service_worker(precache="'/photosalon/web/hero-salon-desktop.jpg'")
        sw = self.root / "sw.js"
        sw.write_text(
            sw.read_text(encoding="utf-8").replace("'v1.2.0'", "'v1.1.0'"),
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("sw.js: CACHE_VERSION must be exactly v1.2.0", errors)
        self.assertIn("sw.js: responsive derivatives must not be precached", errors)

    def test_cli_aggregates_errors_and_exits_nonzero_without_absolute_paths(self):
        (self.root / "photosalon" / "web" / "hero-salon-mobile.jpg").unlink()
        (self.root / "assets" / "og-image.jpg").write_bytes(b"broken")
        stderr = io.StringIO()
        stdout = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = verifier.main(["--root", str(self.root)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        output = stderr.getvalue()
        self.assertGreaterEqual(output.count("ERROR:"), 2)
        self.assertIn("photosalon/web/hero-salon-mobile.jpg", output)
        self.assertIn("assets/og-image.jpg", output)
        self.assertNotIn(str(self.root), output)

    def test_missing_manifest_error_does_not_expose_absolute_root(self):
        (self.root / "scripts" / "photo-manifest.json").unlink()

        errors = "\n".join(self.errors())

        self.assertIn("scripts/photo-manifest.json", errors)
        self.assertNotIn(str(self.root), errors)
        self.assertNotIn(str(self.root).replace("\\", "\\\\"), errors)


if __name__ == "__main__":
    unittest.main()
