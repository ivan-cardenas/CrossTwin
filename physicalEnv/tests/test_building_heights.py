"""Building heights from the DSM (physicalEnv/calculations/building_heights.py), the importer hook and the import-first prompt."""
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import SimpleTestCase, TestCase

SRID = int(settings.COORDINATE_SYSTEM)
ORIGIN = (250000.0, 470000.0)   # upper-left; 1 m cells; 80 x 80 grid
GROUND = 5.0


def _grid():
    """Ground at 5 m; a 10 x 10 m building of 25 m on rows/cols 50..59 with a 40 m chimney cell."""
    import numpy as np

    data = np.full((80, 80), GROUND, dtype="float32")
    data[50:60, 50:60] = GROUND + 25
    data[55, 55] = GROUND + 40
    return data


def _footprint(r0, c0, r1, c1):
    """Footprint covering cells rows r0..r1-1, cols c0..c1-1."""
    poly = Polygon.from_bbox((ORIGIN[0] + c0, ORIGIN[1] - r1, ORIGIN[0] + c1, ORIGIN[1] - r0))
    return MultiPolygon(poly, srid=SRID)


class FootprintHeightsTests(SimpleTestCase):
    def test_roof_percentile_minus_ground(self):
        import numpy as np

        from physicalEnv.calculations.building_heights import footprint_heights

        surface = _grid()
        ground = np.full(surface.shape, GROUND, dtype="float32")
        labels = np.zeros(surface.shape, dtype=np.int32)
        labels[50:60, 50:60] = 1      # the building: the chimney does not lift P70
        labels[5:10, 5:10] = 2        # flat ground: below MIN_BUILDING_HEIGHT_M
        self.assertEqual(footprint_heights(surface, ground, labels, 3), [25.0, None, None])


@mock.patch("core.rasterOperations.export_raster_to_cog")
class FillFromDsmTests(TestCase):
    def _dsm(self):
        import numpy as np
        from django.contrib.gis.gdal import GDALRaster

        from physicalEnv.models import DigitalSurfaceModel

        with mock.patch("core.rasterOperations.export_raster_to_cog"):
            DigitalSurfaceModel.objects.create(
                year=2024, source="AHN4", resolution=1.0,
                dsm_raster=GDALRaster({
                    "srid": SRID, "width": 80, "height": 80, "origin": ORIGIN, "scale": (1.0, -1.0),
                    "datatype": 6, "bands": [{"data": np.ascontiguousarray(_grid()), "nodata_value": -9999.0}],
                }))

    def test_fills_missing_heights_only(self, _cog):
        from builtup.models import Building

        from physicalEnv.calculations.building_heights import fill_from_dsm

        self._dsm()
        Building.objects.create(id=1, geom=_footprint(50, 50, 60, 60))
        Building.objects.create(id=2, geom=_footprint(50, 50, 60, 60), height_m=9.0)
        Building.objects.create(id=3, geom=_footprint(5, 5, 10, 10))

        self.assertEqual(fill_from_dsm(Building.objects.all()), 1)
        # no DEM: ground = 40 m minimum filter of the DSM = 5 m
        self.assertEqual(Building.objects.get(pk=1).height_m, 25.0)
        self.assertEqual(Building.objects.get(pk=2).height_m, 9.0)     # source wins
        self.assertIsNone(Building.objects.get(pk=3).height_m)

    def test_import_hook_measures_imported_buildings(self, _cog):
        from builtup.models import Building
        from importer.external_data import _fill_building_heights

        self._dsm()
        Building.objects.create(id=153100000212134, geom=_footprint(50, 50, 60, 60))
        notes = []
        _fill_building_heights([{"properties": {"identificatie": "0153100000212134"}}], "identificatie", notes)
        self.assertEqual(Building.objects.get().height_m, 25.0)
        self.assertEqual(notes, ["1 building height(s) measured from the DSM"])

    def test_import_hook_without_dsm_leaves_a_note(self, _cog):
        from builtup.models import Building
        from importer.external_data import _fill_building_heights

        Building.objects.create(id=1, geom=_footprint(50, 50, 60, 60))
        notes = []
        _fill_building_heights([{"properties": {"identificatie": "1"}}], "identificatie", notes)
        self.assertIsNone(Building.objects.get().height_m)
        self.assertIn("no Digital Surface Model stored", notes[0])


    def test_dsm_import_fills_buildings_imported_before_it(self, _cog):
        from builtup.models import Building
        from importer.external_data import _heights_after_dsm

        from physicalEnv.models import DigitalSurfaceModel

        Building.objects.create(id=1, geom=_footprint(50, 50, 60, 60))
        Building.objects.create(id=2, geom=_footprint(50, 50, 60, 60), height_m=9.0)
        self._dsm()
        with mock.patch("builtup.signals.schedule_footprints") as canyons:
            message = _heights_after_dsm(DigitalSurfaceModel.objects.get())
        self.assertEqual(message, " 1 building height(s) measured from it.")
        self.assertEqual(Building.objects.get(pk=1).height_m, 25.0)
        self.assertEqual(Building.objects.get(pk=2).height_m, 9.0)
        # Buildings -> Canyon_Aspect re-run around the measured building only
        self.assertEqual(len(canyons.call_args.args[0]), 1)


@mock.patch("core.rasterOperations.export_raster_to_cog")
class ImportFirstTests(TestCase):
    def test_dsm_is_asked_for_until_one_is_stored(self, _cog):
        from importer.views_external import _import_first_status

        status = _import_first_status()["pdok_buildings"]
        self.assertEqual((status["dataset"], status["present"]), ("pdok_dsm_ahn_raster", False))
        FillFromDsmTests._dsm(self)
        self.assertTrue(_import_first_status()["pdok_buildings"]["present"])

    def test_page_shows_the_notice(self, _cog):
        from django.urls import reverse

        response = self.client.get(reverse("importer:external_data"))
        self.assertContains(response, "Import first:")

    def test_dsm_runs_before_the_buildings(self, _cog):
        from importer.views_external import _order_import_first

        self.assertEqual(_order_import_first(["pdok_buildings", "pdok_streets", "pdok_dsm_ahn_raster"]),
                         ["pdok_dsm_ahn_raster", "pdok_buildings", "pdok_streets"])
        self.assertEqual(_order_import_first(["pdok_buildings"]), ["pdok_buildings"])
