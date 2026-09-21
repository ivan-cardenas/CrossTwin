from unittest import mock

import geopandas as gpd
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.test import SimpleTestCase, TestCase
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

    def test_existing_datasets_are_unaffected_by_the_new_options(self):
        # CBS_Housing has no __value_scales__/__value_maps__/region_field: still RegioS
        from importer.external_catalog import FIELD_MAPPINGS
        self.assertNotIn("__value_scales__", FIELD_MAPPINGS["CBS_Housing"])
        self.assertNotIn("region_field", CATALOG_BY_KEY["CBS_Housing"]["params"])
