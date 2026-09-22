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
        export = mock.patch("core.signals.export_raster_to_cog")
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
