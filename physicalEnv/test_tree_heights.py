"""Tree heights from the DSM (physicalEnv/tree_heights.py) and the importer's nature.Tree finalizer."""
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import SimpleTestCase, TestCase

SRID = int(settings.COORDINATE_SYSTEM)
ORIGIN = (250000.0, 470000.0)   # upper-left; 1 m cells; 80 x 80 grid
GROUND = 5.0


def _cell_xy(row, col):
    return ORIGIN[0] + col + 0.5, ORIGIN[1] - row - 0.5


def _grid():
    """Ground at 5 m, a 12 m crown peaking at (20, 20), a 25 m building on rows/cols 50..60."""
    import numpy as np

    data = np.full((80, 80), GROUND, dtype="float32")
    data[18:23, 18:23] = GROUND + 9
    data[20, 20] = GROUND + 12
    data[50:60, 50:60] = GROUND + 25
    return data


class SampleHeightsTests(SimpleTestCase):
    def _sample(self, points, blocked=None):
        import numpy as np

        from .tree_heights import sample_heights

        surface = _grid()
        ground = np.full(surface.shape, GROUND, dtype="float32")
        return sample_heights(surface, ground, blocked, ORIGIN, 1.0, points)

    def test_takes_the_crown_top_near_the_point(self):
        # mapped 1.5 m off the crown top: still within SAMPLE_RADIUS_M
        x, y = _cell_xy(20, 20)
        self.assertEqual(self._sample([(x + 1.5, y)]), [12.0])

    def test_no_crown_in_the_dsm_keeps_none(self):
        self.assertEqual(self._sample([_cell_xy(5, 70)]), [None])

    def test_outside_the_grid_is_none(self):
        self.assertEqual(self._sample([(ORIGIN[0] - 10, ORIGIN[1] + 10)]), [None])

    def test_building_cells_do_not_count(self):
        import numpy as np

        blocked = np.zeros((80, 80), dtype=bool)
        blocked[50:60, 50:60] = True
        beside = _cell_xy(55, 61)   # 1 m east of the facade
        self.assertEqual(self._sample([beside]), [25.0])          # roof picked up without the mask
        self.assertEqual(self._sample([beside], blocked), [None])


@mock.patch("core.rasterOperations.export_raster_to_cog")
class FillFromDsmTests(TestCase):
    def setUp(self):
        import numpy as np
        from django.contrib.gis.gdal import GDALRaster

        from .models import DigitalSurfaceModel

        with mock.patch("core.rasterOperations.export_raster_to_cog"):
            DigitalSurfaceModel.objects.create(
                year=2024, source="AHN4", resolution=1.0,
                dsm_raster=GDALRaster({
                    "srid": SRID, "width": 80, "height": 80, "origin": ORIGIN, "scale": (1.0, -1.0),
                    "datatype": 6, "bands": [{"data": np.ascontiguousarray(_grid()), "nodata_value": -9999.0}],
                }))

    def _tree(self, row, col, **kw):
        from nature.models import Tree

        return Tree.objects.create(geom=Point(*_cell_xy(row, col), srid=SRID), **kw)

    def test_fills_missing_heights_only(self, _cog):
        from nature.models import Tree

        from .tree_heights import fill_from_dsm

        measured = self._tree(20, 21, sourceID="osm:node/1")
        tagged = self._tree(20, 20, sourceID="osm:node/2", height_m=7.0)
        bare = self._tree(5, 70, sourceID="osm:node/3")

        self.assertEqual(fill_from_dsm(Tree.objects.all()), 1)
        # no DEM: ground = 40 m minimum filter of the DSM = 5 m
        self.assertEqual(Tree.objects.get(pk=measured.pk).height_m, 12.0)
        self.assertEqual(Tree.objects.get(pk=tagged.pk).height_m, 7.0)    # source wins
        self.assertIsNone(Tree.objects.get(pk=bare.pk).height_m)          # map keeps its default

    def test_skips_building_footprints(self, _cog):
        from builtup.models import Building
        from nature.models import Tree

        from .tree_heights import fill_from_dsm

        x0, y1 = _cell_xy(50, 50)
        x1, y0 = _cell_xy(59, 59)
        footprint = Polygon.from_bbox((x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5))
        Building.objects.create(id=1, geom=MultiPolygon(footprint, srid=SRID))
        tree = self._tree(55, 61)

        fill_from_dsm(Tree.objects.all())
        self.assertIsNone(Tree.objects.get(pk=tree.pk).height_m)

    def test_import_finalizer_measures_bulk_written_trees(self, _cog):
        from importer.batching import BulkWriter
        from nature.models import Tree

        writer = BulkWriter.for_model(Tree, "sourceID")
        writer.add({"sourceID": "osm:node/9", "geom": Point(*_cell_xy(20, 19), srid=SRID)})
        writer.finish()
        self.assertEqual(Tree.objects.get(sourceID="osm:node/9").height_m, 12.0)
