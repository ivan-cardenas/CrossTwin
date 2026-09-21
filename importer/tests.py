import geopandas as gpd
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.test import SimpleTestCase, TestCase
from shapely.geometry import Polygon as ShapelyPolygon

from administrative.models import Province

from .external_data import _import_geojson_features
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
