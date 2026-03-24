"""
External Data Catalog & Import Logic
=====================================
Defines available datasets from PDOK, Sentinel-2, and Google Earth Engine
that can be fetched and imported into CrossTwin models.

Each catalog entry specifies:
  - source:       'pdok' | 'sentinel2' | 'gee'
  - key:          unique identifier
  - name:         human-readable display name
  - description:  short description for the UI
  - target_model: Django model path (app_label.ModelName)
  - url/endpoint: where to fetch the data
  - format:       'wfs' | 'wcs' | 'wms' | 'raster' | 'atom'
  - field_mapping: dict mapping WFS properties → model fields
  - unique_field:  field to use for update_or_create lookup
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta

import requests
from django.apps import apps
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry, Polygon, MultiPolygon
from django.conf import settings
from django.utils import timezone

coordinate_system = settings.COORDINATE_SYSTEM

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Field Mapping Definitions
# ---------------------------------------------------------------------------
# These define how WFS properties map to Django model fields.
# Keys are WFS property names, values are model field names.
# Special keys:
#   "__geometry__" → the geometry field name in the model
#   "__unique__"   → the WFS property used for update_or_create lookup

FIELD_MAPPINGS = {
    "pdok_provinces": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "ProvinceName",
        "naam": "ProvinceName",
        # Population fields are computed in model.save(), not from WFS
    },
    "pdok_cities": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "CityName",
        "naam": "CityName",
        "code": "code",
        # Province FK will be resolved via spatial join
    },
    "pdok_neighborhoods": {
        "__geometry__": "geom",
        "__unique__": "buurtcode",
        "__unique_field__": "code",
        "buurtnaam": "NeighborhoodName",
        "buurtcode": "code",
        "wijkcode": "wijkcode",
        # City FK will be resolved via spatial join
    },
    "pdok_buildings": {
        "__geometry__": "geom",
        "__unique__": "identificatie",
        "__unique_field__": "bag_id",
        "identificatie": "bag_id",
        "bouwjaar": "construction_year",
        "status": "status",
        "oppervlakte": "area_m2",
    },
    "pdok_streets": {
        "__geometry__": "geom",
        "__unique__": "identificatie",
        "__unique_field__": "identification",
        "identificatie": "identification",
        "openbareruimtenaam": "name",
        "type": "street_type",
    },
    "pdok_natura2000": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "name",
        "naam": "name",
        "sitecode": "site_code",
        "type": "protection_type",
    },
    "pdok_water_bodies": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "name",
        "naam": "name",
        "type": "water_type",
    },
    "pdok_waterways": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "name",
        "naam": "name",
        "type": "waterway_type",
    },
    "pdok_forests": {
        "__geometry__": "geom",
        "__unique__": "id",
        "__unique_field__": "source_id",
        "id": "source_id",
        "naam": "name",
    },
    "pdok_energy_labels": {
        "__geometry__": "geom",
        "__unique__": "pand_id",
        "__unique_field__": "building_id",
        "pand_id": "building_id",
        "energieklasse": "energy_label",
        "registratiedatum": "registration_date",
    },
}


# ---------------------------------------------------------------------------
# Dataset Catalog
# ---------------------------------------------------------------------------
# Organised by source → category for the UI.
# 'enabled' can be toggled once a handler is implemented.
# Preference: raster (TIFF/COG) > WCS > WFS > WMS

EXTERNAL_DATA_CATALOG = [
    # ══════════════════════════════════════════════════════════════════════════
    # PDOK - Dutch National Geospatial Data Platform
    # ══════════════════════════════════════════════════════════════════════════
    
    # ── Administrative boundaries (WFS - vector) ─────────────────────────────
    {
        "key": "pdok_provinces",
        "source": "pdok",
        "category": "Administrative boundaries",
        "name": "Provinces (Provincies)",
        "description": "All 12 Dutch provinces with official boundaries from the Bestuurlijke Grenzen dataset.",
        "target_model": "common.Province",
        "url": "https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0",
        "layer": "bestuurlijkegebieden:Provinciegebied",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_cities",
        "source": "pdok",
        "category": "Administrative boundaries",
        "name": "Municipalities (Gemeenten)",
        "description": "All Dutch municipalities from the Bestuurlijke Grenzen dataset.",
        "target_model": "common.City",
        "url": "https://service.pdok.nl/kadaster/bestuurlijkegebieden/wfs/v1_0",
        "layer": "bestuurlijkegebieden:Gemeentegebied",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_neighborhoods",
        "source": "pdok",
        "category": "Administrative boundaries",
        "name": "Neighborhoods (Wijken & Buurten)",
        "description": "CBS neighborhood polygons from the Wijken en Buurten dataset.",
        "target_model": "common.Neighborhood",
        "url": "https://service.pdok.nl/cbs/wijkenbuurten/wfs/v1_0",
        "layer": "wijkenbuurten:buurten",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },

    # ── Built environment (WFS - vector) ─────────────────────────────────────
    {
        "key": "pdok_buildings",
        "source": "pdok",
        "category": "Built environment",
        "name": "Buildings (BAG Panden)",
        "description": "All buildings from the Basisregistratie Adressen en Gebouwen (BAG). Large dataset — requires bounding box.",
        "target_model": "builtup.Building",
        "url": "https://service.pdok.nl/lv/bag/wfs/v2_0",
        "layer": "bag:pand",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "pdok_streets",
        "source": "pdok",
        "category": "Built environment",
        "name": "Streets (Openbare Ruimten)",
        "description": "Named public spaces (streets, squares) from BAG.",
        "target_model": "builtup.Street",
        "url": "https://service.pdok.nl/lv/bag/wfs/v2_0",
        "layer": "bag:openbareruimte",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },

    # ── Nature & Environment (WFS - vector) ──────────────────────────────────
    {
        "key": "pdok_natura2000",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Natura 2000 Areas",
        "description": "European protected nature areas in the Netherlands.",
        "target_model": "nature.ProtectedArea",
        "url": "https://service.pdok.nl/rvo/natura2000/wfs/v1_0",
        "layer": "natura2000",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_water_bodies",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Water Bodies (TOP10NL)",
        "description": "Lakes, ponds, and other water bodies from TOP10NL.",
        "target_model": "nature.WaterBodies",
        "url": "https://service.pdok.nl/brt/top10nl/wfs/v1_0",
        "layer": "top10nl:Waterdeel",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "pdok_waterways",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Waterways (Vaarwegen)",
        "description": "Navigable waterways from Rijkswaterstaat.",
        "target_model": "nature.WaterWays",
        "url": "https://service.pdok.nl/rws/vaarweginfo/wfs/v1_0",
        "layer": "vaarweginfo:vaarwegvakken",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_forests",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Forests (Bossen)",
        "description": "Forest areas from TOP10NL dataset.",
        "target_model": "nature.Forests",
        "url": "https://service.pdok.nl/brt/top10nl/wfs/v1_0",
        "layer": "top10nl:Terrein",
        "format": "wfs",
        "params": {
            "srsName": "EPSG:{coordinate_system}",
            "cql_filter": "typelandgebruik='bos: loofbos' OR typelandgebruik='bos: naaldbos' OR typelandgebruik='bos: gemengd bos'"
        },
        "requires_bbox": True,
        "enabled": True,
    },

    # ── Energy ───────────────────────────────────────────────────────────────
    {
        "key": "pdok_energy_labels",
        "source": "pdok",
        "category": "Energy",
        "name": "Energy Labels (EP-Online)",
        "description": "Building energy efficiency labels from EP-Online register.",
        "target_model": "Energy.EnergyEfficiencyLabels",
        "url": "https://service.pdok.nl/rvo/epontline/wfs/v1_0",
        "layer": "epontline:Energielabel",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },

    # ── Elevation/Terrain (Raster) ───────────────────────────────────────────
    {
        "key": "pdok_dem_ahn_raster",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Elevation Model (AHN4 DTM)",
        "description": "High-resolution terrain model from AHN4. Downloads GeoTIFF tiles via ATOM feed.",
        "target_model": "common.DigitalElevationModel",
        "url": "https://service.pdok.nl/rws/ahn/atom/v1_0/dtm_05m.xml",
        "format": "atom",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "pdok_dem_ahn_wms",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Elevation Model (AHN4 WMS)",
        "description": "WMS visualization layer for AHN4 elevation data.",
        "target_model": "common.DigitalElevationModelWMS",
        "url": "https://service.pdok.nl/rws/ahn/wms/v1_0",
        "layer": "dtm_05m",
        "format": "wms",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_dsm_ahn_raster",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Surface Model (AHN4 DSM)",
        "description": "High-resolution surface model (including buildings/trees) from AHN4.",
        "target_model": "common.DigitalSurfaceModel",
        "url": "https://service.pdok.nl/rws/ahn/atom/v1_0/dsm_05m.xml",
        "format": "atom",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "pdok_dsm_ahn_wms",
        "source": "pdok",
        "category": "Elevation & Terrain",
        "name": "Digital Surface Model (AHN4 DSM WMS)",
        "description": "WMS visualization layer for AHN4 surface model.",
        "target_model": "common.DigitalSurfaceModelWMS",
        "url": "https://service.pdok.nl/rws/ahn/wms/v1_0",
        "layer": "dsm_05m",
        "format": "wms",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },

    # ── Land Cover (Raster) ──────────────────────────────────────────────────
    {
        "key": "pdok_landcover_lgn",
        "source": "pdok",
        "category": "Land Cover",
        "name": "Land Cover (LGN2021)",
        "description": "Dutch national land use map at 5m resolution via WCS.",
        "target_model": "common.LandCoverRaster",
        "url": "https://service.pdok.nl/rvo/lgn/wcs/v1_0",
        "wcs_url": "https://service.pdok.nl/rvo/lgn/wcs/v1_0",
        "layer": "lgn2021",
        "format": "wcs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Sentinel-2 - Copernicus Earth Observation
    # ══════════════════════════════════════════════════════════════════════════
    
    # ── Land Cover (Raster) ──────────────────────────────────────────────────
    {
        "key": "sentinel2_worldcover_raster",
        "source": "sentinel2",
        "category": "Land Cover",
        "name": "ESA WorldCover 10m (2021)",
        "description": "Global 10m land cover from Sentinel-2 via WCS.",
        "target_model": "common.LandCoverRaster",
        "url": "https://services.terrascope.be/wcs/v2",
        "wcs_url": "https://services.terrascope.be/wcs/v2",
        "layer": "WORLDCOVER_2021_MAP",
        "format": "wcs",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "sentinel2_worldcover_wms",
        "source": "sentinel2",
        "category": "Land Cover",
        "name": "ESA WorldCover 10m (WMS)",
        "description": "WMS visualization of global land cover.",
        "target_model": "common.LandCoverWMS",
        "url": "https://services.terrascope.be/wms/v2",
        "layer": "WORLDCOVER_2021_MAP",
        "format": "wms",
        "params": {"srsName": "EPSG:4326"},
        "enabled": True,
    },

    # ── Spectral Indices (Process API) ───────────────────────────────────────
    {
        "key": "sentinel2_ndvi_raster",
        "source": "sentinel2",
        "category": "Spectral Indices",
        "name": "NDVI (Vegetation Index)",
        "description": "Normalized Difference Vegetation Index computed from Sentinel-2 bands.",
        "target_model": "common.LandCoverRaster",
        "url": "https://services.sentinel-hub.com/api/v1/process",
        "format": "process_api",
        "evalscript": "NDVI",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "sentinel2_ndvi_wms",
        "source": "sentinel2",
        "category": "Spectral Indices",
        "name": "NDVI (WMS Preview)",
        "description": "WMS visualization of NDVI.",
        "target_model": "common.LandCoverWMS",
        "url": "https://services.sentinel-hub.com/ogc/wms",
        "layer": "NDVI",
        "format": "wms",
        "params": {"srsName": "EPSG:4326"},
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "sentinel2_true_color_raster",
        "source": "sentinel2",
        "category": "Imagery",
        "name": "True Color (RGB)",
        "description": "Natural color composite from Sentinel-2 visible bands.",
        "target_model": "common.LandCoverRaster",
        "url": "https://services.sentinel-hub.com/api/v1/process",
        "format": "process_api",
        "evalscript": "TRUE_COLOR",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "sentinel2_ndwi_raster",
        "source": "sentinel2",
        "category": "Spectral Indices",
        "name": "NDWI (Water Index)",
        "description": "Normalized Difference Water Index for water body detection.",
        "target_model": "common.LandCoverRaster",
        "url": "https://services.sentinel-hub.com/api/v1/process",
        "format": "process_api",
        "evalscript": "NDWI",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "sentinel2_moisture_raster",
        "source": "sentinel2",
        "category": "Spectral Indices",
        "name": "Moisture Index",
        "description": "Normalized Difference Moisture Index for vegetation water content.",
        "target_model": "common.LandCoverRaster",
        "url": "https://services.sentinel-hub.com/api/v1/process",
        "format": "process_api",
        "evalscript": "MOISTURE_INDEX",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # Google Earth Engine
    # ══════════════════════════════════════════════════════════════════════════
    
    # ── Water ────────────────────────────────────────────────────────────────
    {
        "key": "gee_global_surface_water",
        "source": "gee",
        "category": "Water",
        "name": "Global Surface Water Occurrence",
        "description": "JRC Global Surface Water dataset showing water occurrence frequency (1984-2021).",
        "target_model": "nature.WaterBodies",
        "asset_id": "JRC/GSW1_4/GlobalSurfaceWater",
        "band": "occurrence",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_water_seasonality",
        "source": "gee",
        "category": "Water",
        "name": "Water Seasonality",
        "description": "Number of months per year with water presence.",
        "target_model": "common.LandCoverRaster",
        "asset_id": "JRC/GSW1_4/GlobalSurfaceWater",
        "band": "seasonality",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },

    # ── Forests ──────────────────────────────────────────────────────────────
    {
        "key": "gee_forest_cover",
        "source": "gee",
        "category": "Forests",
        "name": "Global Forest Cover (2000)",
        "description": "Hansen Global Forest Change - tree cover percentage in year 2000.",
        "target_model": "nature.Forests",
        "asset_id": "UMD/hansen/global_forest_change_2023_v1_11",
        "band": "treecover2000",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_forest_loss",
        "source": "gee",
        "category": "Forests",
        "name": "Forest Loss Year",
        "description": "Year of forest loss event (2001-2023).",
        "target_model": "common.LandCoverRaster",
        "asset_id": "UMD/hansen/global_forest_change_2023_v1_11",
        "band": "lossyear",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_forest_gain",
        "source": "gee",
        "category": "Forests",
        "name": "Forest Gain (2000-2012)",
        "description": "Areas of forest gain between 2000-2012.",
        "target_model": "common.LandCoverRaster",
        "asset_id": "UMD/hansen/global_forest_change_2023_v1_11",
        "band": "gain",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },

    # ── Climate/Weather ──────────────────────────────────────────────────────
    {
        "key": "gee_precipitation",
        "source": "gee",
        "category": "Climate",
        "name": "Precipitation (CHIRPS)",
        "description": "CHIRPS daily precipitation data. Requires date range.",
        "target_model": "weather.PrecipitationRaster",
        "asset_id": "UCSB-CHG/CHIRPS/DAILY",
        "band": "precipitation",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_temperature",
        "source": "gee",
        "category": "Climate",
        "name": "Land Surface Temperature (MODIS)",
        "description": "MODIS 8-day land surface temperature. Requires date range.",
        "target_model": "weather.TemperatureRaster",
        "asset_id": "MODIS/061/MOD11A2",
        "band": "LST_Day_1km",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_wind_speed",
        "source": "gee",
        "category": "Climate",
        "name": "Wind Speed (ERA5)",
        "description": "ERA5 reanalysis wind speed data. Requires date range.",
        "target_model": "weather.WindSpeedRaster",
        "asset_id": "ECMWF/ERA5_LAND/HOURLY",
        "band": "u_component_of_wind_10m",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },

    # ── Land Cover ───────────────────────────────────────────────────────────
    {
        "key": "gee_dynamic_world",
        "source": "gee",
        "category": "Land Cover",
        "name": "Dynamic World (Near Real-Time)",
        "description": "Google/WRI 10m land cover classification. Requires date range.",
        "target_model": "common.LandCoverRaster",
        "asset_id": "GOOGLE/DYNAMICWORLD/V1",
        "band": "label",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_soil_moisture",
        "source": "gee",
        "category": "Land Cover",
        "name": "Soil Moisture (SMAP)",
        "description": "NASA SMAP soil moisture data. Requires date range.",
        "target_model": "common.LandCoverRaster",
        "asset_id": "NASA/SMAP/SPL4SMGP/007",
        "band": "sm_surface",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },

    # ── Demographics ─────────────────────────────────────────────────────────
    {
        "key": "gee_population_density",
        "source": "gee",
        "category": "Demographics",
        "name": "Population Density (WorldPop)",
        "description": "WorldPop population density estimates.",
        "target_model": "common.LandCoverRaster",
        "asset_id": "WorldPop/GP/100m/pop",
        "band": "population",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_auth": True,
        "enabled": True,
    },
    {
        "key": "gee_nighttime_lights",
        "source": "gee",
        "category": "Demographics",
        "name": "Nighttime Lights (VIIRS)",
        "description": "VIIRS nighttime lights as proxy for urban development.",
        "target_model": "common.LandCoverRaster",
        "asset_id": "NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG",
        "band": "avg_rad",
        "format": "raster",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "enabled": True,
    },
]

# Build a quick-lookup dict
CATALOG_BY_KEY = {d["key"]: d for d in EXTERNAL_DATA_CATALOG}

# Sources metadata for the UI
SOURCE_INFO = {
    "pdok": {
        "name": "PDOK",
        "full_name": "Publieke Dienstverlening Op de Kaart",
        "description": "Dutch national geospatial data platform. Open data, no authentication required.",
        "icon": "globe",
        "color": "cyan",
        "auth_required": False,
    },
    "sentinel2": {
        "name": "Sentinel-2",
        "full_name": "Copernicus Sentinel-2 Earth Observation",
        "description": "ESA Copernicus satellite imagery. Open access, some APIs require free registration.",
        "icon": "satellite",
        "color": "violet",
        "auth_required": False,
    },
    "gee": {
        "name": "Google Earth Engine",
        "full_name": "Google Earth Engine",
        "description": "Planetary-scale geospatial analysis platform. Requires a GEE service account JSON key.",
        "icon": "cloud",
        "color": "amber",
        "auth_required": True,
    },
}


def get_catalog_grouped():
    """
    Return the catalog grouped by source, then by category.
    Structure: { source_key: { category: [datasets] } }
    """
    grouped = {}
    for ds in EXTERNAL_DATA_CATALOG:
        src = ds["source"]
        cat = ds["category"]
        grouped.setdefault(src, {}).setdefault(cat, []).append(ds)
    return grouped


# ---------------------------------------------------------------------------
# Import Handlers
# ---------------------------------------------------------------------------

class ImportResult:
    """Result object for import operations."""
    def __init__(self, status: str, message: str, records_created: int = 0, records_updated: int = 0, file_path: str = None):
        self.status = status  # 'success', 'error', 'skipped', 'pending'
        self.message = message
        self.records_created = records_created
        self.records_updated = records_updated
        self.file_path = file_path

    def to_dict(self):
        return {
            "status": self.status,
            "message": self.message,
            "records_created": self.records_created,
            "records_updated": self.records_updated,
            "file_path": self.file_path,
        }


def ensure_multipolygon(geom: GEOSGeometry) -> MultiPolygon:
    """Convert Polygon to MultiPolygon if needed."""
    if geom.geom_type == 'Polygon':
        return MultiPolygon(geom)
    elif geom.geom_type == 'MultiPolygon':
        return geom
    else:
        raise ValueError(f"Expected Polygon or MultiPolygon, got {geom.geom_type}")


def get_model_class(model_path: str):
    """
    Get Django model class from 'app_label.ModelName' string.
    """
    try:
        return apps.get_model(model_path)
    except LookupError:
        raise ValueError(f"Model not found: {model_path}")


class GEEAuthManager:
    """Manages Google Earth Engine authentication."""
    
    _initialized = False
    _credentials = None
    _project_id = None
    
    @classmethod
    def initialize(cls, service_account_json: str) -> Tuple[bool, str]:
        """
        Initialize GEE with service account credentials.
        """
        try:
            import ee
            
            # Parse and validate JSON
            try:
                credentials_dict = json.loads(service_account_json)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {e}"
            
            # Check required fields
            required_fields = ['type', 'project_id', 'private_key', 'client_email']
            missing = [f for f in required_fields if f not in credentials_dict]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"
            
            if credentials_dict.get('type') != 'service_account':
                return False, "JSON must be a service account key (type='service_account')"
            
            # Create credentials
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            
            # Initialize Earth Engine
            ee.Initialize(credentials=credentials, project=credentials_dict['project_id'])
            
            # Test connection
            ee.Number(1).getInfo()
            
            cls._initialized = True
            cls._credentials = credentials
            cls._project_id = credentials_dict['project_id']
            
            return True, f"Successfully authenticated as {credentials_dict['client_email']}"
            
        except ImportError:
            return False, "Google Earth Engine library not installed. Run: pip install earthengine-api google-auth"
        except Exception as e:
            cls._initialized = False
            return False, f"GEE authentication failed: {str(e)}"
    
    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized
    
    @classmethod
    def get_project_id(cls) -> Optional[str]:
        return cls._project_id
    
    @classmethod
    def reset(cls):
        cls._initialized = False
        cls._credentials = None
        cls._project_id = None


class PDOKImporter:
    """Import handler for PDOK datasets - imports directly to Django models."""
    
    @staticmethod
    def fetch_wfs(dataset: Dict, bbox: Optional[list] = None, max_features: int = 10000) -> ImportResult:
        """
        Fetch vector data from PDOK WFS service and import directly to Django model.
        
        Args:
            dataset: Catalog entry dict
            bbox: [xmin, ymin, xmax, ymax] in EPSG:28992
            max_features: Maximum features to fetch
        """
        try:
            url = dataset["url"]
            layer = dataset["layer"]
            dataset_key = dataset["key"]
            model_path = dataset["target_model"]
            
            # Get field mapping for this dataset
            mapping = FIELD_MAPPINGS.get(dataset_key)
            if not mapping:
                return ImportResult("error", f"No field mapping defined for {dataset_key}")
            
            # Get model class
            try:
                Model = get_model_class(model_path)
            except ValueError as e:
                return ImportResult("error", str(e))
            
            # Build WFS request parameters
            params = {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": dataset["params"].get("srsName", "EPSG:28992"),
                "count": max_features,
            }
            
            # Add bbox filter if provided
            if bbox:
                params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:28992"
            
            # Add CQL filter if specified
            if "cql_filter" in dataset.get("params", {}):
                params["cql_filter"] = dataset["params"]["cql_filter"]
            
            logger.info(f"Fetching WFS: {url} layer={layer}")
            response = requests.get(url, params=params, timeout=120)
            response.raise_for_status()
            
            geojson = response.json()
            features = geojson.get("features", [])
            
            if not features:
                return ImportResult("success", "No features found in the specified area.", 0)
            
            # Import features to database
            geom_field = mapping.get("__geometry__", "geom")
            unique_wfs_prop = mapping.get("__unique__")
            unique_model_field = mapping.get("__unique_field__")
            
            created_count = 0
            updated_count = 0
            errors = []
            
            with transaction.atomic():
                for feat in features:
                    try:
                        props = feat.get("properties", {})
                        geom_json = feat.get("geometry")
                        
                        if not geom_json:
                            continue
                        
                        # Parse geometry
                        geom = GEOSGeometry(json.dumps(geom_json))
                        
                        # Ensure correct SRID
                        if geom.srid is None:
                            geom.srid = 28992
                        
                        # Convert to MultiPolygon if model expects it
                        model_geom_field = Model._meta.get_field(geom_field)
                        if hasattr(model_geom_field, 'geom_type'):
                            if model_geom_field.geom_type == 'MULTIPOLYGON' and geom.geom_type == 'Polygon':
                                geom = MultiPolygon(geom)
                            elif model_geom_field.geom_type == 'MULTILINESTRING' and geom.geom_type == 'LineString':
                                from django.contrib.gis.geos import MultiLineString
                                geom = MultiLineString(geom)
                            elif model_geom_field.geom_type == 'MULTIPOINT' and geom.geom_type == 'Point':
                                from django.contrib.gis.geos import MultiPoint
                                geom = MultiPoint(geom)
                        
                        # Build field values from mapping
                        field_values = {geom_field: geom}
                        
                        for wfs_prop, model_field in mapping.items():
                            if wfs_prop.startswith("__"):
                                continue  # Skip special keys
                            if wfs_prop in props and props[wfs_prop] is not None:
                                field_values[model_field] = props[wfs_prop]
                        
                        # Use update_or_create if unique field is defined
                        if unique_wfs_prop and unique_model_field and unique_wfs_prop in props:
                            lookup = {unique_model_field: props[unique_wfs_prop]}
                            defaults = {k: v for k, v in field_values.items() if k != unique_model_field}
                            
                            obj, was_created = Model.objects.update_or_create(
                                **lookup,
                                defaults=defaults
                            )
                            if was_created:
                                created_count += 1
                            else:
                                updated_count += 1
                        else:
                            # Just create new records
                            Model.objects.create(**field_values)
                            created_count += 1
                            
                    except Exception as e:
                        errors.append(str(e))
                        if len(errors) > 10:
                            break  # Stop after too many errors
            
            # Build result message
            msg_parts = []
            if created_count:
                msg_parts.append(f"created {created_count}")
            if updated_count:
                msg_parts.append(f"updated {updated_count}")
            
            msg = f"Imported {len(features)} features from {layer}: " + ", ".join(msg_parts) + "."
            
            if errors:
                msg += f" ({len(errors)} errors)"
                logger.warning(f"Import errors for {dataset_key}: {errors[:5]}")
            
            return ImportResult("success", msg, created_count, updated_count)
            
        except requests.RequestException as e:
            return ImportResult("error", f"WFS request failed: {e}")
        except Exception as e:
            logger.exception(f"WFS import error for {dataset['key']}")
            return ImportResult("error", f"Import failed: {e}")

    @staticmethod
    def fetch_wcs(dataset: Dict, bbox: list, resolution: float = 5.0) -> ImportResult:
        """
        Fetch raster data from PDOK WCS service.
        For rasters, we still save to file since they're not directly storable in typical models.
        """
        try:
            url = dataset.get("wcs_url", dataset["url"])
            layer = dataset["layer"]
            
            # Build WCS GetCoverage request
            params = {
                "service": "WCS",
                "version": "2.0.1",
                "request": "GetCoverage",
                "CoverageId": layer,
                "format": "image/tiff",
                "subset": [
                    f"x({bbox[0]},{bbox[2]})",
                    f"y({bbox[1]},{bbox[3]})",
                ],
            }
            
            logger.info(f"Fetching WCS: {url} coverage={layer}")
            response = requests.get(url, params=params, timeout=300)
            response.raise_for_status()
            
            # Save raster to temp file
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "pdok" / "rasters"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{dataset['key']}_{timestamp}.tif"
            filepath = temp_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return ImportResult(
                "success",
                f"Downloaded raster from {layer} ({len(response.content) / 1024:.1f} KB).",
                1,
                0,
                str(filepath)
            )
            
        except requests.RequestException as e:
            return ImportResult("error", f"WCS request failed: {e}")
        except Exception as e:
            logger.exception(f"WCS import error for {dataset['key']}")
            return ImportResult("error", f"Import failed: {e}")

    @staticmethod
    def fetch_atom(dataset: Dict, bbox: list, max_tiles: int = 4) -> ImportResult:
        """
        Download raster tiles from PDOK ATOM feed.
        """
        try:
            from xml.etree import ElementTree as ET
            
            atom_url = dataset["url"]
            
            logger.info(f"Fetching ATOM feed: {atom_url}")
            response = requests.get(atom_url, timeout=60)
            response.raise_for_status()
            
            # Parse ATOM XML
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'georss': 'http://www.georss.org/georss'}
            
            # Find entries with download links
            entries = root.findall('.//atom:entry', ns)
            
            if not entries:
                return ImportResult("error", "No entries found in ATOM feed.")
            
            # Filter by bbox intersection
            bbox_polygon = Polygon.from_bbox(bbox)
            matching_tiles = []
            
            for entry in entries:
                link_el = entry.find('atom:link[@rel="alternate"]', ns)
                if link_el is None:
                    continue
                
                tile_url = link_el.get('href')
                
                # Try to get georss:polygon or georss:box
                georss_box = entry.find('georss:box', ns)
                if georss_box is not None:
                    coords = georss_box.text.split()
                    if len(coords) == 4:
                        tile_bbox = [float(c) for c in coords]
                        tile_polygon = Polygon.from_bbox([tile_bbox[1], tile_bbox[0], tile_bbox[3], tile_bbox[2]])
                        if bbox_polygon.intersects(tile_polygon):
                            matching_tiles.append(tile_url)
                else:
                    # No georss info, include tile (can't filter)
                    matching_tiles.append(tile_url)
            
            if not matching_tiles:
                return ImportResult("success", "No tiles intersect the specified bounding box.", 0)
            
            # Limit number of tiles
            tiles_to_download = matching_tiles[:max_tiles]
            
            # Download tiles
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "pdok" / "rasters"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            downloaded = []
            for tile_url in tiles_to_download:
                try:
                    tile_response = requests.get(tile_url, timeout=300)
                    tile_response.raise_for_status()
                    
                    tile_filename = tile_url.split('/')[-1]
                    tile_path = temp_dir / tile_filename
                    
                    with open(tile_path, 'wb') as f:
                        f.write(tile_response.content)
                    
                    downloaded.append(str(tile_path))
                except Exception as e:
                    logger.warning(f"Failed to download tile {tile_url}: {e}")
            
            if not downloaded:
                return ImportResult("error", "Failed to download any tiles.")
            
            return ImportResult(
                "success",
                f"Downloaded {len(downloaded)} of {len(matching_tiles)} tiles ({max_tiles} max).",
                len(downloaded),
                0,
                downloaded[0] if len(downloaded) == 1 else str(temp_dir)
            )
            
        except Exception as e:
            logger.exception(f"ATOM import error for {dataset['key']}")
            return ImportResult("error", f"ATOM import failed: {e}")

    @staticmethod
    def register_wms(dataset: Dict) -> ImportResult:
        """
        Register a WMS layer (no data download, just configuration).
        """
        layer = dataset.get("layer", "unknown")
        url = dataset["url"]
        
        # For WMS, we typically just store the configuration
        # The actual rendering happens via TiTiler or direct WMS calls
        return ImportResult(
            "success",
            f"WMS layer registered: {layer}. URL: {url}",
            1
        )


class Sentinel2Importer:
    """Import handler for Sentinel-2 datasets."""
    
    # Evalscript templates for Process API
    EVALSCRIPTS = {
        "NDVI": """
//VERSION=3
function setup() {
  return { input: ["B04", "B08"], output: { bands: 1 } };
}
function evaluatePixel(sample) {
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  return [ndvi];
}
""",
        "NDWI": """
//VERSION=3
function setup() {
  return { input: ["B03", "B08"], output: { bands: 1 } };
}
function evaluatePixel(sample) {
  let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);
  return [ndwi];
}
""",
        "MOISTURE_INDEX": """
//VERSION=3
function setup() {
  return { input: ["B8A", "B11"], output: { bands: 1 } };
}
function evaluatePixel(sample) {
  let moisture = (sample.B8A - sample.B11) / (sample.B8A + sample.B11);
  return [moisture];
}
""",
        "TRUE_COLOR": """
//VERSION=3
function setup() {
  return { input: ["B04", "B03", "B02"], output: { bands: 3 } };
}
function evaluatePixel(sample) {
  return [sample.B04 * 2.5, sample.B03 * 2.5, sample.B02 * 2.5];
}
""",
    }
    
    @staticmethod
    def fetch_wcs(dataset: Dict, bbox: list) -> ImportResult:
        """Fetch raster from Sentinel-2 WCS (e.g., WorldCover)."""
        try:
            url = dataset.get("wcs_url", dataset["url"])
            layer = dataset["layer"]
            
            params = {
                "service": "WCS",
                "version": "2.0.1",
                "request": "GetCoverage",
                "CoverageId": layer,
                "format": "image/tiff",
                "subset": [
                    f"Lat({bbox[1]},{bbox[3]})",
                    f"Long({bbox[0]},{bbox[2]})",
                ],
            }
            
            logger.info(f"Fetching Sentinel-2 WCS: {url}")
            response = requests.get(url, params=params, timeout=300)
            response.raise_for_status()
            
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "sentinel2"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{dataset['key']}_{timestamp}.tif"
            filepath = temp_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return ImportResult(
                "success",
                f"Downloaded {layer} ({len(response.content) / 1024:.1f} KB).",
                1,
                0,
                str(filepath)
            )
            
        except Exception as e:
            logger.exception(f"Sentinel-2 WCS error for {dataset['key']}")
            return ImportResult("error", f"WCS request failed: {e}")

    @staticmethod
    def fetch_process_api(
        dataset: Dict,
        bbox: list,
        date_from: str = None,
        date_to: str = None,
        token: str = None
    ) -> ImportResult:
        """
        Fetch processed imagery via Sentinel Hub Process API.
        """
        try:
            if not token:
                return ImportResult("error", "Sentinel Hub Process API requires authentication token.")
            
            evalscript_key = dataset.get("evalscript", "TRUE_COLOR")
            evalscript = Sentinel2Importer.EVALSCRIPTS.get(evalscript_key)
            
            if not evalscript:
                return ImportResult("error", f"Unknown evalscript: {evalscript_key}")
            
            # Default date range: last 30 days
            if not date_from:
                date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            if not date_to:
                date_to = datetime.now().strftime("%Y-%m-%d")
            
            # Build request payload
            payload = {
                "input": {
                    "bounds": {
                        "bbox": bbox,
                        "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
                    },
                    "data": [{
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "timeRange": {
                                "from": f"{date_from}T00:00:00Z",
                                "to": f"{date_to}T23:59:59Z"
                            },
                            "mosaickingOrder": "leastCC"
                        }
                    }]
                },
                "output": {
                    "width": 512,
                    "height": 512,
                    "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]
                },
                "evalscript": evalscript
            }
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            url = dataset["url"]
            logger.info(f"Fetching Sentinel-2 Process API: {evalscript_key}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "sentinel2"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{dataset['key']}_{timestamp}.tif"
            filepath = temp_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return ImportResult(
                "success",
                f"Downloaded {evalscript_key} for {date_from} to {date_to} ({len(response.content) / 1024:.1f} KB).",
                1,
                0,
                str(filepath)
            )
            
        except Exception as e:
            logger.exception(f"Sentinel-2 Process API error for {dataset['key']}")
            return ImportResult("error", f"Process API request failed: {e}")

    @staticmethod
    def register_wms(dataset: Dict) -> ImportResult:
        """Register a Sentinel-2 WMS layer."""
        layer = dataset.get("layer", "unknown")
        url = dataset["url"]
        
        return ImportResult(
            "success",
            f"WMS layer registered: {layer}. URL: {url}",
            1
        )


class GEEImporter:
    """Import handler for Google Earth Engine datasets."""
    
    @staticmethod
    def export_raster(
        dataset: Dict,
        bbox: list,
        date_from: str = None,
        date_to: str = None
    ) -> ImportResult:
        """
        Export raster from GEE to local GeoTIFF.
        """
        try:
            import ee
            
            if not GEEAuthManager.is_initialized():
                return ImportResult("error", "GEE not authenticated. Please provide credentials.")
            
            asset_id = dataset.get("asset_id")
            band = dataset.get("band")
            
            if not asset_id:
                return ImportResult("error", "No asset_id specified for GEE dataset.")
            
            # Define region
            region = ee.Geometry.Rectangle(bbox)
            
            # Load image or image collection
            try:
                # Try as ImageCollection first
                collection = ee.ImageCollection(asset_id)
                
                # Apply date filter if needed
                if date_from and date_to:
                    collection = collection.filterDate(date_from, date_to)
                
                # Filter by region
                collection = collection.filterBounds(region)
                
                # Composite (mean)
                image = collection.mean()
                
            except Exception:
                # Fall back to single Image
                image = ee.Image(asset_id)
            
            # Select band if specified
            if band:
                image = image.select(band)
            
            # Clip to region
            image = image.clip(region)
            
            # Get download URL
            url = image.getDownloadURL({
                'scale': 30,
                'region': region,
                'format': 'GEO_TIFF',
                'crs': 'EPSG:4326'
            })
            
            logger.info(f"Downloading GEE raster from: {url[:100]}...")
            response = requests.get(url, timeout=300)
            response.raise_for_status()
            
            # Save to file
            temp_dir = Path(settings.MEDIA_ROOT) / "imports" / "gee"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{dataset['key']}_{timestamp}.tif"
            filepath = temp_dir / filename
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return ImportResult(
                "success",
                f"Downloaded {band or asset_id} ({len(response.content) / 1024:.1f} KB).",
                1,
                0,
                str(filepath)
            )
            
        except ImportError:
            return ImportResult("error", "earthengine-api not installed.")
        except Exception as e:
            logger.exception(f"GEE export error for {dataset['key']}")
            return ImportResult("error", f"GEE export failed: {e}")


def import_dataset(
    dataset_key: str,
    bbox: Optional[list] = None,
    date_from: str = None,
    date_to: str = None,
    gee_credentials: str = None,
    sentinel_token: str = None,
) -> ImportResult:
    """
    Main dispatcher for importing a dataset.
    
    Args:
        dataset_key: Key from EXTERNAL_DATA_CATALOG
        bbox: Bounding box [xmin, ymin, xmax, ymax]
        date_from: Start date for temporal datasets
        date_to: End date for temporal datasets
        gee_credentials: GEE service account JSON (for GEE sources)
        sentinel_token: Copernicus access token (for Sentinel Process API)
    
    Returns:
        ImportResult with status and details
    """
    if dataset_key not in CATALOG_BY_KEY:
        return ImportResult("error", f"Unknown dataset: {dataset_key}")
    
    dataset = CATALOG_BY_KEY[dataset_key]
    
    # Check if enabled
    if not dataset.get("enabled", True):
        return ImportResult("skipped", "Dataset is not yet enabled.")
    
    # Check bbox requirement
    if dataset.get("requires_bbox") and not bbox:
        return ImportResult("skipped", "This dataset requires a bounding box.")
    
    # Initialize GEE if needed
    if dataset["source"] == "gee":
        if gee_credentials:
            success, msg = GEEAuthManager.initialize(gee_credentials)
            if not success:
                return ImportResult("error", msg)
        elif not GEEAuthManager.is_initialized():
            return ImportResult("error", "GEE requires authentication. Please provide service account JSON.")
    
    # Dispatch based on source and format
    source = dataset["source"]
    fmt = dataset.get("format", "wfs")
    
    if source == "pdok":
        if fmt == "wfs":
            return PDOKImporter.fetch_wfs(dataset, bbox)
        elif fmt == "wcs":
            return PDOKImporter.fetch_wcs(dataset, bbox)
        elif fmt == "wms":
            return PDOKImporter.register_wms(dataset)
        elif fmt == "atom":
            return PDOKImporter.fetch_atom(dataset, bbox)
    
    elif source == "sentinel2":
        if fmt == "wcs":
            return Sentinel2Importer.fetch_wcs(dataset, bbox)
        elif fmt == "process_api":
            return Sentinel2Importer.fetch_process_api(
                dataset, bbox, date_from, date_to, sentinel_token
            )
        elif fmt == "wms":
            return Sentinel2Importer.register_wms(dataset)
    
    elif source == "gee":
        return GEEImporter.export_raster(dataset, bbox, date_from, date_to)
    
    return ImportResult("error", f"No handler for source={source}, format={fmt}")
