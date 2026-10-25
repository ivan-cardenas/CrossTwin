from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from django.urls import reverse

from physicalEnv.models import LandCoverClasses, LandCoverVector, SoilArea, SoilType
from physicalEnv.soil import scs_runoff_mm

from .factories import make_city

HX = {'HTTP_HX_REQUEST': 'true'}
X0, Y0 = 256500.0, 469500.0   # south-west corner of make_polygon()'s 1 km² square


def _box(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))))


class InfiltrationIndicatorTests(TestCase):
    """The water dashboard's infiltration card follows soil x land cover and the rain slider."""

    def setUp(self):
        self.city = make_city(cityName="Soilville")
        sand = SoilType.objects.create(code="Zn21", name="Vlakvaaggronden; leemarm en zwak lemig fijn zand")
        SoilArea.objects.create(mapAreaID="a", soil_type=sand, geom=_box(X0, Y0, X0 + 1000, Y0 + 1000))
        pastures = LandCoverClasses.objects.create(class_name="pastures", description="test")
        LandCoverVector.objects.create(city=self.city, year=2024, land_cover_type=pastures, land_use="x",
                                       geom=_box(X0, Y0, X0 + 1000, Y0 + 1000), percentage=100)

    def water(self, view='water_indicators', **params):
        url = reverse(f'watersupply:{view}', args=['city', 'Soilville', 2030])
        return self.client.get(url, params, **HX)

    def test_rain_slider_drives_the_scs_infiltration(self):
        light = self.water('recalculate_indicators', consumption=100, rain_mm=25).context['indicators']
        heavy = self.water('recalculate_indicators', consumption=100, rain_mm=100).context['indicators']

        self.assertEqual(light['curve_number'], 39.0)                 # pastures on group A
        self.assertEqual(light['infiltration_pct'], 100.0)            # 25 mm < Ia = 79.4 mm
        expected = round((1 - scs_runoff_mm(100, 39) / 100) * 100, 1)
        self.assertEqual(heavy['infiltration_pct'], expected)
        self.assertLess(heavy['infiltration_pct'], 100)
        self.assertEqual(heavy['runoff_m3'], round(scs_runoff_mm(100, 39) / 1000 * 1e6))
        self.assertEqual(heavy['soil_groups'][0]['group'], 'A')

    def test_panel_carries_both_sliders(self):
        response = self.water()
        self.assertContains(response, 'id="rain-slider"')
        # consumption slider, rain slider and season switch all send all three values
        self.assertContains(response, 'hx-include="#consumption-slider, #rain-slider, input[name=season]:checked"', count=3)
        self.assertEqual(response.context['indicators']['rain_mm'], 25)

    def test_invalid_rain_falls_back_to_the_default(self):
        indicators = self.water('recalculate_indicators', rain_mm='lots').context['indicators']
        self.assertEqual(indicators['rain_mm'], 25)

    def test_unit_without_soil_map_says_what_to_import(self):
        SoilArea.objects.all().delete()
        response = self.water()
        self.assertIsNone(response.context['indicators']['infiltration_pct'])
        self.assertContains(response, 'import the Soil Map')


class GroundwaterSeasonTests(TestCase):
    """The season switch picks GHG (wet) or GLG (dry) for the shallow-groundwater rule."""

    def setUp(self):
        from unittest import mock
        from django.contrib.gis.gdal import GDALRaster
        from physicalEnv.models import GroundwaterDepth

        self.city = make_city(cityName="Wetville")
        sand = SoilType.objects.create(code="Zn21", name="Vlakvaaggronden; leemarm en zwak lemig fijn zand")
        SoilArea.objects.create(mapAreaID="a", soil_type=sand, geom=_box(X0, Y0, X0 + 1000, Y0 + 1000))
        pastures = LandCoverClasses.objects.create(class_name="pastures", description="test")
        LandCoverVector.objects.create(city=self.city, year=2024, land_cover_type=pastures, land_use="x",
                                       geom=_box(X0, Y0, X0 + 1000, Y0 + 1000), percentage=100)
        for statistic, depth_cm in (("GHG", 30), ("GLG", 150)):   # wet: shallow, dry: deep
            raster = GDALRaster({
                "srid": 28992, "width": 20, "height": 20, "origin": (X0, Y0 + 1000), "scale": (50, -50),
                "datatype": 1, "bands": [{"data": [depth_cm] * 400, "nodata_value": 255}],
            })
            with mock.patch("core.rasterOperations.export_raster_to_cog"):
                GroundwaterDepth.objects.create(year=2025, statistic=statistic, depth_raster=raster)

    def recalc(self, **params):
        url = reverse('watersupply:recalculate_indicators', args=['city', 'Wetville', 2030])
        return self.client.get(url, {'consumption': 100, 'rain_mm': 50, **params}, **HX).context['indicators']

    def test_wet_season_waterlogs_the_sand_and_dry_season_does_not(self):
        wet, dry = self.recalc(season='wet'), self.recalc(season='dry')
        self.assertEqual((wet['curve_number'], wet['shallow_groundwater_pct'], wet['groundwater_statistic']), (80.0, 100.0, 'GHG'))
        self.assertEqual((dry['curve_number'], dry['shallow_groundwater_pct'], dry['groundwater_statistic']), (39.0, 0, 'GLG'))
        self.assertLess(wet['infiltration_pct'], dry['infiltration_pct'])

    def test_wet_is_the_default_and_unknown_seasons_fall_back_to_it(self):
        self.assertEqual(self.recalc()['season'], 'wet')
        self.assertEqual(self.recalc(season='monsoon')['season'], 'wet')

    def test_panel_renders_the_switch_and_every_control_sends_the_season(self):
        url = reverse('watersupply:water_indicators', args=['city', 'Wetville', 2030])
        response = self.client.get(url, {'season': 'dry'}, **HX)
        self.assertContains(response, 'class="season-switch"')
        self.assertContains(response, 'value="dry" checked')
        self.assertContains(response, 'input[name=season]:checked', count=3)
