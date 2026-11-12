"""docs/DATA_SOURCES.md lists every importer dataset and is regenerated when the catalog changes."""
import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

ROOT = Path(settings.BASE_DIR)


def _tool():
    spec = importlib.util.spec_from_file_location("data_sources_tool", ROOT / "tools" / "data_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DataSourcesDocTests(SimpleTestCase):
    def test_doc_is_current(self):
        tool = _tool()
        self.assertEqual(tool.OUTPUT.read_text(encoding="utf-8"), tool.render(),
                         "docs/DATA_SOURCES.md is out of date: run uv run python tools/data_sources.py")

    def test_every_catalog_dataset_and_reference_is_listed(self):
        from core.data_sources import REFERENCES
        from importer.external_catalog import EXTERNAL_DATA_CATALOG
        text = _tool().render()
        for entry in EXTERNAL_DATA_CATALOG:
            self.assertIn(f"`{entry['key']}`", text)
        for key, _citation, _used in REFERENCES:
            self.assertIn(key, text)
        for needle in ("bij12_nnn", "Bbl", "NEN 2580", "NEN 6068", "Open-Meteo"):
            self.assertIn(needle, text)
