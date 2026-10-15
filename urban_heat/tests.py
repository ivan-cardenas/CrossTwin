from django.test import SimpleTestCase, TestCase
from unittest import mock

from .calculations import WBGT_BANDS, classify_wbgt, get_thermal_indices, wbgt_color
from .views import MOCK_DATA, _build_indicators


class ClassifyWbgtTests(SimpleTestCase):
    def test_none_has_no_category_or_color(self):
        self.assertIsNone(classify_wbgt(None))
        self.assertIsNone(wbgt_color(None))

    def test_band_edges_belong_to_the_hotter_band(self):
        # Upper bounds are exclusive: exactly 25 is already 'Moderate'.
        self.assertEqual(classify_wbgt(24.9), 'No Heat Stress')
        self.assertEqual(classify_wbgt(25), 'Moderate Heat Stress')
        self.assertEqual(classify_wbgt(28), 'Strong Heat Stress')
        self.assertEqual(classify_wbgt(30), 'Very Strong Heat Stress')
        self.assertEqual(classify_wbgt(33), 'Extreme Heat Stress')

    def test_extremes_are_covered(self):
        self.assertEqual(classify_wbgt(-10), 'No Heat Stress')
        self.assertEqual(classify_wbgt(60), 'Extreme Heat Stress')

    def test_color_follows_the_category(self):
        for upper, label, color in WBGT_BANDS:
            probe = upper - 0.01 if upper != float('inf') else 100
            self.assertEqual(classify_wbgt(probe), label)
            self.assertEqual(wbgt_color(probe), color)


class WbgtIndicatorTests(SimpleTestCase):
    def test_indicators_expose_wbgt_from_the_mock_data(self):
        indicators = _build_indicators(MOCK_DATA)
        self.assertEqual(indicators['wbgt_mean'], 23.4)
        self.assertEqual(indicators['wbgt_category'], 'No Heat Stress')
        self.assertEqual(indicators['wbgt_color'], '#22c55e')
        # 23.4 of a 35 degree gauge
        self.assertAlmostEqual(indicators['wbgt_pct'], 66.9, places=1)

    def test_gauge_is_capped_at_100_percent(self):
        data = {**MOCK_DATA, 'thermal': {**MOCK_DATA['thermal'], 'wbgt': {**MOCK_DATA['thermal']['wbgt'], 'mean': 50}}}
        self.assertEqual(_build_indicators(data)['wbgt_pct'], 100)

    def test_no_wbgt_raster_leaves_the_indicator_empty(self):
        data = {**MOCK_DATA, 'thermal': {k: v for k, v in MOCK_DATA['thermal'].items() if k != 'wbgt'}}
        indicators = _build_indicators(data)
        self.assertIsNone(indicators['wbgt_mean'])
        self.assertIsNone(indicators['wbgt_category'])
        self.assertEqual(indicators['wbgt_pct'], 0)


class WbgtRasterStatsTests(TestCase):
    """The stats query reads the newest WBGT raster inside the unit, like the other indices."""

    def test_thermal_indices_report_none_without_a_wbgt_raster(self):
        from watersupply.tests.factories import make_city
        indices = get_thermal_indices(make_city())
        self.assertIn('wbgt', indices)
        self.assertIsNone(indices['wbgt'])


class SmwEquationTests(SimpleTestCase):
    """urban_heat/lst/smw.py against hand-computed values of the Earth Engine modules."""

    def setUp(self):
        import numpy as np
        from .lst import smw
        from .lst.coefficients import SMW_COEFFICIENTS
        self.np, self.smw, self.coef = np, smw, SMW_COEFFICIENTS

    def test_fvc_squares_before_clipping(self):
        fvc = self.smw.fractional_vegetation_cover([0.86, 0.2, 0.53, 1.0, 0.0])
        self.np.testing.assert_allclose(fvc, [1.0, 0.0, 0.25, 1.0, (0.2 / 0.66) ** 2])

    def test_tpw_bins_are_left_open_6mm_steps(self):
        bins = self.smw.tpw_bin([-999, 0, 6, 6.01, 54, 54.1, 80])
        self.assertEqual(bins.tolist(), [0, 0, 0, 1, 8, 9, 9])

    def test_tpw_interpolation_weights_the_closer_field_more(self):
        h = 3600 * 1000
        tpw = self.smw.interpolate_tpw([(self.np.array([10.0]), 4 * h), (self.np.array([20.0]), 2 * h)])
        self.assertAlmostEqual(float(tpw[0]), 20 * 4 / 6 + 10 * 2 / 6)

    def test_hourly_era5_fields_interpolate_within_their_hour(self):
        h = 3600 * 1000
        # Scene at 10:27 between ERA5's 10:00 (27 min) and 11:00 (33 min) fields.
        tpw = self.smw.interpolate_tpw(
            [(self.np.array([16.3]), 27 * h // 60), (self.np.array([16.6]), 33 * h // 60)], step_ms=h)
        self.assertAlmostEqual(float(tpw[0]), 16.3 * 33 / 60 + 16.6 * 27 / 60)

    def test_no_ncep_field_masks_the_lst(self):
        tpw = self.smw.interpolate_tpw([])
        lst = self.smw.smw_lst(self.np.array([300.0]), self.np.array([0.98]), tpw)
        self.assertTrue(self.np.isnan(lst).all())

    def test_smw_lst_uses_the_landsat9_row_of_the_tpw_bin(self):
        a, b, c = self.coef["L9"][1]   # TPW 10 mm -> bin 1
        lst = self.smw.smw_lst(self.np.array([300.0]), self.np.array([0.98]), self.np.array([10.0]))
        self.assertAlmostEqual(float(lst[0]), a * 300 / 0.98 + b / 0.98 + c, places=6)
        self.assertAlmostEqual(float(lst[0]), 302.41888, places=4)

    def test_bare_ground_emissivity_removes_aster_vegetation(self):
        bare = self.smw.bare_ground_emissivity([0.97, 0.97], [0.53, 0.86])
        self.assertAlmostEqual(float(bare[0]), (0.97 - 0.99 * 0.25) / 0.75)
        self.assertTrue(self.np.isnan(bare[1]))   # fully vegetated ASTER pixel

    def test_qa_water_snow_and_clouds(self):
        em = self.smw.apply_qa_emissivity([0.95, 0.95, 0.95], [0, 1 << 7, 1 << 5])
        self.assertEqual(em.tolist(), [0.95, 0.99, 0.989])
        self.assertEqual(self.smw.cloud_mask([0, 1 << 3, 1 << 4, 1 << 7]).tolist(), [False, True, True, False])


class LstTestMixin:
    """CrossTwin NDVI layers in RD New, and Earth Engine replaced by grid-shaped fake inputs."""

    # 6x6 cells of 10 m whose corners sit on the 30 m grid -> a 2x2 LST grid.
    ORIGIN = (255000, 470070)

    def ndvi_layer(self, values, origin=ORIGIN, day=None):
        from django.contrib.gis.gdal import GDALRaster
        from physicalEnv.models import LandCoverRaster
        raster = GDALRaster({
            "srid": 28992, "width": 6, "height": 6, "origin": origin, "scale": (10, -10),
            "datatype": 6, "bands": [{"data": [v for row in values for v in row], "nodata_value": -9999}],
        })
        with mock.patch("core.rasterOperations.export_raster_to_cog"):
            return LandCoverRaster.objects.create(year=2024, date=day, index="NDVI", raster=raster)

    def west_vegetated_east_bare(self, **kwargs):
        return self.ndvi_layer([[0.86] * 3 + [0.2] * 3] * 6, **kwargs)

    @staticmethod
    def view_around(x0, y0, x1, y1):
        """WGS84 [w, s, e, n] of an RD box."""
        from django.contrib.gis.geos import Polygon
        poly = Polygon.from_bbox((x0, y0, x1, y1))
        poly.srid = 28992
        poly.transform(4326)
        return list(poly.extent)

    @staticmethod
    def scene(scene_id="LC09_197024_20240712", day=12):
        from datetime import datetime, timezone
        from .lst import gee
        return gee.Scene(scene_id, datetime(2024, 7, day, 10, 40, tzinfo=timezone.utc), 3.0,
                         view_coverage=1.0, view_cloud=0.0)

    @staticmethod
    def fake_gee(scenes, qa=None):
        """Patch Earth Engine: `scenes` are found, every scene has uniform inputs (Tb 300 K, TPW 10 mm)."""
        import contextlib
        import numpy as np
        from .lst import gee

        def inputs(sensor, scene, grid):
            full = np.full((grid.height, grid.width), 1.0)
            bands = {
                "B10": full * 300, "QA_PIXEL": full * 0 if qa is None else qa,
                "EM13": full * 0.97, "EM14": full * 0.97,
                "ASTER_NDVI": full * 0.2,   # ASTER FVC 0: bare = ASTER
            }
            return bands, [(full * 10, 0)], gee.TPW_SOURCES[0]

        def export(instance, *args, **kwargs):
            instance.cog_path = f"/nonexistent/lst_{instance.pk}.tif"

        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(gee, "initialize"))
        stack.enter_context(mock.patch.object(gee, "find_scenes", return_value=list(scenes)))
        stack.enter_context(mock.patch.object(
            gee, "get_scene", side_effect=lambda sensor, sid: next(s for s in scenes if s.scene_id == sid)))
        stack.enter_context(mock.patch.object(gee, "fetch_scene_inputs", side_effect=inputs))
        stack.enter_context(mock.patch("core.rasterOperations.export_raster_to_cog", side_effect=export))
        return stack

    @staticmethod
    def expected_lst(em):
        from .lst.coefficients import SMW_COEFFICIENTS
        a, b, c = SMW_COEFFICIENTS["L9"][1]   # TPW 10 mm -> bin 1
        return a * 300 / em + b / em + c - 273.15

    @staticmethod
    def bare_em():
        from .lst.coefficients import ASTER_TO_TIRS
        c13, c14, c0 = ASTER_TO_TIRS
        return c13 * 0.97 + c14 * 0.97 + c0


class CalculateLstPipelineTests(LstTestMixin, TestCase):
    """calculate_lst() with Earth Engine mocked: CrossTwin NDVI in, LandSurfaceTemperature out."""

    def test_lst_is_stored_on_the_ndvi_grid_with_clouds_masked(self):
        import numpy as np
        from .lst.pipeline import NODATA, calculate_lst

        ndvi = self.west_vegetated_east_bare()
        scene = self.scene()
        qa = np.array([[0.0, 0.0], [0.0, 1 << 3]])   # south-east cell cloudy
        with self.fake_gee([scene], qa=qa):
            result = calculate_lst(ndvi=ndvi)

        self.assertEqual((result.grid.width, result.grid.height, result.grid.resolution), (2, 2, 30.0))
        expected = [[self.expected_lst(0.99), self.expected_lst(self.bare_em())],
                    [self.expected_lst(0.99), None]]
        record = result.record
        self.assertEqual(record.date_time, scene.acquired)
        self.assertEqual(record.satellite_type, "Landsat 9")
        self.assertIn(f"NDVI #{ndvi.pk}", record.source)
        record.refresh_from_db()
        band = record.raster.bands[0]
        stored = np.asarray(band.data(), dtype="float64").reshape(2, 2)
        self.assertEqual(band.nodata_value, NODATA)
        self.assertEqual(stored[1, 1], NODATA)
        for (i, j) in [(0, 0), (0, 1), (1, 0)]:
            self.assertAlmostEqual(stored[i, j], expected[i][j], places=3)
        self.assertAlmostEqual(result.valid_fraction, 0.75)

    def test_without_an_ndvi_layer_it_says_what_to_import(self):
        from .lst.pipeline import LSTError, calculate_lst
        with self.assertRaisesMessage(LSTError, "NDVI (Vegetation Index)"):
            calculate_lst()

    def test_the_view_is_clipped_to_the_ndvi_coverage(self):
        from .lst.pipeline import calculate_lst
        ndvi = self.west_vegetated_east_bare()
        view = self.view_around(254000, 469000, 256000, 471000)   # much larger than the layer
        with self.fake_gee([self.scene()]):
            result = calculate_lst(bbox_wgs84=view)
        self.assertEqual(result.grid.extent, (255000, 470010, 255060, 470070))
        self.assertEqual(result.ndvi_layers, [ndvi])
        self.assertAlmostEqual(result.valid_fraction, 1.0)

    def test_a_view_without_ndvi_is_refused(self):
        from .lst.pipeline import LSTError, calculate_lst
        self.west_vegetated_east_bare()
        far_away = self.view_around(230000, 580000, 232000, 582000)   # Groningen
        with self.assertRaisesMessage(LSTError, "No NDVI layer in this view"):
            calculate_lst(bbox_wgs84=far_away)

    def test_recalculating_a_scene_replaces_the_rows_it_covers(self):
        from .models import LandSurfaceTemperature
        from .lst.pipeline import calculate_lst
        self.west_vegetated_east_bare()
        view = self.view_around(254000, 469000, 256000, 471000)
        july, august = self.scene(), self.scene("LC09_197024_20240828", day=28)
        with self.fake_gee([july, august]):
            first = calculate_lst(bbox_wgs84=view, scene_id=july.scene_id)
            other_scene = calculate_lst(bbox_wgs84=view, scene_id=august.scene_id)
            again = calculate_lst(bbox_wgs84=view, scene_id=july.scene_id)
        self.assertEqual(other_scene.replaced, [])
        self.assertEqual(again.replaced, [first.record.pk])
        self.assertEqual(
            set(LandSurfaceTemperature.objects.values_list("pk", flat=True)),
            {other_scene.record.pk, again.record.pk},
        )

    def test_overlapping_ndvi_layers_are_merged_newest_first(self):
        from datetime import datetime, timezone
        from .lst.grid import Grid
        from .lst.pipeline import ndvi_mosaic
        older = self.ndvi_layer([[0.86] * 6] * 6, day=datetime(2024, 6, 1, tzinfo=timezone.utc))
        # Newer layer only over the western 30 m column.
        newer = self.ndvi_layer([[0.2] * 3 + [-9999] * 3] * 6, day=datetime(2024, 7, 1, tzinfo=timezone.utc))
        grid = Grid.covering(28992, 255000, 470010, 255060, 470070, 30)
        mosaic = ndvi_mosaic([newer, older], grid)
        self.assertEqual(mosaic.round(6).tolist(), [[0.2, 0.86], [0.2, 0.86]])

    def test_a_too_large_area_is_refused_before_downloading(self):
        from .lst import gee
        from .lst.grid import Grid
        with self.assertRaisesMessage(gee.GEEError, "Zoom in"):
            gee.check_download_size(Grid(28992, 0, 0, 30.0, 2000, 2000))


class LstToolViewTests(LstTestMixin, TestCase):
    """The map's LST tool endpoints (urban_heat/lst/views.py)."""

    def setUp(self):
        self.west_vegetated_east_bare()
        self.view = ",".join(f"{v:.6f}" for v in self.view_around(254000, 469000, 256000, 471000))

    def login_staff(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client.force_login(user)

    def test_scenes_lists_the_view_grid_and_scenes(self):
        with self.fake_gee([self.scene()]):
            response = self.client.get("/urban_heat/lst/scenes/", {"bbox": self.view})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["grid"], {"width": 2, "height": 2, "resolution": 30.0})
        self.assertEqual([s["id"] for s in data["scenes"]], ["LC09_197024_20240712"])
        self.assertEqual(data["scenes"][0]["view_clear"], 1.0)
        self.assertFalse(data["can_calculate"])

    def test_a_bad_bbox_is_a_400(self):
        response = self.client.get("/urban_heat/lst/scenes/", {"bbox": "5,52,4,53"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("bbox", response.json()["error"])

    def test_calculating_needs_a_staff_login(self):
        response = self.client.post("/urban_heat/lst/calculate/", {"bbox": self.view})
        self.assertEqual(response.status_code, 403)

    def test_calculate_returns_the_new_map_layer(self):
        self.login_staff()
        scene = self.scene()
        with self.fake_gee([scene]):
            response = self.client.post("/urban_heat/lst/calculate/", {"bbox": self.view, "scene": scene.scene_id})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["layer"]["key"], f"raster-urban_heat-LandSurfaceTemperature-{data['id']}")
        self.assertEqual(data["layer"]["layer_type"], "raster")
        self.assertEqual(data["replaced"], [])
        self.assertAlmostEqual(data["stats"]["max"], self.expected_lst(self.bare_em()), places=3)
