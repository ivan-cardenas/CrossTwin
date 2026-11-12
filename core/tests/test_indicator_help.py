"""The "?" help entries of the indicator cards (core/indicator_help.py)."""
import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase

from core.indicator_help import HELP
from core.templatetags.indicator_help import friendly_equation

TEMPLATE_DIRS = ("watersupply", "urban_heat", "housing", "builtup", "Templates")
USED_KEY = re.compile(r'\{%\s*info_help\s+"([^"]+)"\s*%\}')


def _template_keys():
    base = Path(settings.BASE_DIR)
    keys = {}
    for app in TEMPLATE_DIRS:
        for path in (base / app).rglob("*.html"):
            for key in USED_KEY.findall(path.read_text(encoding="utf-8")):
                keys.setdefault(key, path)
    return keys


class IndicatorHelpEntriesTests(SimpleTestCase):
    def test_every_button_in_the_templates_has_an_entry(self):
        keys = _template_keys()
        self.assertTrue(keys, "no {% info_help %} found in the templates")
        missing = {k: str(p) for k, p in keys.items() if k not in HELP}
        self.assertEqual(missing, {})

    def test_every_entry_is_used_and_complete(self):
        used = set(_template_keys())
        for key, entry in HELP.items():
            with self.subTest(key=key):
                self.assertIn(key, used, "entry not used by any template")
                for field in ("title", "what", "how", "eq"):
                    self.assertTrue(entry.get(field), f"{field} missing")
                for line in entry["eq"]:
                    # balanced fraction braces, or the stacked fraction breaks
                    self.assertEqual(line.count("{"), line.count("}"), line)
                for pair in entry.get("where", []):
                    self.assertEqual(len(pair), 2)


class FriendlyEquationTests(SimpleTestCase):
    def test_fraction_is_stacked(self):
        html = friendly_equation("S = {25 400 | CN} − 254")
        self.assertIn('<span class="eq-num">25 400</span><span class="eq-den">CN</span>', html)
        self.assertTrue(html.endswith("− 254"))

    def test_superscript(self):
        self.assertIn("<sup>−n</sup>", friendly_equation("(1 + r)^(−n)"))

    def test_text_is_escaped(self):
        html = friendly_equation("a < b & {<i>x</i> | 2}")
        self.assertNotIn("<i>", html)
        self.assertIn("a &lt; b &amp;", html)


class InfoButtonRenderTests(SimpleTestCase):
    def test_button_carries_the_entry_in_a_template(self):
        html = Template('{% load indicator_help %}{% info_help "water.service_time" %}').render(Context())
        self.assertIn('class="info-btn"', html)
        self.assertIn('<template class="info-btn-content">', html)
        self.assertIn("What it is", html)
        self.assertIn("Equations", html)  # two lines → plural
        self.assertIn('class="eq-frac"', html)

    def test_legacy_include_still_renders_its_text(self):
        html = Template(
            "{% include 'partials/_info_btn.html' with title=\"T\" text=\"Plain note.\" %}"
        ).render(Context())
        self.assertIn("Plain note.", html)
        self.assertNotIn("What it is", html)
