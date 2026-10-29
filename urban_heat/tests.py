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


# ── SOLWEIG thermal comfort (urban_heat/solweig/) ─────────────────────

KNMI_SAMPLE = """# STN         LON(east)   LAT(north)  ALT(m)      NAME
# 260         5.180       52.100      1.90        De Bilt
# 290         6.891       52.274      34.80       Twenthe Airport
# 283         6.657       52.069      29.10       Hupsel
#
# STN,YYYYMMDD,HH,    T,    U,   FF,   DD,    Q,    P
  260,20250715,   13,  250,   40,   30,  240,  250,10170
  283,20250715,   13,  205,   55,   40,  250,  150,10172
  290,20250715,   13,     ,   63,   50,  290,  161,10174
  260,20250715,   14,  310,   35,   30,  240,  280,10168
  283,20250715,   14,  230,   50,   20,  250,  250,10170
"""


class SolweigMetTests(SimpleTestCase):
    def test_write_umep_puts_the_values_in_solweigs_columns(self):
        import os
        import tempfile
        from datetime import datetime
        from zoneinfo import ZoneInfo

        import numpy as np

        from .solweig.met import Met, write_umep

        met = Met(ta_c=28.5, rh_pct=45, wind_ms=2.5, wind_dir_deg=240, kdown_wm2=750, pressure_kpa=101.2)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "met.txt")
            write_umep(met, datetime(2025, 7, 15, 0, tzinfo=ZoneInfo("Europe/Amsterdam")), path)
            rows = np.loadtxt(path, skiprows=1, delimiter=" ")   # as solweig_gpu reads it
        self.assertEqual(rows.shape, (2, 24))
        self.assertEqual(list(rows[0, :4]), [2025, 195, 23, 0])   # the hour before, previous day
        self.assertEqual(list(rows[1, :4]), [2025, 196, 0, 0])
        self.assertEqual([rows[1, i] for i in (9, 10, 11, 12, 14, 23)], [2.5, 45, 28.5, 101.2, 750, 240])
        self.assertEqual(rows[1, 21], -999)

    def test_knmi_picks_the_nearest_station_with_data_and_converts_units(self):
        from datetime import datetime, timezone

        from .solweig import met

        response = mock.Mock(text=KNMI_SAMPLE, raise_for_status=lambda: None)
        with mock.patch("requests.post", return_value=response) as post:
            values, station = met.knmi_hourly(datetime(2025, 7, 15, 13, tzinfo=timezone.utc), 6.89, 52.22)
        self.assertEqual((post.call_args.kwargs["data"]["start"], post.call_args.kwargs["data"]["end"]),
                         ("2025071501", "2025071524"))           # the whole day, for PET's UHI
        # Twenthe (290) is closest but has no temperature: Hupsel (283) is next.
        self.assertEqual(station["id"], 283)
        self.assertEqual((values.ta_c, values.rh_pct, values.wind_ms, values.wind_dir_deg), (20.5, 55.0, 4.0, 250.0))
        self.assertAlmostEqual(values.kdown_wm2, 416.7)          # 150 J/cm2 per hour
        self.assertAlmostEqual(values.pressure_kpa, 101.72)
        # The day of the same station (hours 13 and 14), not De Bilt's.
        self.assertEqual((values.tmax_c, values.tmin_c, values.wind_day_ms), (23.0, 20.5, 3.0))
        self.assertAlmostEqual(values.kdown_day_wm2, 555.6)       # mean of 150 and 250 J/cm2 per hour
        self.assertEqual(values.day_values(), (23.0, 20.5, 555.6, 3.0))

    def test_knmi_midnight_is_hour_24_of_the_previous_day(self):
        from datetime import datetime, timezone

        from .solweig.met import _knmi_hour

        self.assertEqual(_knmi_hour(datetime(2025, 7, 16, 0, tzinfo=timezone.utc)), ("20250715", 24))

    def test_era5_conversions(self):
        from .solweig.met import era5_from_values, wind_from

        values = era5_from_values({
            "temperature_2m": 300.15, "dewpoint_temperature_2m": 300.15, "surface_pressure": 101300,
            "u_component_of_wind_10m": 0.0, "v_component_of_wind_10m": -3.0,
            "surface_solar_radiation_downwards": 3600 * 500,
        })
        self.assertEqual((values.ta_c, values.rh_pct, values.wind_ms, values.kdown_wm2, values.pressure_kpa),
                         (27.0, 100.0, 3.0, 500.0, 101.3))
        self.assertEqual(values.wind_dir_deg, 0.0)                # v < 0: wind from the north
        self.assertAlmostEqual(wind_from(3.0, 0.0)[1], 270.0)     # u > 0: from the west

    def test_era5_day_conversions(self):
        from .solweig.met import Met, era5_day_from_values

        day = era5_day_from_values({"tmax": 303.15, "tmin": 288.15, "ssrd": 3600 * 250, "wind": 3.5})
        self.assertEqual(day, {"tmax_c": 30.0, "tmin_c": 15.0, "kdown_day_wm2": 250.0, "wind_day_ms": 3.5})
        self.assertIsNone(era5_day_from_values({})["tmax_c"])
        self.assertIsNone(Met(ta_c=20, rh_pct=50, wind_ms=2, wind_dir_deg=0, kdown_wm2=0, tmax_c=25).day_values())


class SolweigInputsTests(TestCase):
    def test_land_cover_classes(self):
        from .solweig.inputs import BARE, GRASS, PAVED, WATER, umep_class

        self.assertEqual(umep_class("water bodies"), WATER)
        self.assertEqual(umep_class("pastures"), GRASS)
        self.assertEqual(umep_class("green urban areas"), GRASS)
        self.assertEqual(umep_class("beaches, dunes, sands"), BARE)
        self.assertEqual(umep_class("urban fabric"), PAVED)
        self.assertEqual(umep_class("road and rail networks and associated land"), PAVED)

    def test_build_splits_the_dsm_into_buildings_and_trees(self):
        import numpy as np
        from django.contrib.gis.geos import MultiPolygon, Polygon

        from builtup.models import Building
        from physicalEnv.tests import _stored_dsm

        from .solweig import inputs

        data = np.full((80, 80), 5.0, dtype="float32")
        data[10:20, 10:20] = 25.0      # building, footprint below
        data[50:54, 50:54] = 13.0      # tree (no footprint), 8 m
        data[30:32, 30:32] = 6.0       # 1 m: not a tree
        _stored_dsm(data)
        footprint = Polygon.from_bbox((250010, 469980, 250020, 469990))
        Building.objects.create(id=7, geom=MultiPolygon(footprint, srid=28992))

        p = inputs.plan((250030.0, 469930.0, 250050.0, 469950.0))   # view 20 x 20 m, halo 50 m
        result = inputs.build(p)
        a = result.arrays
        self.assertEqual(result.shape, (80, 80))                  # the window is clipped to the DSM
        self.assertEqual(float(a["Building_DSM"][15, 15]), 25.0)
        self.assertEqual(float(a["Building_DSM"][52, 52]), 5.0)
        self.assertEqual(float(a["Trees"][52, 52]), 8.0)
        self.assertEqual(float(a["Trees"][15, 15]), 0.0)
        self.assertEqual(float(a["Trees"][31, 31]), 0.0)
        self.assertNotIn("Landcover", a)
        self.assertEqual(result.crop, (50, 30, 20, 20))

    def test_a_too_large_view_is_refused(self):
        import numpy as np

        from physicalEnv.tests import _stored_dsm

        from .solweig import inputs

        _stored_dsm(np.zeros((80, 80), dtype="float32"))
        with mock.patch.object(inputs, "MAX_CELLS", 100), self.assertRaisesRegex(inputs.SolweigError, "zoom in"):
            inputs.plan((250030.0, 469930.0, 250050.0, 469950.0))


def _fake_solweig(inputs, met, when_local):
    """Stand-in for SOLWEIG-GPU: Tmrt = Ta + 20, UTCI = Ta + 5 everywhere."""
    import numpy as np

    tmrt = np.full(inputs.shape, met.ta_c + 20.0, dtype="float32")
    return tmrt, np.full(inputs.shape, met.ta_c + 5.0, dtype="float32")


@mock.patch("core.rasterOperations.export_raster_to_cog")
@mock.patch("urban_heat.solweig.pipeline.run_solweig", side_effect=_fake_solweig)
@mock.patch("urban_heat.solweig.pipeline.device", return_value="cpu")
@mock.patch("urban_heat.solweig.pipeline.urban_pet",
            side_effect=lambda inputs, tmrt, met, when: (tmrt - 10.0, "test PET"))
class SolweigPipelineTests(TestCase):
    BBOX = [6.8930, 52.2200, 6.8940, 52.2206]

    def setUp(self):
        import numpy as np

        from physicalEnv.svf import wgs84_to_storage
        from physicalEnv.tests import _stored_dsm

        view = wgs84_to_storage(self.BBOX)
        _stored_dsm(np.full((300, 300), 5.0, dtype="float32"),
                    origin=(float(np.floor(view[0])) - 100, float(np.ceil(view[3])) + 100))

    def _run(self, hour=15, **met):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from physicalEnv.svf import _storage_box, wgs84_to_storage

        from .models import ThermalComfortRun
        from .solweig import pipeline

        values = dict(ta_c=25.0, rh_pct=50.0, wind_ms=2.0, wind_dir_deg=240.0, kdown_wm2=700.0,
                      pressure_kpa=101.3, source="manual")
        values.update(met)
        run = ThermalComfortRun.objects.create(
            area=_storage_box(wgs84_to_storage(self.BBOX)), bbox_wgs84=self.BBOX,
            date_time=datetime(2025, 7, 15, hour, tzinfo=ZoneInfo("Europe/Amsterdam")), met=values, resolution=2.0)
        return pipeline.execute(run.pk)

    def test_stores_tmrt_utci_and_pet_for_the_view(self, *_mocks):
        run = self._run()
        self.assertEqual(run.status, "done", run.message)
        self.assertEqual(run.stats["tmrt"]["mean"], 45.0)
        self.assertEqual(run.stats["utci"]["mean"], 30.0)
        self.assertEqual(run.stats["pet"]["mean"], 35.0)
        self.assertEqual(run.mrt.date_time, run.date_time)
        self.assertTrue(run.mrt.source.startswith("SOLWEIG DSM "))
        self.assertEqual(run.inputs["timezone"], "Europe/Amsterdam")
        self.assertEqual(run.inputs["pet_model"], "test PET")
        self.assertTrue(run.pet.measurement_method.endswith("test PET"))
        x0, _, x1, _ = run.mrt.raster.extent
        vx0, _, vx1, _ = run.area.extent
        self.assertAlmostEqual(x1 - x0, vx1 - vx0, delta=2.0)     # the halo is cropped off

    def test_a_rerun_of_the_same_hour_replaces_the_rows(self, *_mocks):
        from .models import UTCI

        first = self._run()
        second = self._run(ta_c=30.0)
        self.assertEqual(second.stats["replaced"]["utci"], [first.utci_id])
        self.assertEqual(list(UTCI.objects.values_list("pk", flat=True)), [second.utci_id])
        self._run(hour=12)
        self.assertEqual(UTCI.objects.count(), 2)                 # another hour is kept

    def test_a_failure_is_recorded_on_the_run(self, _pet, _device, run_solweig, _cog):
        run_solweig.side_effect = RuntimeError("CUDA out of memory")
        run = self._run()
        self.assertEqual(run.status, "failed")
        self.assertIn("CUDA out of memory", run.message)

    def test_results_older_than_a_building_edit_are_stale(self, *_mocks):
        from physicalEnv.models import DSMEdit
        from physicalEnv.svf import wgs84_to_storage

        from .solweig.pipeline import stale_results

        run = self._run()
        view = wgs84_to_storage(self.BBOX)
        self.assertEqual(stale_results(view)["thermal"], [])
        DSMEdit.objects.create(area=run.area)
        self.assertEqual(stale_results(view)["thermal"], [run.pk])
        self.assertEqual(stale_results((0, 0, 10, 10))["thermal"], [])


class SolweigPetTests(SimpleTestCase):
    """pipeline.urban_pet on a 120 m window: a 15 m building block, grass on the west side."""

    def setUp(self):
        try:
            import pet_adjusted  # noqa: F401
        except ImportError:
            self.skipTest("uv sync --extra solweig")

    def _inputs(self, built=True):
        import numpy as np

        from .solweig.inputs import BUILDING, GRASS, PAVED, Inputs

        shape = (60, 60)
        ground = np.zeros(shape, dtype="float32")
        landcover = np.full(shape, PAVED, dtype="float32")
        landcover[:, :15] = GRASS
        building_dsm = ground.copy()
        if built:
            building_dsm[20:40, 25:45] = 15.0
            landcover[20:40, 25:45] = BUILDING
        arrays = {"Building_DSM": building_dsm, "DEM": ground, "Trees": ground.copy(), "Landcover": landcover}
        return Inputs(origin=(0.0, 120.0), cell=2.0, shape=shape, srid=28992, crop=(0, 0, 60, 60),
                      key="test", arrays=arrays)

    def _met(self, **day):
        from .solweig.met import Met

        return Met(ta_c=25.0, rh_pct=50.0, wind_ms=3.0, wind_dir_deg=240.0, kdown_wm2=0.0, pressure_kpa=101.3, **day)

    def _when(self, month, hour_utc):
        from datetime import datetime, timezone

        return datetime(2025, month, 15, hour_utc, tzinfo=timezone.utc)

    def test_without_the_heat_island_it_is_pet_steady_with_the_1_2_m_wind(self):
        import numpy as np
        from pythermalcomfort.models import pet_steady

        import pet_adjusted

        from .solweig.pipeline import PET_PERSON, urban_pet

        tmrt = np.full((60, 60), 40.0, dtype="float32")
        day = dict(tmax_c=30.0, tmin_c=15.0, kdown_day_wm2=250.0, wind_day_ms=3.0)
        pet, label = urban_pet(self._inputs(built=False), tmrt, self._met(**day), self._when(10, 21))
        self.assertIn("outside April-September", label)
        v = float(pet_adjusted.urban_wind_speed(3.0, 0.0, 0.0, 4.0))   # open terrain
        exact = pet_steady(tdb=25.0, tr=40.0, v=v, rh=50.0, p_atm=1013.0, **PET_PERSON).pet
        self.assertTrue(np.allclose(pet, exact, atol=0.05))

    def test_the_heat_island_warms_pet_in_the_evening(self):
        import numpy as np

        from .solweig.pipeline import urban_pet

        inputs, tmrt = self._inputs(), np.full((60, 60), 30.0, dtype="float32")
        day = dict(tmax_c=30.0, tmin_c=15.0, kdown_day_wm2=250.0, wind_day_ms=3.0)
        urban, label = urban_pet(inputs, tmrt, self._met(**day), self._when(7, 21))
        plain, plain_label = urban_pet(inputs, tmrt, self._met(), self._when(7, 21))
        self.assertEqual(label, "PET urban (Koopmans 2020)")
        self.assertIn("no day values", plain_label)
        self.assertGreater(np.nanmean(urban), np.nanmean(plain) + 0.5)

    def test_roofs_have_no_pet(self):
        import numpy as np

        from .solweig.pipeline import urban_pet

        pet, _ = urban_pet(self._inputs(), np.full((60, 60), 40.0, dtype="float32"), self._met(), self._when(7, 12))
        self.assertTrue(np.isnan(pet[20:40, 25:45]).all())
        self.assertTrue(np.isfinite(pet[:20]).all())


class SolweigViewTests(TestCase):
    def test_calculating_needs_staff(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        self.client.force_login(get_user_model().objects.create_user("viewer", password="x"))
        response = self.client.post(reverse("urban_heat:solweig_calculate"), {"bbox": "6.89,52.22,6.9,52.23"})
        self.assertEqual(response.status_code, 403)

    def test_bad_met_values_are_refused(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        self.client.force_login(get_user_model().objects.create_user("staff", password="x", is_staff=True))
        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=True):
            response = self.client.post(reverse("urban_heat:solweig_calculate"), {
                "bbox": "6.89,52.22,6.9,52.23", "datetime": "2025-07-15T15:00", "ta_c": "25",
                "rh_pct": "150", "wind_ms": "2", "kdown_wm2": "600"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("rh_pct", response.json()["error"])

    def test_info_without_a_dsm_explains_why(self):
        from django.urls import reverse

        response = self.client.get(reverse("urban_heat:solweig_info"),
                                   {"bbox": "6.89,52.22,6.9,52.23", "datetime": "2025-07-15T15:00"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["dsm"])
        self.assertIn("No Digital Surface Model", response.json()["error"])
