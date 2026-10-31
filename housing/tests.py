from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import TestCase

from administrative.models import PopulationProjection
from builtup.models import Building, Property, ZoningArea
from physicalEnv.models import HILUCSLandUse
from watersupply.tests.factories import make_neighborhood, make_polygon

from . import chain, signals
from .calculations import calculate_zoning
from .models import HouseholdSize, HousingSupplyDemand


class ZoningGroupsTests(TestCase):
    """calculate_zoning groups ZoningArea.zone_type HILUCS codes into the dashboard's four bars."""

    def test_codes_and_their_subcodes_fall_in_their_group(self):
        hood = make_neighborhood()
        for i, code in enumerate(["5", "5.1", "5.2", "3.1.1", "2.1", "6.3.2"]):
            ZoningArea.objects.create(
                neighborhood=hood, zone_type=HILUCSLandUse.objects.get(code=code),
                geom=make_polygon(257000.0 + i * 100, 470000.0, 10),   # 400 m² each
            )

        zoning = calculate_zoning(hood)

        counts = {group: data["count"] for group, data in zoning["by_type"].items()}
        # 5.2 is mixed only; 6.3.2 (water) is in no group but counts in the total
        self.assertEqual(counts, {"residential": 2, "commercial": 1, "industrial": 1, "mixed": 1})
        self.assertAlmostEqual(zoning["total_area_sqm"], 6 * 400)
        self.assertAlmostEqual(zoning["by_type"]["residential"]["area_pct"], 33.3)


class PipelineLandTakeTests(TestCase):
    """calculate_pipeline_land_take: DAG edge New_Units -> LandCover, dashboard only."""

    def setUp(self):
        from physicalEnv.models import LandCoverClasses, LandCoverVector
        self.hood = make_neighborhood()   # 1 km x 1 km around (257000, 470000)
        city = self.hood.district.city
        pasture = LandCoverClasses.objects.create(class_name="pastures", description="test")
        urban = LandCoverClasses.objects.create(class_name="Urban fabric", description="test")
        # west half pasture, east half urban fabric; an older year that must be ignored
        for year in (2018, 2024):
            LandCoverVector.objects.create(city=city, year=year, land_cover_type=pasture, land_use="Agriculture",
                                           geom=make_polygon(256750.0, 470000.0, 250), percentage=50)
        LandCoverVector.objects.create(city=city, year=2024, land_cover_type=urban, land_use="Residential",
                                       geom=make_polygon(257250.0, 470000.0, 250), percentage=50)
        self.LandCoverVector = LandCoverVector

    def _project(self, x, completion, half=50):
        from .models import HousingProject
        return HousingProject.objects.create(
            neighborhood=self.hood, year=2024, year_expected_completion=completion,
            project_name="P", project_description="", project_area=(2 * half) ** 2,
            project_units=100, geom=make_polygon(x, 470000.0, half))

    def test_footprint_split_into_greenfield_and_infill(self):
        from .calculations import calculate_pipeline_land_take
        self._project(257000.0, 2030)          # straddles the boundary: 0.5 ha each side
        self._project(257000.0, 2030, half=25)  # overlaps the first: counted once
        self._project(256600.0, 2020)          # completed: not pipeline
        before = self.LandCoverVector.objects.count()

        take = calculate_pipeline_land_take(self.hood, 2025)

        self.assertAlmostEqual(take["footprint_ha"], 1.0, places=2)
        self.assertAlmostEqual(take["greenfield_ha"], 0.5, places=2)
        self.assertAlmostEqual(take["infill_ha"], 0.5, places=2)
        self.assertAlmostEqual(take["uncovered_ha"], 0.0, places=2)
        self.assertEqual({c["class_name"]: c["urban"] for c in take["by_class"]},
                         {"pastures": False, "Urban fabric": True})
        self.assertEqual(self.LandCoverVector.objects.count(), before)   # writes nothing

    def test_no_pipeline_is_zero(self):
        from .calculations import calculate_pipeline_land_take
        take = calculate_pipeline_land_take(self.hood, 2025)
        self.assertEqual((take["footprint_ha"], take["by_class"]), (0.0, []))


class HouseholdSizeTests(TestCase):
    """HouseholdSize derives persons per home from the two CBS columns."""

    def setUp(self):
        self.city = make_neighborhood().district.city

    def test_average_is_population_over_households(self):
        row = HouseholdSize.objects.create(city=self.city, year=2025, population=100_000, households=48_000)
        self.assertAlmostEqual(row.average_size, 100_000 / 48_000)

    def test_population_comes_from_the_forecast_import(self):
        # only the households are imported; the importer's update_or_create saves with
        # update_fields = the columns it was handed, so the derived ones must be added
        PopulationProjection.objects.create(city=self.city, year=2025, population=110_000)
        row, _ = HouseholdSize.objects.update_or_create(city=self.city, year=2025, defaults={"households": 50_000})
        row.refresh_from_db()
        self.assertEqual(row.population, 110_000)
        self.assertAlmostEqual(row.average_size, 2.2)

    def test_forecast_imported_after_the_households_fills_the_average(self):
        row = HouseholdSize.objects.create(city=self.city, year=2026, households=50_000)
        self.assertIsNone(row.average_size)             # no population for 2026 yet
        PopulationProjection.objects.create(city=self.city, year=2026, population=120_000)
        row.refresh_from_db()
        self.assertAlmostEqual(row.average_size, 2.4)
        PopulationProjection.objects.filter(city=self.city, year=2026).update(population=100_000)
        PopulationProjection.objects.get(city=self.city, year=2026).save()   # a corrected forecast
        row.refresh_from_db()
        self.assertAlmostEqual(row.average_size, 2.0)

    def test_other_forecast_variants_are_not_the_population(self):
        PopulationProjection.objects.create(city=self.city, year=2026, scenario="high", population=999_999)
        row = HouseholdSize.objects.create(city=self.city, year=2026, households=50_000)
        self.assertIsNone(row.population)

    def test_for_year_uses_the_closest_earlier_record(self):
        HouseholdSize.objects.create(city=self.city, year=2020, population=100, households=50)
        HouseholdSize.objects.create(city=self.city, year=2024, population=100, households=40)
        self.assertEqual(HouseholdSize.for_year(self.city, 2022).year, 2020)
        self.assertEqual(HouseholdSize.for_year(self.city, 2030).year, 2024)
        self.assertEqual(HouseholdSize.for_year(self.city, 2010).year, 2020)   # earliest later one


class DemandFollowsPopulationTests(TestCase):
    """DAG edges: Total_Population, Household_Size -> Housing_Demand."""

    def setUp(self):
        self.hood = make_neighborhood()           # currentPopulation 1200: only the imported part
        self.city = self.hood.district.city
        PopulationProjection.objects.create(city=self.city, year=2025, population=100_000)
        HouseholdSize.objects.create(city=self.city, year=2025, households=50_000)   # average 2.0

    def _record(self, year):
        return HousingSupplyDemand.objects.create(city=self.city, year=year, supply_units=45_000)

    def test_demand_uses_the_cbs_population_not_the_imported_neighborhoods(self):
        record = self._record(2025)
        self.assertEqual(record.demand_units, 50_000)   # 100 000 / 2.0, not 1 200 / 2.0

    def test_median_forecast_change_updates_demand(self):
        PopulationProjection.objects.create(city=self.city, year=2030, population=120_000)
        record = self._record(2030)
        self.assertEqual(record.demand_units, 60_000)   # size of 2025 carries forward

        PopulationProjection.objects.filter(city=self.city, year=2030).first().delete()
        PopulationProjection.objects.create(city=self.city, year=2030, population=140_000)
        record.refresh_from_db()
        self.assertEqual(record.demand_units, 70_000)

    def test_other_forecast_variants_do_not_move_the_stored_demand(self):
        PopulationProjection.objects.create(city=self.city, year=2030, population=120_000)
        record = self._record(2030)
        PopulationProjection.objects.create(city=self.city, year=2030, scenario="high", population=999_999)
        record.refresh_from_db()
        self.assertEqual(record.demand_units, 60_000)

    def test_new_household_size_updates_demand(self):
        record = self._record(2025)
        HouseholdSize.objects.filter(city=self.city, year=2025).first().delete()
        HouseholdSize.objects.create(city=self.city, year=2025, households=40_000)
        record.refresh_from_db()
        self.assertEqual(record.demand_units, 40_000)   # 100 000 / 2.5

    def test_city_population_cascade_updates_demand(self):
        # a city without a CBS forecast falls back to the imported population
        PopulationProjection.objects.all().delete()
        self.city.refresh_from_db()   # the cascade writes with update(): the factory's instance is stale
        record = self._record(2026)
        self.assertEqual(record.demand_units, round(self.city.currentPopulation / 2.0))
        self.hood.currentPopulation = 5_000
        self.hood.save()    # Neighborhood -> District -> City cascade announces city_population_changed
        record.refresh_from_db()
        self.assertEqual(record.demand_units, round(5_000 / 2.0))

    def test_without_household_size_a_stored_demand_is_kept(self):
        HouseholdSize.objects.all().delete()
        record = HousingSupplyDemand.objects.create(city=self.city, year=2025, supply_units=1, demand_units=77)
        self.assertEqual(record.demand_units, 77)


class ResidentsTests(TestCase):
    """DAG edge: Household_Size -> Property (each dwelling holds the average)."""

    def setUp(self):
        self.hood = make_neighborhood()
        self.city = self.hood.district.city
        self.building = Building.objects.create(
            id=1, buildingType="residential", geom=make_polygon(257000.0, 470000.0, 20))
        HouseholdSize.objects.create(city=self.city, year=2025, population=100_000, households=50_000)

    def _property(self, usage, dx=0.0):
        return Property.objects.create(
            name="p", grossArea=80, usageFunction=usage,
            geom=Point(257000.0 + dx, 470000.0, srid=settings.COORDINATE_SYSTEM))

    def test_new_dwelling_gets_the_average_and_a_shop_does_not(self):
        dwelling = self._property(["Residential function"])
        shop = self._property(["Shop function"], dx=1.0)
        dwelling.refresh_from_db()
        shop.refresh_from_db()
        self.assertEqual(dwelling.residents, 2.0)
        self.assertIsNone(shop.residents)

    def test_new_household_size_updates_every_dwelling(self):
        dwellings = [self._property(["Residential function"], dx=i) for i in range(3)]
        shop = self._property(["Shop function"], dx=5.0)
        HouseholdSize.objects.create(city=self.city, year=2026, population=100_000, households=40_000)
        self.assertEqual({Property.objects.get(pk=d.pk).residents for d in dwellings}, {2.5})
        self.assertIsNone(Property.objects.get(pk=shop.pk).residents)

    def test_a_dwelling_turned_into_a_shop_loses_its_residents(self):
        prop = self._property(["Residential function"])
        prop.usageFunction = ["Shop function"]
        prop.save()
        prop.refresh_from_db()
        self.assertIsNone(prop.residents)


class DeferralTests(TestCase):
    """Bulk imports refresh a city once (housing.signals.deferred_housing_refresh)."""

    def setUp(self):
        self.city = make_neighborhood().district.city
        HouseholdSize.objects.create(city=self.city, year=2020, population=100, households=50)
        HousingSupplyDemand.objects.create(city=self.city, year=2020, supply_units=1)

    def _save_projections(self):
        for year in range(2030, 2036):
            PopulationProjection.objects.create(city=self.city, year=year, population=1000 + year)

    def test_without_deferral_every_row_refreshes(self):
        with mock.patch.object(signals, '_resave', wraps=signals._resave) as resave:
            self._save_projections()
        self.assertEqual(resave.call_count, 6)

    def test_deferred_refreshes_once_per_city(self):
        with mock.patch.object(signals, '_resave', wraps=signals._resave) as resave:
            with signals.deferred_housing_refresh():
                self._save_projections()
            self.assertEqual(resave.call_count, 1)


class DashboardIsADeviationFromTheBaselineTests(TestCase):
    """The dashboard with default controls equals the stored demand, whatever the import coverage."""

    def setUp(self):
        self.hood = make_neighborhood()
        self.city = self.hood.district.city
        HouseholdSize.objects.create(city=self.city, year=2025, population=100_000, households=50_000)
        HousingSupplyDemand.objects.create(city=self.city, year=2025, supply_units=45_000)

    def _indicators(self, **kwargs):
        from .views import _build_indicators, _get_adminUnit_data
        data = _get_adminUnit_data('city', self.city.cityName, 2025)
        return _build_indicators(data, **kwargs)

    def test_default_controls_equal_the_stored_demand(self):
        ind = self._indicators()
        self.assertEqual(ind['demand_units'], 50_000)
        self.assertEqual(ind['household_size'], 2.0)
        self.assertEqual(ind['deficit'], 5_000)

    def test_slider_scales_demand_without_writing(self):
        ind = self._indicators(household_size_override=2.5)
        self.assertEqual(ind['demand_units'], 40_000)
        self.assertEqual(HousingSupplyDemand.objects.get().demand_units, 50_000)

    def test_what_if_helper(self):
        self.assertEqual(chain.what_if_demand(50_000, 110, 100, 2.0, 2.0), 55_000)     # +10 % population
        self.assertEqual(chain.what_if_demand(0, 100_000, 100_000, 2.0, 2.5), 40_000)  # no stored demand
        self.assertEqual(chain.what_if_demand(70, 1, 1, None, None), 70)                # no size: unchanged
