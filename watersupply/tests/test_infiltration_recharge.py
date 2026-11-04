"""
Stored LandCover/Soil_Type -> Infiltration -> Available_FW and
Meteorology -> Available_FW: AvailableFreshWater derives its infiltration
rate, yearly recharge depth and yield from the soil map, land cover and a
year of daily KNMI rain and reference ET, and is refreshed when they change.
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import SimpleTestCase, TestCase

from physicalEnv.models import LandCoverClasses, LandCoverVector, SoilArea, SoilType
from physicalEnv.soil import impervious_fraction, weighted_infiltration_rate_mm_h
from watersupply import signals
from watersupply.chain import recharge_depth_cm_yr
from watersupply.models import AvailableFreshWater
from weather.knmi import parse_knmi, rain_mm, select_stations, store_daily
from weather.models import Meteorology, WeatherStation

from .factories import make_city, make_polygon

X0, Y0 = 256500.0, 469500.0   # south-west corner of make_polygon()'s 1 km² square
BBOX = [6.85, 52.20, 6.93, 52.24]   # around make_polygon() (Enschede), WGS84
SAND = "Vlakvaaggronden; leemarm en zwak lemig fijn zand"


def _box(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))))


def knmi_csv(year, days=None, rh=20, ev24=10, stations=((290, 6.891, 52.274, 34.8, "Twenthe"),)):
    """A KNMI daggegevens answer: every day of `year` (or the first `days`) with RH/EV24 in 0.1 mm."""
    lines = ["# STN         LON(east)   LAT(north)  ALT(m)      NAME"]
    lines += [f"# {stn}  {lon}  {lat}  {alt}  {name}" for stn, lon, lat, alt, name in stations]
    lines += ["# ", "# STN,YYYYMMDD,   RH, EV24", "# "]
    day, end = date(year, 1, 1), date(year, 12, 31)
    count = 0
    while day <= end and (days is None or count < days):
        for stn, *_ in stations:
            lines.append(f"  {stn},{day:%Y%m%d},   {rh},   {ev24}")
        day += timedelta(days=1)
        count += 1
    return "\n".join(lines) + "\n"


class PureEquationTests(SimpleTestCase):
    def test_rate_of_unsealed_sand_is_group_a(self):
        self.assertAlmostEqual(weighted_infiltration_rate_mm_h([("A", "pastures", 1e6)]), 7.6)

    def test_sealed_share_lowers_the_rate(self):
        self.assertAlmostEqual(impervious_fraction("Continuous urban fabric"), 0.85)
        self.assertAlmostEqual(
            weighted_infiltration_rate_mm_h([("A", "Continuous urban fabric", 1e6)]), 7.6 * 0.15)

    def test_rate_is_area_weighted_and_skips_unknown_groups(self):
        rate = weighted_infiltration_rate_mm_h([("A", "pastures", 1.0), ("D", "pastures", 3.0), (None, "x", 9.0)])
        self.assertAlmostEqual(rate, (7.6 + 3 * 0.65) / 4)
        self.assertIsNone(weighted_infiltration_rate_mm_h([(None, "pastures", 1.0)]))

    def test_recharge_without_runoff_is_rain_minus_et(self):
        # 2 mm/day never exceeds the initial abstraction of sandy pasture (CN 39): no runoff
        self.assertAlmostEqual(recharge_depth_cm_yr([2.0] * 365, 365.0, [("A", "pastures", 1.0)]), 36.5)

    def test_runoff_reduces_recharge(self):
        rain = [30.0] * 20
        pasture = recharge_depth_cm_yr(rain, 0, [("A", "pastures", 1.0)])
        paved = recharge_depth_cm_yr(rain, 0, [("D", "Continuous urban fabric", 1.0)])
        self.assertLess(paved, pasture)
        self.assertEqual(recharge_depth_cm_yr(rain, 0, [("A", "Water bodies", 1.0)]), 0.0)

    def test_dry_year_gives_zero_and_unknown_cover_none(self):
        self.assertEqual(recharge_depth_cm_yr([1.0] * 100, 500.0, [("A", "pastures", 1.0)]), 0.0)
        self.assertIsNone(recharge_depth_cm_yr([5.0], 0, [("A", "no such cover", 1.0)]))


class KnmiParserTests(SimpleTestCase):
    def test_daily_csv(self):
        stations, rows = parse_knmi(knmi_csv(2024, days=2))
        self.assertEqual(stations[290], (6.891, 52.274, 34.8, "Twenthe"))
        self.assertEqual(rows[0], {"STN": 290, "YYYYMMDD": 20240101, "RH": 20, "EV24": 10})

    def test_trace_rain_is_zero(self):
        self.assertEqual(rain_mm(-1), 0.0)
        self.assertEqual(rain_mm(25), 2.5)

    def test_stations_near_the_bbox_else_the_nearest(self):
        stations = {290: (6.891, 52.274, 0, "Twenthe"), 260: (5.18, 52.10, 0, "De Bilt")}
        self.assertEqual(select_stations(stations, BBOX), [290])
        self.assertEqual(select_stations({260: stations[260]}, BBOX), [260])


class SourceDerivationTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Soilville")
        self.sand = SoilType.objects.create(code="Zn21", name=SAND)
        SoilArea.objects.create(mapAreaID="a", soil_type=self.sand, geom=_box(X0, Y0, X0 + 1000, Y0 + 1000))
        self.pastures = LandCoverClasses.objects.create(class_name="pastures", description="test")
        LandCoverVector.objects.create(city=self.city, year=2024, land_cover_type=self.pastures, land_use="x",
                                       geom=_box(X0, Y0, X0 + 1000, Y0 + 1000), percentage=100)

    def make_source(self, **kwargs):
        return AvailableFreshWater.objects.create(SourceName="Src", geom=make_polygon(), **kwargs)

    def test_rate_is_derived_from_soil_and_land_cover(self):
        source = self.make_source(infiltrationRate_cm_h=99.0)
        self.assertAlmostEqual(source.infiltrationRate_cm_h, 0.76)

    def test_new_land_cover_refreshes_the_rate(self):
        source = self.make_source()
        urban = LandCoverClasses.objects.create(class_name="Continuous urban fabric", description="test")
        LandCoverVector.objects.create(city=self.city, year=2025, land_cover_type=urban, land_use="x",
                                       geom=_box(X0, Y0, X0 + 1000, Y0 + 1000), percentage=100)
        source.refresh_from_db()
        self.assertAlmostEqual(source.infiltrationRate_cm_h, round(0.76 * 0.15, 4))

    def test_without_soil_data_the_stored_rate_is_kept(self):
        source = self.make_source()
        SoilArea.objects.all().delete()
        source.refresh_from_db()
        self.assertAlmostEqual(source.infiltrationRate_cm_h, 0.76)

    def test_without_meteorology_a_supplied_depth_is_kept(self):
        source = self.make_source(infiltrationDepth_cm=30.0)
        self.assertEqual(source.infiltrationDepth_cm, 30.0)
        self.assertAlmostEqual(source.yield_Mm3_year, 0.3)

    def test_daily_import_sets_depth_and_yield(self):
        source = self.make_source(infiltrationDepth_cm=30.0)
        store_daily(knmi_csv(2024), BBOX)   # 366 days x (2 mm rain - 1 mm ET), no runoff on sandy pasture
        source.refresh_from_db()
        self.assertAlmostEqual(source.infiltrationDepth_cm, 36.6)
        self.assertAlmostEqual(source.yield_Mm3_year, 0.366)
        station = WeatherStation.objects.get(knmi_id=290)
        self.assertEqual(Meteorology.objects.filter(station=station).count(), 366)

    def test_incomplete_year_keeps_the_depth(self):
        source = self.make_source(infiltrationDepth_cm=30.0)
        store_daily(knmi_csv(2024, days=100), BBOX)
        source.refresh_from_db()
        self.assertEqual(source.infiltrationDepth_cm, 30.0)

    def test_pinned_recharge_year(self):
        store_daily(knmi_csv(2023, rh=30), BBOX)
        store_daily(knmi_csv(2024), BBOX)
        latest = self.make_source()
        pinned = self.make_source(recharge_year=2023)
        self.assertAlmostEqual(latest.infiltrationDepth_cm, 36.6)
        self.assertAlmostEqual(pinned.infiltrationDepth_cm, 365 * 2 / 10)   # (3 - 1) mm x 365 days

    def test_editing_one_daily_row_refreshes_the_source(self):
        store_daily(knmi_csv(2024), BBOX)
        source = self.make_source()
        row = Meteorology.objects.filter(station__knmi_id=290).first()
        row.reference_et_mm += 10.0
        row.save()
        source.refresh_from_db()
        self.assertAlmostEqual(source.infiltrationDepth_cm, 35.6)


class FreshwaterDeferralTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Soilville")
        sand = SoilType.objects.create(code="Zn21", name=SAND)
        SoilArea.objects.create(mapAreaID="a", soil_type=sand, geom=_box(X0, Y0, X0 + 1000, Y0 + 1000))
        self.pastures = LandCoverClasses.objects.create(class_name="pastures", description="test")
        self.source = AvailableFreshWater.objects.create(SourceName="Src", geom=make_polygon())

    def _freshwater_resaves(self, resave):
        return [c for c in resave.call_args_list
                if getattr(getattr(c.args[0], "model", None), "__name__", "") == "AvailableFreshWater"]

    def test_bulk_land_cover_refreshes_each_source_once(self):
        with mock.patch.object(signals, "_resave", wraps=signals._resave) as resave:
            with signals.deferred_water_refresh():
                for i in range(3):
                    LandCoverVector.objects.create(
                        city=self.city, year=2024, land_cover_type=self.pastures, land_use="x",
                        geom=_box(X0 + i * 300, Y0, X0 + i * 300 + 300, Y0 + 1000), percentage=30)
        self.assertEqual(len(self._freshwater_resaves(resave)), 1)
        self.source.refresh_from_db()
        self.assertAlmostEqual(self.source.infiltrationRate_cm_h, 0.76)

    def test_bulk_writer_finalizer_replays_the_refresh(self):
        from importer.batching import BULK_IMPORT_MODELS

        rows = [LandCoverVector(city=self.city, year=2024, land_cover_type=self.pastures, land_use="x",
                                geom=_box(X0, Y0, X0 + 1000, Y0 + 1000), percentage=100)]
        LandCoverVector.objects.bulk_create(rows)   # no post_save
        BULK_IMPORT_MODELS["physicalEnv.LandCoverVector"](rows)
        self.source.refresh_from_db()
        self.assertAlmostEqual(self.source.infiltrationRate_cm_h, 0.76)


class KnmiDailyCatalogTests(TestCase):
    def test_dispatcher_routes_the_daily_entry(self):
        from importer.external_catalog import CATALOG_BY_KEY
        from importer.external_data import ImportResult, import_dataset

        with mock.patch("importer.external_data.KNMIImporter.fetch_daily",
                        return_value=ImportResult("success", "ok")) as fetch:
            import_dataset("knmi_daily_water_balance", BBOX, "2024-01-01", "2024-12-31")
        fetch.assert_called_once_with(CATALOG_BY_KEY["knmi_daily_water_balance"], BBOX, "2024-01-01", "2024-12-31")

    def test_import_stores_rows_from_the_knmi_answer(self):
        from importer.external_catalog import CATALOG_BY_KEY
        from importer.external_data import KNMIImporter

        with mock.patch("weather.knmi.fetch_daily", return_value=knmi_csv(2024, days=3)):
            result = KNMIImporter.fetch_daily(CATALOG_BY_KEY["knmi_daily_water_balance"], BBOX,
                                              "2024-01-01", "2024-01-03")
        self.assertEqual(result.status, "success", result.message)
        self.assertEqual(Meteorology.objects.count(), 3)
