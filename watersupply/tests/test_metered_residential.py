# water/tests/test_metered_residential.py
from django.test import TestCase
from unittest.mock import patch, MagicMock
from .factories import (
    make_city, make_neighborhood, make_users_location,
    make_consumption_capita, make_metered_residential
)
from watersupply.models import MeteredResidential

class TestMeteredResidentialRecovery(TestCase):
    
    def setUp(self):
        self.city = make_city()
        self.neighborhood = make_neighborhood(city=self.city)
        self.user_location = make_users_location(
            neighborhood=self.neighborhood,
            populationServed=1200
        )
        self.consumption = make_consumption_capita(
            city=self.city,
            consumption_capita_L_d=120.0,
            year=2024
        )

    def test_recovery_eur_calculated_on_save(self):
        mr = make_metered_residential(
            user_location=self.user_location,
            installed_meters=400,
            collected_meters=350,
            userTariff_EUR_m3=0.50,
        )
        mr.save()

        collection_ratio = 350 / 400
        consumption = 120.0 / 1000 * 365 * 1200 * collection_ratio  # L→m³ * days * pop * ratio
        expected_recovery = consumption * 0.50

        self.assertAlmostEqual(mr.Recovery_EUR, expected_recovery, places=2)

    def test_recovery_zero_when_no_meters_installed(self):
        mr = make_metered_residential(
            user_location=self.user_location,
            installed_meters=0,
            collected_meters=0,
        )
        mr.save()
        self.assertEqual(mr.Recovery_EUR, 0)

    def test_recovery_none_when_no_consumption_record(self):
        """No ConsumptionCapita for this city → Recovery_EUR stays None."""
        empty_city = make_city()  # city with no ConsumptionCapita
        neighborhood = make_neighborhood(city=empty_city)
        user_location = make_users_location(neighborhood=neighborhood)
        
        mr = make_metered_residential(user_location=user_location)
        mr.save()
        self.assertIsNone(mr.Recovery_EUR)

    def test_recovery_none_when_no_population_served(self):
        user_location = make_users_location(
            neighborhood=self.neighborhood,
            populationServed=None
        )
        mr = make_metered_residential(user_location=user_location)
        mr.save()
        self.assertIsNone(mr.Recovery_EUR)