# water/tests/factories.py
import uuid
from django.conf import settings
from django.contrib.gis.geos import Point, MultiPoint, MultiPolygon, Polygon
from administrative.models import Province, City, District, Neighborhood
from watersupply.models import (
    UsersLocation, MeteredResidential,
    ConsumptionCapita, ExtractionWater,
    AvailableFreshWater, OPEX
)

def make_polygon(x=257000.0, y=470000.0, half_size_m=500.0):
    """
    Square (default 1 km x 1 km = 1 km2) around an EPSG:28992 point (default:
    Enschede) for spatial fields. Metres, so area/density computed in save()
    are meaningful. The MultiPolygon constructor drops the SRID, so it is
    passed explicitly.
    """
    h = half_size_m
    return MultiPolygon(Polygon((
        (x-h, y-h), (x+h, y-h),
        (x+h, y+h), (x-h, y+h),
        (x-h, y-h)
    )), srid=settings.COORDINATE_SYSTEM)

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

def make_district(city=None, **kwargs):
    city = city or make_city()
    defaults = dict(
        id=f"test-district-{uuid.uuid4().hex[:8]}",
        districtName="Test District",
        city=city,
        geom=make_polygon(),
    )
    defaults.update(kwargs)
    return District.objects.create(**defaults)

def make_neighborhood(city=None, district=None, **kwargs):
    district = district or make_district(city=city)
    defaults = dict(
        id=f"test-neighborhood-{uuid.uuid4().hex[:8]}",
        neighborhoodName="Test Neighborhood",
        district=district,
        geom=make_polygon(),
        currentPopulation=1200,
    )
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