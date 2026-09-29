from unittest import mock

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from administrative.models import City, District, Neighborhood, Province
from .models import LandCoverClasses, LandCoverVector


def _square(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))))


class UrbanAreaSourceComputationTests(TestCase):
    """physicalEnv.signals.landcover_changed: Neighborhood.urban_area is
    derived from the PostGIS intersection area between LandCoverVector
    polygons (matching URBAN_AREA_KEYWORDS) and the Neighborhood boundary,
    restricted to the most recent LandCoverVector.year per city."""

    def setUp(self):
        self.full_square = _square(0, 0, 1000, 1000)  # 1 km^2
        self.province = Province.objects.create(ProvinceName="P", geom=self.full_square)
        self.city = City.objects.create(cityName="C", province=self.province, geom=self.full_square)
        self.district = District.objects.create(
            id="D1", districtName="D", city=self.city, geom=self.full_square, currentPopulation=0
        )
        self.neighborhood = Neighborhood.objects.create(
            id="N1", neighborhoodName="N", district=self.district, geom=self.full_square, currentPopulation=0
        )
        self.urban_class = LandCoverClasses.objects.create(
            class_name="Urban fabric, continuous", description="test"
        )
        self.non_urban_class = LandCoverClasses.objects.create(
            class_name="Arable land", description="test"
        )

    def test_qualifying_landcover_sets_neighborhood_urban_area(self):
        half_square = _square(500, 0, 1000, 1000)  # 0.5 km^2, half the neighborhood
        LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.urban_class,
            land_use="Residential", geom=half_square, percentage=50.0,
        )

        self.neighborhood.refresh_from_db()
        self.district.refresh_from_db()
        self.city.refresh_from_db()
        self.province.refresh_from_db()

        self.assertAlmostEqual(self.neighborhood.urban_area, 0.5)
        self.assertAlmostEqual(self.district.urban_area, 0.5)
        self.assertAlmostEqual(self.city.urban_area, 0.5)
        self.assertAlmostEqual(self.province.urban_area, 0.5)

    def test_non_qualifying_category_is_ignored(self):
        LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.non_urban_class,
            land_use="Agriculture", geom=self.full_square, percentage=100.0,
        )

        self.neighborhood.refresh_from_db()
        self.assertEqual(self.neighborhood.urban_area, 0.0)

    def test_only_the_most_recent_year_is_summed(self):
        LandCoverVector.objects.create(
            city=self.city, year=2020, land_cover_type=self.urban_class,
            land_use="Residential", geom=self.full_square, percentage=100.0,
        )
        LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.urban_class,
            land_use="Residential", geom=_square(500, 0, 1000, 1000), percentage=50.0,
        )

        self.neighborhood.refresh_from_db()
        # Only 2024 (0.5 km^2) counts, not 2020 + 2024 (which would be 1.5).
        self.assertAlmostEqual(self.neighborhood.urban_area, 0.5)

    def test_deleting_the_last_row_resets_urban_area_to_zero(self):
        lcv = LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.urban_class,
            land_use="Residential", geom=self.full_square, percentage=100.0,
        )
        self.neighborhood.refresh_from_db()
        self.assertAlmostEqual(self.neighborhood.urban_area, 1.0)

        lcv.delete()

        self.neighborhood.refresh_from_db()
        self.district.refresh_from_db()
        self.city.refresh_from_db()
        self.province.refresh_from_db()
        self.assertEqual(self.neighborhood.urban_area, 0.0)
        self.assertEqual(self.district.urban_area, 0.0)
        self.assertEqual(self.city.urban_area, 0.0)
        self.assertEqual(self.province.urban_area, 0.0)


class UrbanAreaSetBasedUpdateTests(TestCase):
    """The single-statement recompute (docs/PERFORMANCE.md §2): clipping, cascade count, deferral."""

    def setUp(self):
        wide = _square(0, 0, 2000, 1000)
        self.province = Province.objects.create(ProvinceName="P", geom=wide)
        self.city = City.objects.create(cityName="C", province=self.province, geom=wide)
        self.district = District.objects.create(
            id="D1", districtName="D", city=self.city, geom=wide, currentPopulation=0)
        self.west = Neighborhood.objects.create(
            id="W", neighborhoodName="W", district=self.district, geom=_square(0, 0, 1000, 1000), currentPopulation=0)
        self.east = Neighborhood.objects.create(
            id="E", neighborhoodName="E", district=self.district, geom=_square(1000, 0, 2000, 1000), currentPopulation=0)
        self.urban = LandCoverClasses.objects.create(class_name="Railway", description="test")  # 'rail'

    def _landcover(self, geom, year=2024):
        return LandCoverVector.objects.create(
            city=self.city, year=year, land_cover_type=self.urban, land_use="Rail", geom=geom, percentage=0)

    def test_polygon_crossing_a_boundary_is_split_between_neighborhoods(self):
        self._landcover(_square(500, 0, 1500, 1000))    # half in W, half in E
        self._landcover(_square(1600, 0, 1800, 1000))   # entirely inside E: counted unclipped

        self.west.refresh_from_db()
        self.east.refresh_from_db()
        self.district.refresh_from_db()
        self.assertAlmostEqual(self.west.urban_area, 0.5)
        self.assertAlmostEqual(self.east.urban_area, 0.7)
        self.assertAlmostEqual(self.district.urban_area, 1.2)

    def test_each_parent_is_recomputed_once(self):
        from physicalEnv import signals

        with mock.patch.object(signals, "_recompute_population", wraps=signals._recompute_population) as cascade:
            self._landcover(_square(0, 0, 100, 100))
        # one district + the city + the province, not the full chain per district
        self.assertEqual(cascade.call_count, 3)

    def test_deferred_block_recomputes_once_per_city(self):
        from physicalEnv import signals

        with mock.patch.object(signals, "_recompute_neighborhood_urban_area",
                               wraps=signals._recompute_neighborhood_urban_area) as recompute:
            with signals.deferred_urban_area():
                for x in (0, 200, 400, 1200, 1400):
                    self._landcover(_square(x, 0, x + 100, 1000))
                recompute.assert_not_called()
        recompute.assert_called_once_with(self.city.pk)

        self.west.refresh_from_db()
        self.east.refresh_from_db()
        self.assertAlmostEqual(self.west.urban_area, 0.3)
        self.assertAlmostEqual(self.east.urban_area, 0.2)
