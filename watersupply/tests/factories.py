# water/tests/factories.py
from django.contrib.gis.geos import Point, MultiPoint, MultiPolygon, Polygon
from common.models import Province, City, Neighborhood
from watersupply.models import (
    UsersLocation, MeteredResidential,
    ConsumptionCapita, ExtractionWater,
    AvailableFreshWater, OPEX
)

def make_polygon(x=5.0, y=52.0):
    """Simple polygon around a point for spatial fields."""
    return MultiPolygon(Polygon((
        (x-0.1, y-0.1), (x+0.1, y-0.1),
        (x+0.1, y+0.1), (x-0.1, y+0.1),
        (x-0.1, y-0.1)
    ), srid=4326))

def make_province(**kwargs):
    defaults = dict(ProvinceName="Test Province", geom=make_polygon())
    defaults.update(kwargs)
    return Province.objects.create(**defaults)

def make_city(province=None, **kwargs):
    province = province or make_province()
    defaults = dict(
        cityName="Test City",
        province=province,
        currentPopulation=10000,
        geom=make_polygon()
    )
    defaults.update(kwargs)
    return City.objects.create(**defaults)

def make_neighborhood(city=None, **kwargs):
    city = city or make_city()
    defaults = dict(neighborhoodName="Test Neighborhood", city=city, geom=make_polygon(), currentPopulation=1200)
    defaults.update(kwargs)
    return Neighborhood.objects.create(**defaults)

def make_users_location(neighborhood=None, **kwargs):
    neighborhood = neighborhood or make_neighborhood()
    defaults = dict(
        neighborhood=neighborhood,
        usersTotal=500,
        ResidentialUsers=400,
        populationServed=1200,
    )
    defaults.update(kwargs)
    return UsersLocation.objects.create(**defaults)

def make_consumption_capita(city=None, **kwargs):
    city = city or make_city()
    defaults = dict(
        city=city,
        year=2024,
        consumption_capita_L_d=120.0,
    )
    defaults.update(kwargs)
    # bypass save() validation if needed
    obj = ConsumptionCapita(**defaults)
    obj.save()
    return obj

def make_metered_residential(user_location=None, **kwargs):
    user_location = user_location or make_users_location()
    defaults = dict(
        userLocation=user_location,
        installed_meters=400,
        functional_meters=380,
        collected_meters=350,
        userTariff_EUR_m3=0.50,
        userAffordability_PCT=3.5,
    )
    defaults.update(kwargs)
    return MeteredResidential(**defaults)  # don't .save() yet — let test control it