from django.conf import settings

coordinate_system = settings.COORDINATE_SYSTEM


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
        "code": "id",
        # Population fields are computed in model.save(), not from WFS
    },
    "pdok_cities": {
        "__geometry__": "geom",
        "__unique__": "naam",
        "__unique_field__": "CityName",
        "naam": "CityName",
        "code": "id",        
        # Province FK will be resolved via spatial join
    },
    "pdok_districts": {
        "__geometry__": "geom",
        "__unique__": "wijkcode",
        "__unique_field__": "wijkcode",
        "wijknaam": "districtName",
        "wijkcode": "id",
        # City FK will be resolved via spatial join
    },
    "pdok_neighborhoods": {
        "__geometry__": "geom",
        "__unique__": "buurtcode",
        "__unique_field__": "code",
        "buurtnaam": "NeighborhoodName",
        "buurtcode": "id",
        "aantalInwoners": "currentPopulation",
        # City FK will be resolved via spatial join
    },
    "CBS_Housing": {
        "__unique_fields__": ["city", "year"],
        "__year_source__": "Perioden",
        "__year_field__": "year",
        "__city_source__": "RegioS",
        "__city_field__": "city",
        "EindstandVoorraad_22": "supply_units",
        "VergundeNieuwbouw_2": "demand_units",
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
        "key": "pdok_districts",
        "source": "CBS",
        "category": "Administrative boundaries",
        "name": "Districts - Wijken ",
        "description": "CBS districts polygons from the Wijken en Buurten dataset.",
        "target_model": "common.Districts",
        "url": "https://service.pdok.nl/cbs/wijkenbuurten/wfs/v1_0",
        "layer": "wijkenbuurten:wijken",
        "format": "wfs",
        "requires_bbox": True,
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    
    {
        "key": "pdok_neighborhoods",
        "source": "CBS",
        "category": "Administrative boundaries",
        "name": "Neighborhoods - Buurten",
        "description": "CBS neighborhood polygons from the Wijken en Buurten dataset.",
        "target_model": "common.Neighborhood",
        "url": "https://service.pdok.nl/cbs/wijkenbuurten/wfs/v1_0",
        "layer": "wijkenbuurten:buurten",
        "format": "wfs",
        "requires_bbox": True,
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
        
    },
    
    {
      "key": "CBS_Housing",
      "source": "CBS",
      "category": "Housing",
      "name": "Housing Lifecycle (86098NED)",
      "description": "CBS housing stock lifecycle per municipality: inventory, new construction, permits, demolitions.",
      "target_model": "housing.HousingSupplyDemand",
      "table_id": "86098NED",
      "format": "odata",
      "requires_bbox": False,
      "params": {
          "filter": "Gebruiksfunctie eq 'A045364' and startswith(RegioS,'GM') and substringof('KW04',Perioden)",
          "select": ["RegioS", "Perioden", "EindstandVoorraad_22", "VergundeNieuwbouw_2"],
      },
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
        "color": "indigo",
        "auth_required": False,
    },
    
    "CBS":{
      "name": "CBS",
      "full_name": "Census Bureau of Statistics",
      "description": "Dutch national statistics data platform. Open data, no authentication required.",
      "icon": "globe",
      "color": "cyan",
      "auth_required": False 
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