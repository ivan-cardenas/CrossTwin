from unittest import mock

import geopandas as gpd
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from shapely.geometry import Polygon as ShapelyPolygon

from administrative.models import Province

from .external_catalog import CATALOG_BY_KEY
from .external_data import CBSImporter, _import_geojson_features
from .utils import to_storage_srid
from .views import _generic_import, _to_multipolygon

RD = settings.COORDINATE_SYSTEM

# ~6.8 km x ~5.6 km box over Amsterdam: about 38 km2 on the ground. Stored in
# degrees the area would be 0.005, so the area alone tells the two apart.
AMS_LONLAT = [(4.85, 52.35), (4.95, 52.35), (4.95, 52.40), (4.85, 52.40), (4.85, 52.35)]
AMS_AREA_KM2 = (30, 45)


def _wgs84_frame(polygon_type=ShapelyPolygon, crs="EPSG:4326"):
    return gpd.GeoDataFrame({"name": ["x"]}, geometry=[polygon_type(AMS_LONLAT)], crs=crs)


class ToStorageSridTests(SimpleTestCase):
    def test_wgs84_polygon_is_reprojected(self):
        geom = to_storage_srid(Polygon(AMS_LONLAT, srid=4326))
        self.assertEqual(geom.srid, RD)
        self.assertTrue(30 < geom.area / 1e6 < 45, geom.area)

    def test_declared_source_overrides_geojson_default_srid(self):
        # GeoJSON parsing labels everything 4326, whatever the coordinates are
        rd_point = GEOSGeometry('{"type": "Point", "coordinates": [121000, 487000]}')
        self.assertEqual(rd_point.srid, 4326)
        out = to_storage_srid(rd_point, RD)
        self.assertEqual(out.srid, RD)
        self.assertEqual(out.coords, (121000, 487000))  # untouched, not re-transformed

    def test_missing_crs_is_refused(self):
        with self.assertRaises(ValueError):
            to_storage_srid(Polygon(AMS_LONLAT))  # no srid, no source_srid

    def test_multi_wrapper_drops_srid_unless_passed(self):
        # Documents the Django behaviour the importers work around
        poly = to_storage_srid(Polygon(AMS_LONLAT, srid=4326))
        self.assertIsNone(MultiPolygon(poly).srid)
        self.assertEqual(MultiPolygon(poly, srid=poly.srid).srid, RD)

    def test_to_multipolygon_keeps_srid(self):
        poly = to_storage_srid(Polygon(AMS_LONLAT, srid=4326))
        self.assertEqual(_to_multipolygon(poly).srid, RD)


class GenericImportStorageCrsTests(TestCase):
    """_generic_import must store every geometry in COORDINATE_SYSTEM."""

    def _import(self, gdf):
        return _generic_import(gdf, "administrative.Province", {}, dry_run=False)

    def _stored(self):
        province = Province.objects.get()
        self.assertEqual(province.geom.srid, RD)
        return province

    def test_wgs84_upload_is_stored_in_rd(self):
        report = self._import(_wgs84_frame())
        self.assertEqual(report["errors"], 0, report["sample_errors"])
        province = self._stored()
        self.assertTrue(AMS_AREA_KM2[0] < province.area_km2 < AMS_AREA_KM2[1], province.area_km2)

    def test_web_mercator_upload_is_stored_in_rd(self):
        report = self._import(_wgs84_frame().to_crs(3857))
        self.assertEqual(report["errors"], 0, report["sample_errors"])
        # Web Mercator inflates areas by ~1/cos(lat)^2 (~2.7x here); if it had
        # been stored unconverted the area would be far outside this range.
        province = self._stored()
        self.assertTrue(AMS_AREA_KM2[0] < province.area_km2 < AMS_AREA_KM2[1], province.area_km2)

    def test_rd_upload_is_unchanged(self):
        gdf = _wgs84_frame().to_crs(RD)
        report = self._import(gdf)
        self.assertEqual(report["errors"], 0, report["sample_errors"])
        stored = self._stored().geom
        self.assertAlmostEqual(stored.centroid.x, gdf.geometry.iloc[0].centroid.x, places=3)

    def test_no_crs_is_refused_not_guessed(self):
        gdf = _wgs84_frame()
        gdf.crs = None
        with self.assertRaises(ValueError):
            self._import(gdf)
        self.assertEqual(Province.objects.count(), 0)


class GeoJsonFeatureImportStorageCrsTests(TestCase):
    """PDOK/OGC feature imports honour the requested srsName but store in RD."""

    MAPPING = {"__geometry__": "geom"}

    def _feature(self, coords):
        return {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [coords]}}

    def _run(self, feature, srs_name):
        dataset = {"key": "test", "params": {"srsName": srs_name}}
        created, updated, errors = _import_geojson_features([feature], dataset, Province, self.MAPPING)
        self.assertEqual(errors, [])
        self.assertEqual(created, 1)
        province = Province.objects.get()
        self.assertEqual(province.geom.srid, RD)
        return province

    def test_wgs84_srsname_is_reprojected(self):
        province = self._run(self._feature([list(p) for p in AMS_LONLAT]), "EPSG:4326")
        self.assertTrue(AMS_AREA_KM2[0] < province.area_km2 < AMS_AREA_KM2[1], province.area_km2)

    def test_rd_srsname_is_kept(self):
        rd = _wgs84_frame().to_crs(RD).geometry.iloc[0]
        province = self._run(self._feature([list(p) for p in rd.exterior.coords]), f"EPSG:{RD}")
        self.assertTrue(AMS_AREA_KM2[0] < province.area_km2 < AMS_AREA_KM2[1], province.area_km2)


class CBSPopulationForecastImportTests(TestCase):
    """CBS 85173NED: region column RegioIndeling2021, x 1000 scale, forecast variants."""

    def setUp(self):
        from watersupply.tests.factories import make_city
        self.city = make_city(id=153, cityName="Enschede")  # City.pk is the gemeente number
        self.dataset = CATALOG_BY_KEY["CBS_PopulationForecast"]
        self.bbox = [6.8, 52.2, 6.95, 52.25]  # WGS84, overlaps the factory city (around 6.9E 52.2N)

    def _rows(self):
        def row(region, variant, period, value, age="10000"):
            return {"RegioIndeling2021": region, "PrognoseInterval": variant,
                    "Leeftijd": age, "Perioden": period, "TotaleBevolking_1": value}
        return [
            row("GM0153", "MW00000", "2030JJ00", 168.9),
            row("GM0153", "MOG0067", "2030JJ00", 160.1),
            row("GM0153", "MBG0067", "2030JJ00", 177.4),
            row("GM0153", "MW00000", "2031JJ00", 169.5),
            row("GM0153", "XX99999", "2030JJ00", 1.0),   # unknown variant: skipped
            row("GM0999", "MW00000", "2030JJ00", 5.0),   # city not in the database: skipped
        ]

    def _fetch(self, rows=None):
        response = mock.Mock()
        response.json.return_value = {"value": rows if rows is not None else self._rows()}
        response.raise_for_status.return_value = None
        with mock.patch("importer.external_data.requests.get", return_value=response) as get:
            result = CBSImporter.fetch(self.dataset, bbox=self.bbox)
        return result, get

    def test_rows_are_scaled_mapped_and_stored_per_city(self):
        from administrative.models import PopulationProjection
        result, _ = self._fetch()
        self.assertEqual(result.status, "success", result.message)
        self.assertEqual(result.records_created, 4)

        stored = {(p.year, p.scenario): p.population for p in PopulationProjection.objects.filter(city=self.city)}
        self.assertEqual(stored, {
            (2030, "prognose"): 168900,   # 168.9 x 1000
            (2030, "low"): 160100,
            (2030, "high"): 177400,
            (2031, "prognose"): 169500,
        })

    def test_request_uses_the_table_specific_region_column_and_age_total(self):
        _, get = self._fetch()
        odata_filter = get.call_args.kwargs["params"]["$filter"]
        self.assertIn("Leeftijd eq '10000'", odata_filter)
        self.assertIn("startswith(RegioIndeling2021,'GM0153')", odata_filter)
        self.assertNotIn("RegioS", odata_filter)

    def test_reimport_updates_instead_of_duplicating(self):
        from administrative.models import PopulationProjection
        self._fetch()
        result, _ = self._fetch()
        self.assertEqual((result.records_created, result.records_updated), (0, 4))
        self.assertEqual(PopulationProjection.objects.count(), 4)

    def test_request_carries_top_but_no_skip_on_the_plain_odata_api(self):
        # CBS's older ODataApi endpoint 500s on an unpaginated request against a large
        # source table even when the filtered result is small, so $top is mandatory --
        # but that same endpoint rejects $skip outright, so it must never be sent
        # unless the catalog entry opts into the newer ODataFeed (params.use_feed).
        _, get = self._fetch()
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["$top"], 10000)
        self.assertNotIn("$skip", params)

    def test_a_full_page_is_not_repaged_without_use_feed(self):
        # Only one request is made, even if the page comes back "full" -- $skip
        # isn't supported here, so a second request would just repeat page one.
        # GM0999 is an unknown city (see _rows()), so these rows are skipped
        # during import without touching the database -- keeps the test fast.
        full_page = [
            {"RegioIndeling2021": "GM0999", "PrognoseInterval": "MW00000",
             "Leeftijd": "10000", "Perioden": "2030JJ00", "TotaleBevolking_1": 100.0}
        ] * 10000
        _, get = self._fetch(rows=full_page)
        self.assertEqual(get.call_count, 1)

    def test_use_feed_datasets_paginate_with_skip(self):
        dataset = {**self.dataset, "params": {**self.dataset["params"], "use_feed": True}}
        full_page = [
            {"RegioIndeling2021": "GM0999", "PrognoseInterval": "MW00000",
             "Leeftijd": "10000", "Perioden": f"{2000 + i}JJ00", "TotaleBevolking_1": 100.0}
            for i in range(10000)
        ]
        response_full = mock.Mock()
        response_full.json.return_value = {"value": full_page}
        response_full.raise_for_status.return_value = None
        response_empty = mock.Mock()
        response_empty.json.return_value = {"value": []}
        response_empty.raise_for_status.return_value = None

        with mock.patch(
            "importer.external_data.requests.get", side_effect=[response_full, response_empty]
        ) as get:
            CBSImporter.fetch(dataset, bbox=self.bbox)

        self.assertEqual(get.call_count, 2)
        skips = [call.kwargs["params"]["$skip"] for call in get.call_args_list]
        self.assertEqual(skips, [0, 10000])

    def test_existing_datasets_are_unaffected_by_the_new_options(self):
        # CBS_Housing has no __value_scales__/__value_maps__/region_field: still RegioS
        from importer.external_catalog import FIELD_MAPPINGS
        self.assertNotIn("__value_scales__", FIELD_MAPPINGS["CBS_Housing"])
        self.assertNotIn("region_field", CATALOG_BY_KEY["CBS_Housing"]["params"])


class AdminAreasGeojsonTests(TestCase):
    """The import map picks its area of interest from the level above the dataset."""

    @classmethod
    def setUpTestData(cls):
        from watersupply.tests.factories import make_city, make_district, make_neighborhood

        cls.city = make_city(cityName="Enschede")
        cls.district = make_district(city=cls.city, districtName="Centrum")
        cls.neighborhood = make_neighborhood(district=cls.district, neighborhoodName="Roombeek")

    def _get(self, level=None):
        url = reverse("importer:admin_areas_geojson")
        return self.client.get(url, {"level": level} if level else {})

    def test_city_level_returns_cities(self):
        features = self._get("city").json()["features"]
        self.assertEqual([f["properties"]["name"] for f in features], ["Enschede"])
        self.assertEqual(features[0]["properties"]["id"], self.city.id)

    def test_district_level_returns_districts(self):
        features = self._get("district").json()["features"]
        self.assertEqual([f["properties"]["name"] for f in features], ["Centrum"])
        self.assertEqual(features[0]["properties"]["id"], self.district.id)

    def test_defaults_to_neighborhoods(self):
        features = self._get().json()["features"]
        self.assertEqual([f["properties"]["name"] for f in features], ["Roombeek"])

    def test_bbox_is_wgs84_west_south_east_north(self):
        west, south, east, north = self._get("city").json()["features"][0]["properties"]["bbox"]
        self.assertTrue(west < east and south < north)
        # The factory square sits around Enschede (~6.9E, 52.2N)
        self.assertTrue(6.5 < west < east < 7.3, (west, east))
        self.assertTrue(52.0 < south < north < 52.5, (south, north))

    def test_unknown_level_is_rejected(self):
        response = self._get("province")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


class AdminBboxSourceCatalogTests(SimpleTestCase):
    def test_districts_pick_bbox_from_cities(self):
        self.assertEqual(CATALOG_BY_KEY["pdok_districts"]["bbox_from"], "administrative.City")

    def test_neighborhoods_pick_bbox_from_districts(self):
        self.assertEqual(CATALOG_BY_KEY["pdok_neighborhoods"]["bbox_from"], "administrative.District")

    def test_bbox_source_matches_prerequisite_model(self):
        # The unit you pick the area from is the one that must already be imported.
        for key in ("pdok_districts", "pdok_neighborhoods"):
            ds = CATALOG_BY_KEY[key]
            self.assertEqual(ds["bbox_from"], ds["requires_model"])


# ---------------------------------------------------------------------------
# KNMI WBGT import
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Just enough of requests.Response for KNMIImporter."""

    def __init__(self, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json = json_data
        self._content = content

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        yield self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _write_grid(path, value=24.0, crs="EPSG:4326", **profile_overrides):
    """Small synthetic grid over the Netherlands standing in for a KNMI file."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_bounds

    profile = dict(
        driver="GTiff", dtype="float32", count=1, width=10, height=8,
        crs=crs, transform=from_bounds(5.0, 52.0, 5.5, 52.4, 10, 8), nodata=-9999.0,
    )
    profile.update(profile_overrides)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(np.full((profile["height"], profile["width"]), value, dtype=profile["dtype"]), 1)
    return path


class KNMIFilenameTests(SimpleTestCase):
    def _parse(self, name):
        from .external_data import KNMIImporter
        return KNMIImporter.parse_valid_time(name)

    def test_minute_precision(self):
        parsed = self._parse("KNMI_WBGT_202609211230.nc")
        self.assertEqual((parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute), (2026, 9, 21, 12, 30))
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)

    def test_separated_iso_style(self):
        parsed = self._parse("wbgt_2026-09-21T13-45.nc")
        self.assertEqual((parsed.hour, parsed.minute), (13, 45))

    def test_hour_only_and_date_only(self):
        self.assertEqual(self._parse("wbgt_2026092114.nc").hour, 14)
        date_only = self._parse("wbgt_20260921.nc")
        self.assertEqual((date_only.hour, date_only.minute), (0, 0))

    def test_no_timestamp(self):
        self.assertIsNone(self._parse("latest.nc"))


class KNMIWbgtCatalogTests(TestCase):
    def test_entry_needs_no_bbox_or_user_credentials(self):
        ds = CATALOG_BY_KEY["knmi_wbgt"]
        self.assertEqual(ds["source"], "knmi")
        self.assertFalse(ds.get("requires_bbox"))
        self.assertFalse(ds.get("requires_auth"))
        self.assertEqual(ds["target_model"], "urban_heat.WetBulbGlobeTemperature")

    def test_model_is_a_registered_raster_so_the_cog_pipeline_covers_it(self):
        from core.utils import RASTER_REGISTRY
        from urban_heat.models import WetBulbGlobeTemperature
        self.assertIn(WetBulbGlobeTemperature, RASTER_REGISTRY.values())

    def test_import_page_lists_knmi_source(self):
        # A source missing from SOURCE_INFO used to raise KeyError while rendering (B19).
        response = self.client.get(reverse("importer:external_data"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wet Bulb Globe Temperature (KNMI, latest)")

    def test_dispatcher_routes_knmi_source(self):
        from .external_data import import_dataset, ImportResult
        with mock.patch("importer.external_data.KNMIImporter.fetch_latest",
                        return_value=ImportResult("success", "ok")) as fetch:
            result = import_dataset("knmi_wbgt")
        fetch.assert_called_once_with(CATALOG_BY_KEY["knmi_wbgt"])
        self.assertEqual(result.status, "success")


class KNMIToGeotiffTests(SimpleTestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name

    def _convert(self, src):
        import rasterio
        from .external_data import KNMIImporter
        dst = f"{self.tmp}/out.tif"
        note = KNMIImporter.to_geotiff(src, dst)
        with rasterio.open(dst) as out:
            return note, out.crs.to_epsg(), out.read(1), out.nodata

    def test_output_is_in_storage_crs(self):
        src = _write_grid(f"{self.tmp}/in.tif", value=24.0)
        _, epsg, data, _ = self._convert(src)
        self.assertEqual(epsg, RD)
        self.assertAlmostEqual(float(data.max()), 24.0, places=3)

    def test_kelvin_with_scale_and_offset_becomes_celsius(self):
        # Packed int16 as some NetCDF products store it: 2975 * 0.1 = 297.5 K = 24.35 C
        import rasterio
        src = _write_grid(f"{self.tmp}/packed.tif", value=2975, dtype="int16", nodata=-32768)
        with rasterio.open(src, "r+") as ds:
            ds.scales = (0.1,)
            ds.offsets = (0.0,)
            ds.units = ("K",)
        _, _, data, nodata = self._convert(src)
        valid = data[data != nodata]
        self.assertGreater(valid.size, 0)
        self.assertAlmostEqual(float(valid.mean()), 24.35, places=1)

    def test_source_nodata_stays_nodata(self):
        import numpy as np
        import rasterio
        src = _write_grid(f"{self.tmp}/holes.tif", value=24.0)
        with rasterio.open(src, "r+") as ds:
            block = np.full((8, 10), 24.0, dtype="float32")
            block[:, :5] = -9999.0  # west half missing
            ds.write(block, 1)
        _, _, data, nodata = self._convert(src)
        self.assertTrue((data == nodata).any())
        self.assertAlmostEqual(float(data[data != nodata].mean()), 24.0, places=3)

    def test_file_without_crs_is_refused(self):
        src = _write_grid(f"{self.tmp}/nocrs.tif", crs=None)
        with self.assertRaisesRegex(ValueError, "coordinate reference system"):
            self._convert(src)


class KNMIWbgtImportTests(TestCase):
    FILENAME = "KNMI_WBGT_202609211200.nc"

    def setUp(self):
        import tempfile
        from django.test import override_settings

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        source = _write_grid(f"{self._tmp.name}/source.tif", value=24.0)
        with open(source, "rb") as fh:
            self.payload = fh.read()

        overrides = override_settings(KNMI_API_KEY="secret-test-key", MEDIA_ROOT=self._tmp.name)
        overrides.enable()
        self.addCleanup(overrides.disable)

        # COG export is exercised by core.signals; here we only check it is triggered.
        # core.signals imports it when the signal fires, so patch it at its source.
        export = mock.patch("core.rasterOperations.export_raster_to_cog")
        self.export = export.start()
        self.addCleanup(export.stop)

        self.dataset = CATALOG_BY_KEY["knmi_wbgt"]
        self.calls = []
        get = mock.patch("importer.external_data.requests.get", side_effect=self._fake_get)
        get.start()
        self.addCleanup(get.stop)

    def _fake_get(self, url, headers=None, **kwargs):
        self.calls.append((url, headers))
        if url.endswith("/files"):
            return _FakeResponse(json_data={"files": [{
                "filename": self.FILENAME, "created": "2026-09-21T12:20:00+00:00",
            }]})
        if url.endswith("/url"):
            return _FakeResponse(json_data={"temporaryDownloadUrl": "https://download.example/signed"})
        return _FakeResponse(content=self.payload)

    def _fetch(self):
        from .external_data import KNMIImporter
        return KNMIImporter.fetch_latest(self.dataset)

    def test_imports_latest_file_into_storage_crs(self):
        from urban_heat.models import WetBulbGlobeTemperature

        result = self._fetch()

        self.assertEqual(result.status, "success", result.message)
        self.assertEqual(WetBulbGlobeTemperature.objects.count(), 1)
        row = WetBulbGlobeTemperature.objects.get()
        self.assertEqual(row.date_time.isoformat(), "2026-09-21T12:00:00+00:00")
        self.assertEqual(row.source, "KNMI Data Platform")
        self.assertEqual(row.measurement_method, "KNMI WBGT analysis")
        self.assertEqual(row.raster.srid, RD)
        self.export.assert_called_once()

    def test_stored_values_survive_the_round_trip(self):
        from django.db import connection
        from urban_heat.models import WetBulbGlobeTemperature

        self._fetch()
        row = WetBulbGlobeTemperature.objects.get()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT (ST_SummaryStats(raster)).mean FROM urban_heat_wetbulbglobetemperature WHERE id = %s",
                [row.id],
            )
            mean = cursor.fetchone()[0]
        self.assertAlmostEqual(mean, 24.0, places=1)

    def test_key_goes_to_the_api_but_not_to_the_presigned_download(self):
        self._fetch()
        api_calls = [c for c in self.calls if "api.dataplatform.knmi.nl" in c[0]]
        download_calls = [c for c in self.calls if "download.example" in c[0]]
        self.assertEqual(len(api_calls), 2)  # list + url
        self.assertTrue(all(h == {"Authorization": "secret-test-key"} for _, h in api_calls))
        self.assertEqual(len(download_calls), 1)
        self.assertIsNone(download_calls[0][1])

    def test_importing_the_same_file_twice_does_not_duplicate_or_redownload(self):
        from urban_heat.models import WetBulbGlobeTemperature

        self._fetch()
        second = self._fetch()

        self.assertEqual(second.status, "success")
        self.assertIn("already imported", second.message)
        self.assertEqual(WetBulbGlobeTemperature.objects.count(), 1)
        self.assertEqual(len([c for c in self.calls if "download.example" in c[0]]), 1)

    def test_missing_api_key_fails_before_any_request(self):
        from django.test import override_settings
        with override_settings(KNMI_API_KEY=None):
            result = self._fetch()
        self.assertEqual(result.status, "error")
        self.assertIn("KNMI_API_KEY", result.message)
        self.assertEqual(self.calls, [])

    def test_rejected_key_is_reported_without_leaking_it(self):
        with mock.patch("importer.external_data.requests.get",
                        return_value=_FakeResponse(status_code=401)):
            result = self._fetch()
        self.assertEqual(result.status, "error")
        self.assertIn("rejected", result.message)
        self.assertNotIn("secret-test-key", result.message)

    def test_empty_listing_is_an_error(self):
        with mock.patch("importer.external_data.requests.get",
                        return_value=_FakeResponse(json_data={"files": []})):
            result = self._fetch()
        self.assertEqual(result.status, "error")
        self.assertIn("no files", result.message)


# ── Import throughput (docs/PERFORMANCE.md §2/§3) ──────────────────────────────

def _rd_square(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))), srid=RD)


def _rd_feature(x0, y0, x1, y1, **props):
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [ring]}}


RD_DATASET = {"key": "test", "params": {"srsName": f"EPSG:{RD}"}}


class SpatialParentIndexTests(SimpleTestCase):
    def setUp(self):
        from types import SimpleNamespace
        from .batching import SpatialParentIndex
        self.west = SimpleNamespace(name="west", geom=_rd_square(0, 0, 1000, 1000))
        self.east = SimpleNamespace(name="east", geom=_rd_square(1000, 0, 2000, 1000))
        self.index = SpatialParentIndex([self.west, self.east])

    def test_feature_is_attributed_to_the_parent_it_lies_in(self):
        self.assertIs(self.index.find(_rd_square(1200, 200, 1400, 400)), self.east)
        self.assertIs(self.index.find(GEOSGeometry("POINT (100 900)", srid=RD)), self.west)

    def test_point_on_a_shared_boundary_still_finds_a_parent(self):
        self.assertIn(self.index.find(GEOSGeometry("POINT (1000 500)", srid=RD)), (self.west, self.east))

    def test_feature_outside_every_parent(self):
        self.assertIsNone(self.index.find(_rd_square(5000, 5000, 5100, 5100)))

    def test_ring_shaped_feature_uses_a_point_on_itself_not_its_centroid(self):
        # A U-shape inside `west` whose centroid falls in the gap, outside the feature.
        u_shape = GEOSGeometry(
            "POLYGON ((100 100, 900 100, 900 900, 700 900, 700 300, 300 300, 300 900, 100 900, 100 100))",
            srid=RD,
        )
        self.assertFalse(u_shape.contains(u_shape.centroid))
        self.assertIs(self.index.find(u_shape), self.west)


class BulkLandCoverImportTests(TestCase):
    """pdok_landcover_brt goes through bulk_create, and the urban-area recompute runs once per city."""

    def setUp(self):
        from administrative.models import City, District, Neighborhood
        from .external_catalog import FIELD_MAPPINGS
        square = _rd_square(0, 0, 1000, 1000)
        province = Province.objects.create(ProvinceName="P", geom=square)
        self.city = City.objects.create(cityName="C", province=province, geom=square)
        district = District.objects.create(id="D1", districtName="D", city=self.city, geom=square, currentPopulation=0)
        self.neighborhood = Neighborhood.objects.create(
            id="N1", neighborhoodName="N", district=district, geom=square, currentPopulation=0)
        self.mapping = FIELD_MAPPINGS["pdok_landcover_brt"]

    def _features(self):
        common = {"observationDate": "2024-05-01T00:00:00Z"}
        return [
            _rd_feature(0, 0, 250, 1000, landCoverObservationClass="urban fabric", **common),   # 0.25 km2
            _rd_feature(250, 0, 500, 1000, landCoverObservationClass="road", **common),         # 0.25 km2
            _rd_feature(500, 0, 1000, 1000, landCoverObservationClass="arable land", **common),  # not urban
        ]

    def test_rows_are_bulk_written_with_parent_percentage_and_one_recompute(self):
        from physicalEnv import signals as landcover_signals
        from physicalEnv.models import LandCoverVector

        with mock.patch.object(landcover_signals, "_recompute_neighborhood_urban_area",
                               wraps=landcover_signals._recompute_neighborhood_urban_area) as recompute:
            created, updated, errors = _import_geojson_features(
                self._features(), RD_DATASET, LandCoverVector, self.mapping)

        self.assertEqual((created, updated, errors), (3, 0, []))
        recompute.assert_called_once_with(self.city.pk)   # not once per polygon

        rows = LandCoverVector.objects.order_by("id")
        self.assertEqual({r.city_id for r in rows}, {self.city.pk})
        self.assertEqual([r.year for r in rows], [2024, 2024, 2024])
        self.assertEqual([round(r.percentage) for r in rows], [25, 25, 50])
        self.neighborhood.refresh_from_db()
        self.assertAlmostEqual(self.neighborhood.urban_area, 0.5)
        self.city.refresh_from_db()
        self.assertAlmostEqual(self.city.urban_area, 0.5)

    def test_parents_are_loaded_without_their_other_columns(self):
        from physicalEnv.models import LandCoverVector
        from .batching import SpatialParentIndex

        loaded = {}
        original = SpatialParentIndex.for_model.__func__

        def spy(cls, ParentModel, extra_fields=()):
            index = original(cls, ParentModel, extra_fields)
            loaded["deferred"] = next(iter(index._entries))[0].get_deferred_fields()
            return index

        with mock.patch.object(SpatialParentIndex, "for_model", classmethod(spy)):
            _import_geojson_features(self._features()[:1], RD_DATASET, LandCoverVector, self.mapping)
        self.assertIn("cityName", loaded["deferred"])
        self.assertNotIn("area_km2", loaded["deferred"])   # read by __percentage_of_parent__


class BulkUpsertImportTests(TestCase):
    """Upserts through INSERT ... ON CONFLICT keep update_or_create's behaviour."""

    MAPPING = {
        "__geometry__": "geom",
        "__unique__": "localId",
        "__unique_field__": "localId",
        "geographicalName": "name",
        "type": "type",
    }

    def _import(self, features):
        from nature.models import WaterBodies
        return _import_geojson_features(features, RD_DATASET, WaterBodies, self.MAPPING)

    def test_reimport_updates_changed_rows_and_creates_new_ones(self):
        from nature.models import WaterBodies

        self.assertEqual(self._import([
            _rd_feature(0, 0, 10, 10, localId="a", geographicalName="Lake A", type="lake"),
            _rd_feature(20, 0, 30, 10, localId="b", geographicalName="Pond B", type="pond"),
        ]), (2, 0, []))

        # "a" comes back renamed and without its optional `type`; "c" is new
        self.assertEqual(self._import([
            _rd_feature(0, 0, 10, 10, localId="a", geographicalName="Lake A (renamed)"),
            _rd_feature(40, 0, 50, 10, localId="c", geographicalName="Canal C", type="canal"),
        ]), (1, 1, []))

        rows = {w.localId: w for w in WaterBodies.objects.all()}
        self.assertEqual(sorted(rows), ["a", "b", "c"])
        self.assertEqual(rows["a"].name, "Lake A (renamed)")
        self.assertEqual(rows["a"].type, "lake")   # a missing property doesn't blank the stored value

    def test_one_bad_row_does_not_lose_the_rest_of_its_batch(self):
        from nature.models import WaterBodies

        created, updated, errors = self._import([
            _rd_feature(0, 0, 10, 10, localId="ok-1", geographicalName="Fine"),
            _rd_feature(20, 0, 30, 10, localId="bad", geographicalName="x" * 300),   # name max_length=200
            _rd_feature(40, 0, 50, 10, localId="ok-2", geographicalName="Also fine"),
        ])
        self.assertEqual((created, updated), (2, 0))
        self.assertEqual(len(errors), 1)
        self.assertEqual(sorted(WaterBodies.objects.values_list("localId", flat=True)), ["ok-1", "ok-2"])

    def test_bulk_writes_invalidate_the_cached_layer(self):
        from core.cache import layer_version
        from nature.models import WaterBodies

        before = layer_version(WaterBodies)
        self._import([_rd_feature(0, 0, 10, 10, localId="a", geographicalName="Lake A")])
        self.assertNotEqual(layer_version(WaterBodies), before)


class BulkImportRegistryTests(SimpleTestCase):
    def test_bulk_models_have_no_save_logic_that_bulk_create_would_skip(self):
        from django.apps import apps
        from django.db import models
        from .batching import BULK_IMPORT_MODELS

        for label in BULK_IMPORT_MODELS:
            with self.subTest(label):
                self.assertIs(apps.get_model(label).save, models.Model.save)

    def test_models_with_save_logic_keep_the_row_path(self):
        from administrative.models import Neighborhood
        from builtup.models import Building
        from .batching import BulkWriter

        self.assertIsNone(BulkWriter.for_model(Building, "id"))
        self.assertIsNone(BulkWriter.for_model(Neighborhood, "id"))


class DeferredCascadeImportTests(TestCase):
    """Neighborhoods saved inside deferred_cascades() cascade once per parent, at the end."""

    def setUp(self):
        from administrative.models import City, District
        square = _rd_square(0, 0, 1000, 1000)
        self.province = Province.objects.create(ProvinceName="P", geom=square)
        self.city = City.objects.create(cityName="C", province=self.province, geom=square)
        self.district = District.objects.create(id="D1", districtName="D", city=self.city, geom=square)

    def test_each_parent_is_recomputed_once_with_the_final_totals(self):
        from administrative import signals as population_signals
        from administrative.models import Neighborhood
        from .batching import deferred_cascades

        with mock.patch.object(population_signals, "_recompute_population",
                               wraps=population_signals._recompute_population) as recompute:
            with deferred_cascades():
                for i, population in enumerate((100, 200, 300)):
                    Neighborhood.objects.create(
                        id=f"N{i}", neighborhoodName=f"N{i}", district=self.district,
                        geom=_rd_square(i * 100, 0, i * 100 + 100, 100), currentPopulation=population)
                self.assertEqual(recompute.call_count, 0)   # nothing until the block ends

        # district, city and province once each, instead of 3 x 3
        self.assertEqual(recompute.call_count, 3)
        for unit in (self.district, self.city, self.province):
            unit.refresh_from_db()
            self.assertEqual(unit.currentPopulation, 600, unit)

    def test_cascade_still_runs_when_the_block_fails(self):
        from administrative.models import Neighborhood
        from .batching import deferred_cascades

        with self.assertRaises(RuntimeError):
            with deferred_cascades():
                Neighborhood.objects.create(
                    id="N1", neighborhoodName="N1", district=self.district,
                    geom=_rd_square(0, 0, 100, 100), currentPopulation=42)
                raise RuntimeError("feed dropped mid-import")
        # the row that was written before the failure is reflected upward
        self.district.refresh_from_db()
        self.assertEqual(self.district.currentPopulation, 42)


# ---------------------------------------------------------------------------
# OpenStreetMap (Overpass)
# ---------------------------------------------------------------------------

def _ll_way(way_id, lonlats, **tags):
    """An Overpass `out geom` way."""
    return {"type": "way", "id": way_id, "tags": tags,
            "geometry": [{"lon": lon, "lat": lat} for lon, lat in lonlats]}


AMS_BBOX = [4.85, 52.35, 4.95, 52.40]   # west, south, east, north
LL_SQUARE = [(4.90, 52.37), (4.91, 52.37), (4.91, 52.38), (4.90, 52.38), (4.90, 52.37)]


class OSMConversionTests(SimpleTestCase):
    def test_query_uses_overpass_bbox_order_and_output_per_geometry(self):
        from .external_data import OSMImporter
        dataset = {"osm_query": ['node["natural"="tree"]']}

        points = OSMImporter.build_query(dataset, AMS_BBOX, as_points=True)
        self.assertIn("[bbox:52.35,4.85,52.4,4.95]", points)   # south, west, north, east
        self.assertIn('node["natural"="tree"];', points)
        self.assertTrue(points.endswith("out center tags;"))
        self.assertTrue(OSMImporter.build_query(dataset, AMS_BBOX, as_points=False).endswith("out geom;"))

    def test_tag_numbers(self):
        from .external_data import OSMImporter
        self.assertEqual(OSMImporter.parse_number("12"), 12.0)
        self.assertEqual(OSMImporter.parse_number("12 m"), 12.0)
        self.assertEqual(OSMImporter.parse_number("7,5"), 7.5)
        self.assertAlmostEqual(OSMImporter.parse_number("40 ft"), 12.192)
        self.assertIsNone(OSMImporter.parse_number("tall"))

    def test_elements_become_features_with_synthesized_properties(self):
        from .external_data import OSMImporter
        elements = [
            {"type": "node", "id": 1, "lat": 52.37, "lon": 4.90, "tags": {"amenity": "clinic", "name": "Kliniek"}},
            {"type": "way", "id": 2, "center": {"lat": 52.38, "lon": 4.91}, "tags": {"railway": "station"}},
            {"type": "node", "id": 3, "lat": 52.37, "lon": 4.90, "tags": {"amenity": "bench"}},   # no class
        ]
        features = OSMImporter.to_geojson_features(elements, CATALOG_BY_KEY["osm_amenities"])

        self.assertEqual([f["properties"]["osm_id"] for f in features], ["osm:node/1", "osm:way/2"])
        clinic, station = (f["properties"] for f in features)
        self.assertEqual((clinic["osm_class"], clinic["osm_subtype"], clinic["osm_name"]),
                         ("hospital", "clinic", "Kliniek"))
        self.assertEqual((station["osm_class"], station["osm_name"]), ("transportNode", "Facility osm:way/2"))
        self.assertEqual(features[1]["geometry"], {"type": "Point", "coordinates": [4.91, 52.38]})

        # polygon targets keep closed ways and drop open ones
        ways = [_ll_way(10, LL_SQUARE), _ll_way(11, LL_SQUARE[:3])]
        kept = OSMImporter.to_geojson_features(ways, {}, polygons_only=True)
        self.assertEqual([f["properties"]["osm_id"] for f in kept], ["osm:way/10"])
        self.assertEqual(kept[0]["geometry"]["type"], "Polygon")

    def test_multipolygon_relation_rings_are_assembled_from_split_ways(self):
        from shapely.geometry import shape
        from .external_data import OSMImporter

        def member(role, coords):
            return {"type": "way", "role": role, "geometry": [{"lon": x, "lat": y} for x, y in coords]}

        # the outer ring is split over two ways; the inner ring cuts a hole
        north = [(4.90, 52.37), (4.90, 52.38), (4.92, 52.38), (4.92, 52.37)]
        south = [(4.92, 52.37), (4.90, 52.37)]
        hole = [(4.905, 52.372), (4.915, 52.372), (4.915, 52.378), (4.905, 52.378), (4.905, 52.372)]
        relation = {
            "type": "relation", "id": 5, "tags": {"type": "multipolygon", "leisure": "park"},
            "members": [member("outer", north), member("outer", south), member("inner", hole)],
        }
        geom = shape(OSMImporter.element_geometry(relation))
        self.assertEqual(geom.geom_type, "Polygon")
        self.assertEqual(len(geom.interiors), 1)
        self.assertAlmostEqual(geom.area, 0.02 * 0.01 - 0.01 * 0.006)


class OSMImportTests(TestCase):
    """End to end through OSMImporter.fetch with Overpass mocked."""

    def setUp(self):
        from administrative.models import City, District, Neighborhood
        area = MultiPolygon(to_storage_srid(Polygon(AMS_LONLAT, srid=4326)), srid=RD)
        province = Province.objects.create(ProvinceName="P", geom=area)
        city = City.objects.create(cityName="C", province=province, geom=area)
        district = District.objects.create(id="D1", districtName="D", city=city, geom=area, currentPopulation=0)
        self.neighborhood = Neighborhood.objects.create(
            id="N1", neighborhoodName="N", district=district, geom=area, currentPopulation=0)

    def _fetch(self, key, elements, remark=None):
        from .external_data import OSMImporter
        body = {"elements": elements}
        if remark:
            body["remark"] = remark
        with mock.patch("importer.external_data.requests.post",
                        return_value=_FakeResponse(json_data=body)) as post:
            result = OSMImporter.fetch(CATALOG_BY_KEY[key], AMS_BBOX)
        return result, post

    def test_trees_are_upserted_with_numeric_tags_and_neighborhood(self):
        from nature.models import Tree
        tree = {"type": "node", "id": 42, "lat": 52.37, "lon": 4.90,
                "tags": {"natural": "tree", "genus": "Tilia", "height": "12 m", "circumference": "n/a"}}

        result, post = self._fetch("osm_trees", [tree])
        self.assertEqual((result.status, result.records_created), ("success", 1), result.message)
        self.assertIn("out center tags;", post.call_args.kwargs["data"]["data"])

        row = Tree.objects.get()
        self.assertEqual((row.sourceID, row.genus, row.height_m), ("osm:node/42", "Tilia", 12.0))
        self.assertIsNone(row.circumference_m)
        self.assertEqual(row.neighborhood_id, self.neighborhood.pk)
        self.assertEqual(row.geom.srid, RD)

        tree["tags"]["height"] = "14"
        result, _ = self._fetch("osm_trees", [tree])
        self.assertEqual((result.records_created, result.records_updated), (0, 1))
        self.assertEqual(Tree.objects.get().height_m, 14.0)

    def test_parks_get_area_from_save_and_feed_the_dashboard_filter(self):
        from builtup.models import Park
        result, post = self._fetch("osm_parks", [_ll_way(7, LL_SQUARE, leisure="park", name="Vondelpark")])

        self.assertEqual(result.status, "success", result.message)
        self.assertIn("out geom;", post.call_args.kwargs["data"]["data"])
        park = Park.objects.get(neighborhood=self.neighborhood)
        self.assertEqual((park.name, park.sourceID), ("Vondelpark", "osm:way/7"))
        self.assertTrue(700_000 < park.area < 800_000, park.area)   # ~680 m x ~1110 m, in m2

    def test_amenities_are_classified_into_facility_types(self):
        from builtup.models import Facility
        elements = [
            {"type": "node", "id": 1, "lat": 52.37, "lon": 4.90, "tags": {"amenity": "kindergarten"}},
            {"type": "node", "id": 2, "lat": 52.38, "lon": 4.91, "tags": {"amenity": "police", "name": "Bureau"}},
        ]
        result, post = self._fetch("osm_amenities", elements)
        self.assertEqual(result.records_created, 2, result.message)
        rows = {f.sourceID: f for f in Facility.objects.all()}
        self.assertEqual((rows["osm:node/1"].type, rows["osm:node/1"].subtype), ("school", "kindergarten"))
        self.assertEqual((rows["osm:node/2"].type, rows["osm:node/2"].name), ("police_station", "Bureau"))

        # only nodes are asked for: no way/relation (or nwr) statements
        query = post.call_args.kwargs["data"]["data"]
        statements = [line.strip() for line in query.splitlines()
                      if line.strip().endswith("];") and not line.startswith("[")]   # skip the settings line
        self.assertEqual(len(statements), 2)
        self.assertTrue(all(s.startswith("node[") for s in statements), statements)

    def test_water_bodies_take_their_type_from_the_water_tag(self):
        from nature.models import WaterBodies
        result, _ = self._fetch("osm_water_bodies", [
            _ll_way(3, LL_SQUARE, natural="water", water="pond"),
            _ll_way(4, LL_SQUARE[:3], natural="water"),   # open way: not an area
        ])
        self.assertEqual(result.records_created, 1, result.message)
        water = WaterBodies.objects.get()
        self.assertEqual((water.localId, water.type, water.name), ("osm:way/3", "pond", "Water body osm:way/3"))

    def test_overpass_runtime_error_is_reported(self):
        result, _ = self._fetch("osm_trees", [], remark="runtime error: Query timed out at line 3")
        self.assertEqual(result.status, "error")
        self.assertIn("smaller area", result.message)

    def test_dispatcher_routes_osm_datasets(self):
        from .external_data import ImportResult, import_dataset
        with mock.patch("importer.external_data.OSMImporter.fetch",
                        return_value=ImportResult("success", "ok")) as fetch:
            import_dataset("osm_parks", AMS_BBOX)
        fetch.assert_called_once_with(CATALOG_BY_KEY["osm_parks"], AMS_BBOX)


# ---------------------------------------------------------------------------
# HILUCS land use / INSPIRE planned land use (ATOM GML)
# ---------------------------------------------------------------------------

HILUCS = "http://inspire.ec.europa.eu/codelist/HILUCSValue/"


class HILUCSHrefTests(SimpleTestCase):
    def test_code_and_label_come_from_the_uri(self):
        from physicalEnv.hilucs import parse_hilucs_href
        self.assertEqual(parse_hilucs_href(HILUCS + "6_3_2_WaterAreasNotInOtherEconomicUse"),
                         ("6.3.2", "water areas not in other economic use"))
        self.assertEqual(parse_hilucs_href(HILUCS + "1_1_Agriculture"), ("1.1", "agriculture"))
        self.assertIsNone(parse_hilucs_href("http://example.org/no-code-here"))
        self.assertIsNone(parse_hilucs_href(None))


class HILUCSTableTests(TestCase):
    def test_migration_loads_the_inspire_codelist(self):
        from physicalEnv.models import HILUCSLandUse
        self.assertEqual(HILUCSLandUse.objects.count(), 98)
        water = HILUCSLandUse.objects.get(code="6.3.2")
        self.assertEqual(water.label, "water areas not in other economic use")
        self.assertEqual(water.description, "Water areas which are not in any other socio-economic use.")


def _pos_list(lonlats):
    # EPSG:4258 GML axis order is lat lon
    return " ".join(f"{lat} {lon}" for lon, lat in lonlats)


def _plu_gml(members):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:plu="http://inspire.ec.europa.eu/schemas/plu/4.0" '
        'xmlns:base="http://inspire.ec.europa.eu/schemas/base/3.3">'
        + "".join(f"<wfs:member>{m}</wfs:member>" for m in members)
        + "</wfs:FeatureCollection>"
    ).encode("utf-8")


def _surface(tag, lonlats, hole=None):
    interior = (f"<gml:interior><gml:LinearRing><gml:posList>{_pos_list(hole)}</gml:posList>"
                f"</gml:LinearRing></gml:interior>") if hole else ""
    return (f"<plu:{tag}><gml:MultiSurface><gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing>"
            f"<gml:posList>{_pos_list(lonlats)}</gml:posList></gml:LinearRing></gml:exterior>{interior}"
            f"</gml:Polygon></gml:surfaceMember></gml:MultiSurface></plu:{tag}>")


def _spatial_plan(gml_id, title, lonlats):
    return (f'<plu:SpatialPlan gml:id="{gml_id}"><plu:inspireId><base:Identifier><base:localId>{gml_id}'
            f'</base:localId></base:Identifier></plu:inspireId>{_surface("extent", lonlats)}'
            f'<plu:officialTitle>{title}</plu:officialTitle><plu:validFrom>2024-03-12</plu:validFrom>'
            f'<plu:planTypeName xlink:href="http://inspireregister.nl/codelijst/PlanTypeNameValue/bestemmingsplan"/>'
            f'</plu:SpatialPlan>')


def _zoning_element(local_id, plan_id, hilucs, lonlats, hole=None):
    return (f'<plu:ZoningElement><plu:inspireId><base:Identifier><base:localId>{local_id}</base:localId>'
            f'</base:Identifier></plu:inspireId>{_surface("geometry", lonlats, hole)}'
            f'<plu:hilucsLandUse xlink:href="{HILUCS}{hilucs}"/>'
            f'<plu:plan xlink:href="#{plan_id}"/></plu:ZoningElement>')


def _ll_box(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


class AtomZoningElementImportTests(TestCase):
    """_import_atom_gml_features turns plu:ZoningElements into ZoningArea rows with a HILUCS zone_type."""

    def setUp(self):
        from administrative.models import City, District, Neighborhood
        area = MultiPolygon(to_storage_srid(Polygon(AMS_LONLAT, srid=4326)), srid=RD)
        province = Province.objects.create(ProvinceName="P", geom=area)
        city = City.objects.create(cityName="C", province=province, geom=area)
        district = District.objects.create(id="D1", districtName="D", city=city, geom=area, currentPopulation=0)
        self.neighborhood = Neighborhood.objects.create(
            id="N1", neighborhoodName="N", district=district, geom=area, currentPopulation=0)

    def _import(self, gml_bytes):
        import io
        from .external_catalog import FIELD_MAPPINGS
        from .external_data import _import_atom_gml_features
        from builtup.models import ZoningArea

        class Raw(io.BytesIO):
            pass

        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.raw = Raw(gml_bytes)
        with mock.patch("importer.external_data.requests.get", return_value=response):
            return _import_atom_gml_features("http://example.org/plu.gml", Polygon.from_bbox(AMS_BBOX),
                                             ZoningArea, FIELD_MAPPINGS["pdok_landcover_kadaster"])

    def test_zoning_elements_get_their_hilucs_class_and_plan(self):
        from builtup.models import ZoningArea
        from physicalEnv.models import HILUCSLandUse

        plan_box = _ll_box(4.89, 52.36, 4.93, 52.39)
        gml = _plu_gml([
            _spatial_plan("NL.IMRO.plan-in", "Bestemmingsplan Centrum", plan_box),
            _spatial_plan("NL.IMRO.plan-out", "Elders", _ll_box(6.0, 52.0, 6.1, 52.1)),
            _zoning_element("NL.IMRO.1", "NL.IMRO.plan-in", "6_3_2_WaterAreasNotInOtherEconomicUse",
                            _ll_box(4.90, 52.37, 4.91, 52.38), hole=_ll_box(4.903, 52.373, 4.905, 52.375)),
            # PDOK's misspelt URI still resolves to the registry's 5.2
            _zoning_element("NL.IMRO.2", "NL.IMRO.plan-in", "5_2_ResidentialUseWithOtherComptibleUses",
                            _ll_box(4.91, 52.37, 4.92, 52.38)),
            _zoning_element("NL.IMRO.3", "NL.IMRO.plan-out", "1_1_Agriculture", _ll_box(6.0, 52.0, 6.01, 52.01)),
            "<plu:SupplementaryRegulation><plu:name>skipped</plu:name></plu:SupplementaryRegulation>",
        ])

        created, errors = self._import(gml)

        self.assertEqual((created, errors), (2, []))
        self.assertEqual(HILUCSLandUse.objects.count(), 98)   # no row added for the misspelt URI
        water, mixed = ZoningArea.objects.order_by("id")
        self.assertEqual(water.zone_type.code, "6.3.2")
        self.assertEqual(water.zone_type.label, "water areas not in other economic use")
        self.assertEqual(mixed.zone_type.code, "5.2")
        self.assertEqual((water.description, water.plan_type, str(water.valid_from)),
                         ("Bestemmingsplan Centrum", "bestemmingsplan", "2024-03-12"))
        self.assertEqual(water.neighborhood_id, self.neighborhood.pk)
        self.assertEqual(len(water.geom[0]), 2)   # exterior + hole
        self.assertLess(water.area, mixed.area)

    def test_unknown_code_is_added_with_a_label_from_the_uri(self):
        from builtup.models import ZoningArea
        gml = _plu_gml([
            _spatial_plan("P", "Plan", _ll_box(4.89, 52.36, 4.93, 52.39)),
            _zoning_element("Z", "P", "9_9_SomeFutureLandUse", _ll_box(4.90, 52.37, 4.91, 52.38)),
        ])
        self.assertEqual(self._import(gml), (1, []))
        zone_type = ZoningArea.objects.get().zone_type
        self.assertEqual((zone_type.code, zone_type.label, zone_type.description),
                         ("9.9", "some future land use", ""))


# ---------------------------------------------------------------------------
# Soil map (BIS Nederland WFS)
# ---------------------------------------------------------------------------

class SoilMapImportTests(TestCase):
    """bodemdata_soil_map: polygons upsert on maparea_id and share one SoilType per code + name."""

    def _import(self, features):
        from physicalEnv.models import SoilArea
        from .external_catalog import FIELD_MAPPINGS
        return _import_geojson_features(features, RD_DATASET, SoilArea, FIELD_MAPPINGS["bodemdata_soil_map"])

    @staticmethod
    def _soil(x0, maparea_id, code, name, unit=None, unit_name="Veldpodzolgronden"):
        return _rd_feature(x0, 0, x0 + 10, 10, maparea_id=maparea_id, soilcode=code,
                           normal_soilprofile_name=name, first_soilcode=unit or code,
                           first_soilname=unit_name)

    def test_soil_type_stores_its_legend_unit(self):
        """first_soilcode/name fill SoilType.unitCode/unitName, also on a soil
        type imported before the fields existed."""
        from physicalEnv.models import SoilType
        sand = "Veldpodzolgronden; leemarm en zwak lemig fijn zand"
        SoilType.objects.create(code="kHn21", name=sand)   # unitCode empty
        _created, _updated, errors = self._import([
            self._soil(0, "m1", "kHn21", sand, unit="Hn21"),
            self._soil(20, "m2", "Hn21/Hd21", sand, unit="Hn21"),
        ])
        self.assertEqual(errors, [])
        self.assertEqual(
            set(SoilType.objects.values_list("code", "unitCode", "unitName")),
            {("kHn21", "Hn21", "Veldpodzolgronden"), ("Hn21/Hd21", "Hn21", "Veldpodzolgronden")},
        )

    def test_soil_types_are_shared_and_classified(self):
        from physicalEnv.models import SoilArea, SoilType
        sand = "Veldpodzolgronden; leemarm en zwak lemig fijn zand"
        created, updated, errors = self._import([
            self._soil(0, "m1", "Hn21", sand),
            self._soil(20, "m2", "Hn21", sand),
            # one code, two names in the 2025 map: two soil types
            self._soil(40, "m3", "zVp", "Meerveengronden op zand met humuspodzol, beginnend ondieper dan 1.2 m"),
            self._soil(60, "m4", "zVp", "Veenafbraakgebied"),
        ])
        self.assertEqual((created, updated, errors), (4, 0, []))
        self.assertEqual(SoilType.objects.count(), 3)
        self.assertEqual(SoilType.objects.get(code="Hn21").areas.count(), 2)
        self.assertEqual(set(SoilType.objects.values_list("soilGroup", flat=True)), {"A", "D"})

        # re-import updates on maparea_id
        created, updated, errors = self._import([self._soil(0, "m1", "Hn21", sand)])
        self.assertEqual((created, updated), (0, 1))
        self.assertEqual(SoilArea.objects.count(), 4)

    def test_polygon_without_soil_code_is_skipped(self):
        from physicalEnv.models import SoilArea
        feature = _rd_feature(0, 0, 10, 10, maparea_id="m1", normal_soilprofile_name="x")
        created, _updated, errors = self._import([feature])
        self.assertEqual(created, 0)
        self.assertEqual(len(errors), 1)
        self.assertFalse(SoilArea.objects.exists())

    def test_catalog_entry_targets_the_soil_layer(self):
        dataset = CATALOG_BY_KEY["bodemdata_soil_map"]
        self.assertEqual((dataset["source"], dataset["format"], dataset["layer"]),
                         ("bodemdata", "wfs", "bodem:Bodemkaart50000_v2025"))
        with mock.patch("importer.external_data.PDOKImporter.fetch_wfs") as fetch:
            from .external_data import import_dataset
            import_dataset("bodemdata_soil_map", AMS_BBOX)
        fetch.assert_called_once_with(dataset, AMS_BBOX)


# ---------------------------------------------------------------------------
# Groundwater depth (BIS Nederland WCS)
# ---------------------------------------------------------------------------

def _ghg_tiff_bytes(value=40):
    """A small uint8 GeoTIFF in RD New, as BIS Nederland's WCS returns it."""
    import numpy as np
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", width=4, height=4, count=1, dtype="uint8", crs="EPSG:28992",
                      transform=from_origin(256000, 471000, 50, 50), nodata=255) as dst:
            dst.write(np.full((1, 4, 4), value, dtype="uint8"))
        return mem.read()


class GroundwaterDepthImportTests(TestCase):
    def setUp(self):
        # fetch_wcs writes its downloads under MEDIA_ROOT; keep them out of the real imports/
        import tempfile
        from django.test import override_settings
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        media = override_settings(MEDIA_ROOT=tmp.name)
        media.enable()
        self.addCleanup(media.disable)

    def _fetch(self, key, value=40):
        from .external_data import PDOKImporter
        response = _FakeResponse(content=_ghg_tiff_bytes(value))
        response.content = response._content
        with mock.patch("importer.external_data.requests.get", return_value=response) as get, \
                mock.patch("core.rasterOperations.export_raster_to_cog"):
            result = PDOKImporter.fetch_wcs(CATALOG_BY_KEY[key], [6.89, 52.21, 6.90, 52.22])
        return result, get

    def test_subset_uses_the_coverage_axis_labels(self):
        result, get = self._fetch("bodemdata_ghg")
        self.assertEqual(result.status, "success", result.message)
        subset = get.call_args.kwargs["params"]["subset"]
        self.assertTrue(subset[0].startswith("X(") and subset[1].startswith("Y("), subset)
        self.assertEqual(get.call_args.kwargs["params"]["CoverageId"], "bodem__ghg-mediaan")

    def test_each_statistic_keeps_its_own_row(self):
        from physicalEnv.models import GroundwaterDepth
        self._fetch("bodemdata_ghg", value=40)
        self._fetch("bodemdata_glg", value=120)
        self._fetch("bodemdata_ghg", value=45)   # re-import updates the GHG row

        rows = {g.statistic: g for g in GroundwaterDepth.objects.all()}
        self.assertEqual(sorted(rows), ["GHG", "GLG"])
        self.assertEqual(rows["GHG"].depth_raster.bands[0].data()[0][0], 45)
        self.assertEqual(rows["GLG"].depth_raster.bands[0].data()[0][0], 120)
        self.assertEqual(rows["GHG"].source, "BIS Nederland (WUR)")

    def test_pdok_wcs_keeps_lowercase_axes(self):
        self.assertNotIn("wcs_axis_labels", CATALOG_BY_KEY["pdok_dem_ahn_raster"])
