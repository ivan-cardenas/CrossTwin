"""
DAG edge CityArea -> Network (partial): the city's urban land cover outside
the pipe network's service area is stored on its CoverageWaterSupply records
and follows land-cover (urban growth) and pipe changes.
"""
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import LineString, MultiLineString
from django.test import TestCase

from importer.batching import deferred_cascades
from physicalEnv.models import LandCoverClasses, LandCoverVector
from watersupply import signals
from watersupply.models import CoverageWaterSupply, PipeNetwork

from .factories import make_neighborhood, make_polygon

RD = settings.COORDINATE_SYSTEM
X, Y = 257000.0, 470000.0   # centre of the factory neighborhood / city (1 km square)


class UrbanAreaOutsideNetworkTests(TestCase):
    def setUp(self):
        self.city = make_neighborhood().district.city
        self.urban = LandCoverClasses.objects.create(class_name="Urban fabric", description="test")
        self.pasture = LandCoverClasses.objects.create(class_name="pastures", description="test")
        # 400 m x 400 m of urban fabric (0.16 km²) and a pasture that never counts
        self._landcover(make_polygon(X, Y, 200))
        self._landcover(make_polygon(X + 400, Y + 400, 50), cls=self.pasture)

    def _landcover(self, geom, year=2024, cls=None):
        return LandCoverVector.objects.create(city=self.city, year=year, land_cover_type=cls or self.urban,
                                              land_use="test", geom=geom)

    def _pipe(self, y=Y + 200):
        # along the urban square's north edge: a 50 m buffer covers 400 m x 50 m of it
        line = LineString((X - 400, y), (X + 400, y), srid=RD)
        return PipeNetwork.objects.create(geom=MultiLineString(line, srid=RD), length_km=0)

    def _coverage(self, year=2025):
        return CoverageWaterSupply.objects.create(city=self.city, year=year, buffer_m=50,
                                                  coveredArea_km2=0, coveragePCT=0)

    def _stored(self, year=2025):
        return CoverageWaterSupply.objects.get(city=self.city, year=year)

    def test_urban_area_outside_the_service_area_is_stored(self):
        self._pipe()
        record = self._coverage()
        self.assertEqual(record.urban_landcover_year, 2024)
        self.assertAlmostEqual(record.urban_area_km2, 0.16)
        self.assertAlmostEqual(record.uncovered_urban_km2, 0.14)
        self.assertAlmostEqual(record.uncovered_urban_pct, 87.5)

    def test_without_a_network_all_urban_area_is_uncovered(self):
        record = self._coverage()
        self.assertAlmostEqual(record.uncovered_urban_km2, 0.16)
        self.assertEqual(record.uncovered_urban_pct, 100.0)

    def test_urban_growth_refreshes_the_coverage(self):
        self._pipe()
        self._coverage()
        growth = self._landcover(make_polygon(X, Y - 400, 100))      # 0.04 km², far from the pipe
        self.assertAlmostEqual(self._stored().urban_area_km2, 0.20)
        self.assertAlmostEqual(self._stored().uncovered_urban_km2, 0.18)
        growth.delete()
        self.assertAlmostEqual(self._stored().uncovered_urban_km2, 0.14)

    def test_a_pipe_into_the_new_district_shrinks_the_gap(self):
        self._coverage()
        self._pipe(y=Y)                                                # through the middle: 100 m strip
        self.assertAlmostEqual(self._stored().uncovered_urban_km2, 0.12)

    def test_a_record_uses_the_land_cover_of_its_year(self):
        self._landcover(make_polygon(X, Y - 400, 100), year=2026)     # growth mapped later
        self.assertAlmostEqual(self._coverage(year=2025).urban_area_km2, 0.16)
        record = self._coverage(year=2026)
        self.assertEqual(record.urban_landcover_year, 2026)
        self.assertAlmostEqual(record.urban_area_km2, 0.04)

    def test_without_land_cover_the_fields_stay_empty(self):
        LandCoverVector.objects.all().delete()
        record = self._coverage()
        self.assertIsNone(record.urban_area_km2)
        self.assertIsNone(record.uncovered_urban_km2)

    def test_a_land_cover_import_refreshes_the_coverage_once(self):
        self._coverage()
        with mock.patch.object(signals, '_resave', wraps=signals._resave) as resave:
            with deferred_cascades():
                for i in range(4):
                    self._landcover(make_polygon(X - 300 + i * 150, Y - 400, 50))
        saved = [obj for call in resave.call_args_list for obj in call.args[0]
                 if isinstance(obj, CoverageWaterSupply)]
        self.assertEqual(len(saved), 1)
        self.assertAlmostEqual(self._stored().urban_area_km2, 0.20)
