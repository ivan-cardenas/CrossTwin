from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from .models import City, District, Neighborhood, Province


def _square(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))))


class UrbanAreaCascadeTests(TestCase):
    """urban_area cascades Neighborhood -> District -> City -> Province the
    same way currentPopulation does -- see administrative/signals.py's
    generalized _recompute_population()."""

    def setUp(self):
        square = _square(0, 0, 1000, 1000)
        self.province = Province.objects.create(ProvinceName="P", geom=square)
        self.city = City.objects.create(cityName="C", province=self.province, geom=square)
        self.district = District.objects.create(
            id="D1", districtName="D", city=self.city, geom=square, currentPopulation=0
        )
        self.neighborhood = Neighborhood.objects.create(
            id="N1", neighborhoodName="N", district=self.district, geom=square, currentPopulation=0
        )

    def test_urban_area_cascades_up_to_province(self):
        self.neighborhood.urban_area = 0.5
        self.neighborhood.save()

        self.district.refresh_from_db()
        self.city.refresh_from_db()
        self.province.refresh_from_db()

        self.assertEqual(self.district.urban_area, 0.5)
        self.assertEqual(self.city.urban_area, 0.5)
        self.assertEqual(self.province.urban_area, 0.5)

    def test_urban_area_is_none_when_no_child_has_a_value(self):
        # Distinct from population, where "no data" still sums to 0 -- see
        # the comment in _recompute_population().
        self.neighborhood.save()  # urban_area left unset (None)

        self.district.refresh_from_db()
        self.assertIsNone(self.district.urban_area)
