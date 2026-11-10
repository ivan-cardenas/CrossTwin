"""physicalEnv/dsm_edited.py: editor patches burnt into the DSM COG the map shows (Buildings -> DSM)."""
import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase


def _square(x, y, half):
    return MultiPolygon(Polygon(((x - half, y - half), (x + half, y - half), (x + half, y + half),
                                 (x - half, y + half), (x - half, y - half))), srid=int(settings.COORDINATE_SYSTEM))


class EditedDsmCogTests(TestCase):
    def setUp(self):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        from .models import DigitalSurfaceModel

        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        # ~1 m cells near Enschede, flat 40 m surface, as _reproject_and_cog writes it (EPSG:4326).
        self.path = os.path.join(self.dir, "DigitalSurfaceModel_AHN4_2024_1.tif").replace("\\", "/")
        self.transform = from_origin(6.89, 52.22, 1.5e-5, 1e-5)
        with rasterio.open(self.path, "w", driver="GTiff", width=200, height=200, count=1,
                           dtype="float32", crs="EPSG:4326", nodata=-9999.0, tiled=True,
                           blockxsize=128, blockysize=128, transform=self.transform) as dst:
            dst.write(np.full((200, 200), 40.0, dtype="float32"), 1)
        self.dsm = DigitalSurfaceModel.objects.create(year=2024, source="AHN4", cog_path=self.path)

        centre = Point(6.89 + 100 * 1.5e-5, 52.22 - 100 * 1e-5, srid=4326)
        centre.transform(int(settings.COORDINATE_SYSTEM))
        self.centre = centre

    def _value(self, path, lng, lat):
        import rasterio

        with rasterio.open(path) as src:
            return float(next(src.sample([(lng, lat)]))[0])

    def _centre_value(self, path):
        return self._value(path, 6.89 + 100 * 1.5e-5, 52.22 - 100 * 1e-5)

    def _corner_value(self, path):
        return self._value(path, 6.89 + 5 * 1.5e-5, 52.22 - 5 * 1e-5)

    def test_a_building_edit_is_written_into_the_displayed_dsm(self):
        from .models import DSMBuildingPatch

        with self.captureOnCommitCallbacks(execute=True):
            patch = DSMBuildingPatch.objects.create(
                building_id=-1, footprint=_square(self.centre.x, self.centre.y, 8), height_m=12.0)
        self.dsm.refresh_from_db()
        edited = self.dsm.edited_cog_path
        self.assertTrue(edited and os.path.exists(edited))
        self.assertAlmostEqual(self._centre_value(edited), 52.0, places=3)     # ground 40 + 12 m
        self.assertAlmostEqual(self._corner_value(edited), 40.0, places=3)
        self.assertAlmostEqual(self._centre_value(self.path), 40.0, places=3)  # measured COG untouched

        # Deleting the patch (e.g. Restore) puts the measured surface back, in a new file.
        with self.captureOnCommitCallbacks(execute=True):
            patch.delete()
        self.dsm.refresh_from_db()
        self.assertNotEqual(self.dsm.edited_cog_path, edited)
        self.assertFalse(os.path.exists(edited))
        self.assertAlmostEqual(self._centre_value(self.dsm.edited_cog_path), 40.0, places=3)

    def test_the_map_serves_the_edited_cog(self):
        from core.views import displayed_cog_path

        from .dsm_edited import refresh_edited_cog
        from .models import DSMBuildingPatch

        self.assertEqual(displayed_cog_path(self.dsm), self.path)
        DSMBuildingPatch.objects.create(
            building_id=-2, footprint=_square(self.centre.x, self.centre.y, 8), height_m=6.0)
        refresh_edited_cog(self.dsm)
        self.dsm.refresh_from_db()
        self.assertEqual(displayed_cog_path(self.dsm), self.dsm.edited_cog_path)
        self.assertNotEqual(self.dsm.edited_cog_path, self.path)

    def test_a_new_cog_rebuilds_the_edited_copy_from_all_patches(self):
        from .dsm_edited import refresh_edited_cog
        from .models import DSMBuildingPatch

        DSMBuildingPatch.objects.create(
            building_id=-3, footprint=_square(self.centre.x, self.centre.y, 8), height_m=10.0)
        refresh_edited_cog(self.dsm)
        self.dsm.refresh_from_db()

        # A re-export writes a new cog_path: the edited copy is dropped and rebuilt.
        moved = os.path.join(self.dir, "DigitalSurfaceModel_AHN4_2024_1_new.tif").replace("\\", "/")
        shutil.copyfile(self.path, moved)
        self.dsm.cog_path = moved
        with self.captureOnCommitCallbacks(execute=True):
            self.dsm.save(update_fields=["cog_path"])
        self.dsm.refresh_from_db()
        self.assertTrue(self.dsm.edited_cog_path.startswith(moved[:-4]))
        self.assertAlmostEqual(self._centre_value(self.dsm.edited_cog_path), 50.0, places=3)

    def test_no_edit_no_copy(self):
        from .dsm_edited import refresh_edited_cog

        self.assertIsNone(refresh_edited_cog(self.dsm))
        self.dsm.refresh_from_db()
        self.assertIsNone(self.dsm.edited_cog_path)


class EditedDsmWorkerTests(TestCase):
    """The background worker: the save returns at once, edits queued meanwhile are coalesced."""

    def test_worker_runs_in_the_background_and_coalesces(self):
        import threading
        from unittest import mock

        from django.test import override_settings

        from . import dsm_edited

        started, release, done = threading.Event(), threading.Event(), threading.Event()
        calls = []

        def slow_refresh(dsm_pk=None):
            calls.append(dsm_pk)
            started.set()
            release.wait(5)
            if len(calls) == 2:
                done.set()

        with override_settings(DSM_EDIT_BACKGROUND=True), \
                mock.patch.object(dsm_edited, "refresh_pending", side_effect=slow_refresh), \
                mock.patch("django.db.connection.close"):
            dsm_edited.enqueue(1)
            self.assertTrue(started.wait(5))
            self.assertTrue(dsm_edited.busy())
            dsm_edited.enqueue(2)            # while the first pass writes
            dsm_edited.enqueue(2)
            self.assertEqual(self.client.get("/physicalEnv/dsm/edited/status/").json(), {"busy": True})
            release.set()
            self.assertTrue(done.wait(5))
            for _ in range(50):
                if not dsm_edited.busy():
                    break
                threading.Event().wait(0.05)
        self.assertEqual(calls, [1, 2])      # the two queued edits of DSM 2 written in one pass
        self.assertFalse(dsm_edited.busy())
        self.assertEqual(self.client.get("/physicalEnv/dsm/edited/status/").json(), {"busy": False})
