"""Vegetation coverage of the heat panel: green area clipped to the unit."""
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from administrative.models import City, District, Neighborhood, Province
from builtup.models import Park
from physicalEnv.models import LandCoverClasses, LandCoverVector

from .calculations import calculate_green_area, calculate_vegetation_coverage


def _square(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))))


class GreenAreaIsClippedToTheUnitTests(TestCase):
    """A 2 km x 1 km city split into a west and an east neighborhood of 1 km²."""

    def setUp(self):
        wide = _square(0, 0, 2000, 1000)
        self.province = Province.objects.create(ProvinceName="P", geom=wide)
        self.city = City.objects.create(cityName="C", province=self.province, geom=wide)
        district = District.objects.create(
            id="D1", districtName="D", city=self.city, geom=wide, currentPopulation=0)
        self.west = Neighborhood.objects.create(
            id="W", neighborhoodName="W", district=district,
            geom=_square(0, 0, 1000, 1000), currentPopulation=0)
        self.east = Neighborhood.objects.create(
            id="E", neighborhoodName="E", district=district,
            geom=_square(1000, 0, 2000, 1000), currentPopulation=0)
        self.forest = LandCoverClasses.objects.create(class_name="Broad-leaved forest", description="t")
        self.arable = LandCoverClasses.objects.create(class_name="Arable land", description="t")

    def _landcover(self, cls, geom, year=2024, percentage=0.0):
        return LandCoverVector.objects.create(
            city=self.city, year=year, land_cover_type=cls, land_use="x",
            geom=geom, percentage=percentage)

    def test_a_polygon_crossing_the_boundary_counts_only_inside(self):
        # 1.5 km² of forest, x 500–2000; its stored share of the province (75 %)
        # used to be applied to the neighborhood's 1 km² as 0.75 km².
        self._landcover(self.forest, _square(500, 0, 2000, 1000), percentage=75.0)
        self.west.refresh_from_db()
        self.east.refresh_from_db()

        self.assertAlmostEqual(calculate_green_area(self.west)['green_lc_km2'], 0.5, places=3)
        self.assertAlmostEqual(calculate_green_area(self.east)['green_lc_km2'], 1.0, places=3)
        self.assertEqual(calculate_vegetation_coverage(self.west)['vegetation_coverage_pct'], 50.0)
        self.assertEqual(calculate_vegetation_coverage(self.east)['vegetation_coverage_pct'], 100.0)

    def test_coverage_cannot_exceed_the_unit_through_stored_percentages(self):
        # Two polygons whose province shares add up to 140 %: the old sum gave 140 %.
        self._landcover(self.forest, _square(0, 0, 500, 1000), percentage=70.0)
        self._landcover(self.forest, _square(500, 0, 1000, 1000), percentage=70.0)
        self.west.refresh_from_db()

        self.assertEqual(calculate_vegetation_coverage(self.west)['vegetation_coverage_pct'], 100.0)

    def test_only_green_classes_of_the_latest_year_count(self):
        self._landcover(self.forest, _square(0, 0, 1000, 1000), year=2018)   # superseded
        self._landcover(self.arable, _square(0, 0, 1000, 1000))              # not green
        self._landcover(self.forest, _square(0, 0, 250, 1000))               # 0.25 km²
        self.west.refresh_from_db()

        self.assertAlmostEqual(calculate_green_area(self.west)['green_lc_km2'], 0.25, places=3)

    def test_parks_are_clipped_too(self):
        # 200 m x 100 m park straddling the W/E boundary: 0.01 km² on each side.
        Park.objects.create(name="Border park", area=0, geom=_square(900, 0, 1100, 100))
        self.west.refresh_from_db()

        green = calculate_green_area(self.west)
        self.assertAlmostEqual(green['park_area_km2'], 0.01, places=4)
        self.assertAlmostEqual(green['total_green_km2'], 0.01, places=4)

    def test_a_park_inside_green_land_cover_counts_once(self):
        # 0.25 km² forest with a 0.04 km² park inside it: 0.25 km² of green, not 0.29.
        self._landcover(self.forest, _square(0, 0, 500, 500))
        Park.objects.create(name="Forest park", area=0, geom=_square(100, 100, 300, 300))
        self.west.refresh_from_db()

        green = calculate_green_area(self.west)
        self.assertAlmostEqual(green['total_green_km2'], 0.25, places=4)
        self.assertAlmostEqual(green['park_area_km2'], 0.04, places=4)
        self.assertAlmostEqual(green['green_lc_km2'], 0.21, places=4)  # green outside the park
        self.assertEqual(calculate_vegetation_coverage(self.west)['vegetation_coverage_pct'], 25.0)

    def test_overlapping_parks_count_once(self):
        # Two 0.04 km² parks sharing half their area (e.g. duplicate OSM ways): 0.06 km².
        Park.objects.create(name="A", area=0, geom=_square(0, 0, 200, 200))
        Park.objects.create(name="B", area=0, geom=_square(100, 0, 300, 200))
        self.west.refresh_from_db()

        green = calculate_green_area(self.west)
        self.assertAlmostEqual(green['park_area_km2'], 0.06, places=4)
        self.assertAlmostEqual(green['total_green_km2'], 0.06, places=4)
        self.assertEqual(green['green_lc_km2'], 0.0)

    def test_a_park_partly_outside_green_land_cover_adds_only_its_outside_part(self):
        # Forest x 0–500, park x 400–600: 0.05 km² + 0.02 km² of park beyond the forest.
        self._landcover(self.forest, _square(0, 0, 500, 100))
        Park.objects.create(name="Edge park", area=0, geom=_square(400, 0, 600, 100))
        self.west.refresh_from_db()

        green = calculate_green_area(self.west)
        self.assertAlmostEqual(green['total_green_km2'], 0.06, places=4)
        self.assertAlmostEqual(green['park_area_km2'], 0.02, places=4)
        self.assertAlmostEqual(green['green_lc_km2'], 0.04, places=4)

    def test_without_green_area_everything_is_zero(self):
        self.west.refresh_from_db()
        self.assertEqual(
            calculate_vegetation_coverage(self.west),
            {'park_area_km2': 0.0, 'green_lc_km2': 0.0, 'total_green_km2': 0.0,
             'vegetation_coverage_pct': 0.0},
        )
