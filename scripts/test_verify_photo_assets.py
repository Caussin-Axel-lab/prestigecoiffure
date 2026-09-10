import importlib.util
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

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


def picture_markup(
    slug,
    prefix="",
    *,
    below_fold=False,
    mobile_jpeg_type=True,
    mobile_media="(max-width: 720px)",
):
    loading = ' loading="lazy" decoding="async"' if below_fold else ' loading="eager" fetchpriority="high"'
    jpeg_type = ' type="image/jpeg"' if mobile_jpeg_type else ""
    return f"""
      <picture>
        <source media="{mobile_media}" type="image/webp" srcset="{prefix}photosalon/web/{slug}-mobile.webp">
        <source media="{mobile_media}"{jpeg_type} srcset="{prefix}photosalon/web/{slug}-mobile.jpg">
        <source type="image/webp" srcset="{prefix}photosalon/web/{slug}-desktop.webp">
        <img src="{prefix}photosalon/web/{slug}-desktop.jpg" width="4" height="4" alt="Description utile"{loading}>
      </picture>
    """


def write_exif_jpeg(path):
    exif = Image.Exif()
    exif[274] = 1
    Image.new("RGB", (1200, 630)).save(path, format="JPEG", exif=exif)


def file_hashes(directory):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.iterdir())
        if path.is_file()
    }


class RepositoryFixture:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "scripts").mkdir()
        (self.root / "services").mkdir()
        (self.root / "photosalon" / "web").mkdir(parents=True)
        (self.root / "photosalon" / "retouched").mkdir()
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
            source = Image.new("RGB", (4, 4), "tan")
            source.save(
                self.root / "photosalon" / "retouched" / f"{slug}.png",
                format="PNG",
            )
            for variant in ("desktop", "mobile"):
                for extension, image_format in (("jpg", "JPEG"), ("webp", "WEBP")):
                    destination = output / f"{slug}-{variant}.{extension}"
                    if image_format == "JPEG":
                        source.save(
                            destination,
                            format="JPEG",
                            quality=88,
                            optimize=True,
                            progressive=True,
                        )
                    else:
                        source.save(
                            destination,
                            format="WEBP",
                            quality=84,
                            method=6,
                        )

    def write_html(self):
        index_roles = ROLE_SLUGS[:5]
        index_media = {
            "hero-salon": "(max-width: 900px)",
            "salon-lounge": "(max-width: 860px)",
            "salon-barbier": "(max-width: 860px)",
            "salon-headspa": "(max-width: 860px)",
            "cabine-headspa": "(max-width: 720px)",
        }
        index = ["<!doctype html><html><body>"]
        for position, slug in enumerate(index_roles):
            index.append(
                picture_markup(
                    slug,
                    below_fold=position > 0,
                    mobile_jpeg_type=False,
                    mobile_media=index_media[slug],
                )
            )
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
        target = self.root / "photosalon" / "web" / "hero-salon-desktop.jpg"
        Image.new("RGB", (4, 4), "black").save(
            target,
            format="JPEG",
            quality=88,
            optimize=True,
            progressive=True,
        )

        errors = "\n".join(self.errors())

        self.assertIn("trusted derivative verification", errors)
        self.assertIn("photosalon/web/hero-salon-desktop.jpg: stale derivative", errors)
        self.assertNotIn(str(self.root), errors)

    def test_audited_root_builder_is_never_executed_or_allowed_to_mutate(self):
        marker = self.root / "malicious-builder-ran"
        target = self.root / "photosalon" / "web" / "hero-salon-desktop.jpg"
        before = file_hashes(self.root / "photosalon" / "web")
        (self.root / "scripts" / "build-photo-derivatives.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed')\n"
            f"Path({str(target)!r}).write_bytes(b'mutated')\n",
            encoding="utf-8",
        )

        self.assertEqual(self.errors(), [])

        self.assertFalse(marker.exists())
        self.assertEqual(file_hashes(self.root / "photosalon" / "web"), before)

    def test_trusted_staleness_check_preserves_all_56_output_hashes(self):
        output = self.root / "photosalon" / "web"
        before = file_hashes(output)
        self.assertEqual(len(before), 56)

        self.assertEqual(self.errors(), [])

        self.assertEqual(file_hashes(output), before)

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

    def test_og_contract_rejects_wrong_format_and_oversized_file(self):
        og = self.root / "assets" / "og-image.jpg"
        Image.new("RGB", (1200, 630)).save(og, format="PNG")
        self.assertIn("RGB JPEG", "\n".join(self.errors()))

        self.fixture.write_og()
        og.write_bytes(og.read_bytes() + b"x" * 900_001)
        self.assertIn("exceeds 900000 bytes", "\n".join(self.errors()))

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

    def test_index_rejects_a_sixth_picture_even_when_it_is_external(self):
        index = self.root / "index.html"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "</body>",
                '<picture><img src="https://example.test/extra.jpg" alt="Extra"></picture></body>',
            ),
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("index.html: expected exactly 5 picture elements, got 6", errors)

    def test_service_rejects_premium_picture_outside_its_hero_figure(self):
        service = self.root / "services" / "balayage.html"
        service.write_text(
            '<figure class="service-hero-image service-hero-image--cinematic"></figure>'
            + picture_markup("service-balayage", prefix="../"),
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("services/balayage.html: premium picture must be inside the unique hero figure", errors)

    def test_service_rejects_multiple_local_hero_figures(self):
        service = self.root / "services" / "balayage.html"
        service.write_text(
            '<figure class="service-hero-image service-hero-image--cinematic"></figure>'
            + service.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("services/balayage.html: expected exactly one service hero figure, got 2", errors)

    def test_service_rejects_external_image_inside_local_hero(self):
        service = self.root / "services" / "balayage.html"
        service.write_text(
            service.read_text(encoding="utf-8").replace(
                "<picture>",
                '<img src="https://example.test/wrong-hero.jpg" alt="Wrong"><picture>',
                1,
            ),
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("services/balayage.html: hero figure must contain exactly the premium fallback img", errors)

    def test_picture_source_attributes_are_exact_for_index_and_services(self):
        index = self.root / "index.html"
        original_index = index.read_text(encoding="utf-8")
        index.write_text(
            original_index.replace(
                'media="(max-width: 900px)" srcset="photosalon/web/hero-salon-mobile.jpg"',
                'media="(max-width: 900px)" type="image/jpeg" srcset="photosalon/web/hero-salon-mobile.jpg"',
                1,
            ),
            encoding="utf-8",
        )
        self.assertIn(
            "index.html: hero-salon mobile JPEG source must not declare type",
            "\n".join(self.errors()),
        )

        index.write_text(original_index, encoding="utf-8")
        service = self.root / "services" / "balayage.html"
        original_service = service.read_text(encoding="utf-8")
        cases = (
            (
                "media",
                original_service.replace("(max-width: 720px)", "(max-width: 999px)"),
                "mobile source media must be exactly (max-width: 720px)",
            ),
            (
                "JPEG type",
                original_service.replace(' type="image/jpeg"', "", 1),
                "mobile JPEG source type must be image/jpeg",
            ),
            (
                "WebP type",
                original_service.replace(
                    'type="image/webp" srcset="../photosalon/web/service-balayage-mobile.webp"',
                    'type="image/jpeg" srcset="../photosalon/web/service-balayage-mobile.webp"',
                    1,
                ),
                "mobile WebP source type must be image/webp",
            ),
            (
                "desktop media",
                original_service.replace(
                    '<source type="image/webp" srcset="../photosalon/web/service-balayage-desktop.webp">',
                    '<source media="(min-width: 721px)" type="image/webp" srcset="../photosalon/web/service-balayage-desktop.webp">',
                    1,
                ),
                "desktop WebP source must not declare media",
            ),
        )
        for label, document, expected in cases:
            with self.subTest(label=label):
                service.write_text(document, encoding="utf-8")
                self.assertIn(expected, "\n".join(self.errors()))

    def test_child_requires_one_hero_with_all_classes_on_the_same_figure(self):
        child = self.root / "services" / "coupes-enfant.html"
        child.write_text(
            '<figure class="service-hero-image service-hero-image--cinematic">'
            '<img src="https://example.test/one.jpg" alt="One"></figure>'
            '<figure class="service-hero-image service-hero-image--temporary">'
            '<img src="https://example.test/two.jpg" alt="Two"></figure>',
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("services/coupes-enfant.html: expected exactly one service hero figure, got 2", errors)

    def test_child_rejects_picture_and_local_hero_url(self):
        child = self.root / "services" / "coupes-enfant.html"
        child.write_text(
            '<figure class="service-hero-image service-hero-image--cinematic service-hero-image--temporary">'
            '<picture><img src="../assets/og-image.jpg" alt="Local"></picture>'
            "</figure>",
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("services/coupes-enfant.html: temporary hero must not contain a picture", errors)
        self.assertIn("services/coupes-enfant.html: temporary hero img must be external", errors)

    def test_child_requires_exactly_one_hero_image(self):
        child = self.root / "services" / "coupes-enfant.html"
        child.write_text(
            '<figure class="service-hero-image service-hero-image--cinematic service-hero-image--temporary">'
            '<img src="https://example.test/one.jpg" alt="One">'
            '<img src="https://example.test/two.jpg" alt="Two">'
            "</figure>",
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn("services/coupes-enfant.html: temporary hero must contain exactly one img", errors)

    def test_manifest_requires_exact_roles_and_variants(self):
        manifest_path = self.root / "scripts" / "photo-manifest.json"
        original = json.loads(manifest_path.read_text(encoding="utf-8"))
        cases = []
        missing_role = json.loads(json.dumps(original))
        missing_role.pop("hero-salon")
        cases.append(("role", missing_role, "expected exactly 14 photo roles"))
        extra_variant = json.loads(json.dumps(original))
        extra_variant["hero-salon"]["variants"]["tablet"] = {
            "width": 4,
            "height": 4,
            "focalX": 0.5,
            "focalY": 0.5,
        }
        cases.append(("variant", extra_variant, "must define exactly desktop and mobile variants"))

        for label, manifest, expected in cases:
            with self.subTest(label=label):
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                self.assertIn(expected, "\n".join(self.errors()))

    def test_duplicate_attributes_are_rejected_before_dict_conversion(self):
        retired = self.root / "services" / "lissage-ybera.html"
        retired.write_text(
            '<img src="../assets/missing.jpg" src="../assets/og-image.jpg">',
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn(
            "services/lissage-ybera.html:1: <img> duplicate attribute 'src'",
            errors,
        )

    def test_premium_service_hero_and_picture_are_rejected_inside_template(self):
        service = self.root / "services" / "balayage.html"
        service.write_text(
            "<template>" + service.read_text(encoding="utf-8") + "</template>",
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn(
            "services/balayage.html: service hero figure must not be inside <template>",
            errors,
        )
        self.assertIn(
            "services/balayage.html: premium picture must not be inside <template>",
            errors,
        )

    def test_premium_srcset_rejects_multiple_remote_and_local_candidates(self):
        service = self.root / "services" / "balayage.html"
        expected = "../photosalon/web/service-balayage-mobile.webp"
        original = service.read_text(encoding="utf-8")
        cases = (
            (f"https://example.test/remote.webp 1x, {expected} 2x", "remote and expected"),
            (f"{expected}, {expected}", "two local candidates"),
        )
        for srcset, label in cases:
            with self.subTest(label=label):
                service.write_text(
                    original.replace(f'srcset="{expected}"', f'srcset="{srcset}"', 1),
                    encoding="utf-8",
                )
                self.assertIn(
                    "service-balayage mobile WebP source must contain exactly one srcset candidate",
                    "\n".join(self.errors()),
                )

    def test_premium_srcset_rejects_descriptor_on_single_expected_candidate(self):
        service = self.root / "services" / "balayage.html"
        expected = "../photosalon/web/service-balayage-mobile.webp"
        service.write_text(
            service.read_text(encoding="utf-8").replace(
                f'srcset="{expected}"', f'srcset="{expected} 2x"', 1
            ),
            encoding="utf-8",
        )

        errors = "\n".join(self.errors())

        self.assertIn(
            "service-balayage mobile WebP source must not use a srcset descriptor",
            errors,
        )

    def test_single_local_expected_srcset_candidate_is_accepted(self):
        self.assertEqual(self.errors(), [])

    def test_oversized_derivative_is_not_opened_or_decoded(self):
        target = self.root / "photosalon" / "web" / "hero-salon-desktop.jpg"
        target.write_bytes(target.read_bytes() + b"x" * 900_001)
        errors = []
        with mock.patch.object(verifier.Image, "open", wraps=Image.open) as opened:
            verifier._check_image(self.root, target, "JPEG", (4, 4), errors)

        opened_paths = [Path(call.args[0]) for call in opened.call_args_list]
        self.assertNotIn(target, opened_paths)
        self.assertIn("exceeds 900000 bytes", "\n".join(errors))

    def test_decompression_bomb_warning_is_aggregated_as_image_error(self):
        target = self.root / "small.jpg"
        Image.new("RGB", (20, 20), "black").save(target, format="JPEG")
        errors = []

        with mock.patch.object(verifier.Image, "MAX_IMAGE_PIXELS", 300):
            verifier._check_image(self.root, target, "JPEG", (20, 20), errors)

        self.assertIn("decompression bomb", "\n".join(errors).lower())

    def test_explicit_pixel_limit_is_checked_before_image_load(self):
        target = self.root / "bounded.jpg"
        Image.new("RGB", (20, 20), "black").save(target, format="JPEG")
        errors = []

        with mock.patch.object(
            verifier, "MAX_DECODE_PIXELS", 100, create=True
        ):
            verifier._check_image(self.root, target, "JPEG", (20, 20), errors)

        self.assertIn("pixel limit", "\n".join(errors))

    def test_local_references_are_resolved_case_sensitively(self):
        retired = self.root / "services" / "lissage-ybera.html"
        for reference in (
            "../Assets/og-image.jpg",
            "../assets/OG-image.jpg",
            "../assets/og-image.JPG",
        ):
            with self.subTest(reference=reference):
                retired.write_text(f'<img src="{reference}">', encoding="utf-8")
                self.assertIn("case mismatch", "\n".join(self.errors()))

        retired.write_text(
            '<img src="../assets/og%2Dimage.jpg">', encoding="utf-8"
        )
        self.assertEqual(self.errors(), [])

    def test_manifest_og_and_html_entry_paths_require_exact_case(self):
        cases = (
            (
                self.root / "scripts" / "photo-manifest.json",
                self.root / "scripts" / "Photo-Manifest.json",
                "scripts/photo-manifest.json",
            ),
            (
                self.root / "assets" / "og-image.jpg",
                self.root / "assets" / "OG-image.jpg",
                "assets/og-image.jpg",
            ),
            (
                self.root / "index.html",
                self.root / "Index.html",
                "index.html",
            ),
        )
        for expected, wrong_case, label in cases:
            with self.subTest(label=label):
                intermediate = expected.with_name("case-rename.tmp")
                expected.rename(intermediate)
                intermediate.rename(wrong_case)
                try:
                    errors = "\n".join(self.errors())
                    self.assertIn(label, errors)
                    self.assertIn("case mismatch", errors)
                finally:
                    wrong_case.rename(intermediate)
                    intermediate.rename(expected)

    def test_manifest_input_path_requires_exact_case(self):
        manifest_path = self.root / "scripts" / "photo-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["hero-salon"]["input"] = (
            "photosalon/Retouched/hero-salon.PNG"
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        errors = "\n".join(self.errors())

        self.assertIn("scripts/photo-manifest.json: hero-salon.input", errors)
        self.assertIn("case mismatch", errors)

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
