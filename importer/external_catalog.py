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
#   "__static__"   → dict of {model_field: constant_value} applied to every
#                    feature in this dataset, regardless of WFS properties

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
        "__unique_field__": "cityName",
        "__spatial_fk__": {"field": "province", "model": "common.Province", "required": True},
        "naam": "cityName",
        "code": "id",
    },
    "pdok_districts": {
        "__geometry__": "geom",
        "__unique__": "wijkcode",
        "__unique_field__": "id",
        "__spatial_fk__": {"field": "city", "model": "common.City", "required": True},
        "wijknaam": "districtName",
        "wijkcode": "id",
    },
    "pdok_neighborhoods": {
        "__geometry__": "geom",
        "__unique__": "buurtcode",
        "__unique_field__": "id",
        "__spatial_fk__": {"field": "district", "model": "common.District", "required": False},
        "buurtnaam": "neighborhoodName",
        "buurtcode": "id",
        "aantalInwoners": "currentPopulation",
        "jaar": "populationDate",
    },
    "CBS_Housing": {
        "__unique_fields__": ["city", "year"],
        "__year_source__": "Perioden",
        "__year_field__": "year",
        "__city_source__": "RegioS",
        "__city_field__": "city",
        "SaldoVoorraad_21": "supply_units",
        "VergundeNieuwbouw_2": "demand_units",
    },
    
    "pdok_buildings": {
        "__geometry__": "geom",
        "__unique__": "identificatie",
        "__unique_field__": "id",
        "bouwjaar": "constructionYear",
        # "status": "status",
        'gebruiksdoel': "usageFunction",
        'aantal_verblijfsobjecten': "numberUnits",
    },
    "pdok_streets": {
        "__geometry__": "geom",
        "__unique__": "gmlId",
        "__unique_field__": "inspireID",
        "text": "name",
    },
    
    "pdok_natura2000": {
        "__geometry__": "geom",
        "__unique__": "gmlID",
        "__unique_field__": "inspireID",
        "__static__": {"protection_type": "N2K"},
        "text": "name",
    },
    "pdok_water_bodies": {
        "__geometry__": "geom",
        "__unique__": "localId",
        "__unique_field__": "localId",
        "geographicalName": "name",
        "type": "water_type",
        "persistence": "persistence",
    },
    "pdok_waterwaysLN": {
        "__geometry__": "geom",
        "__unique__": "localId",
        "__unique_field__": "localId",
        "namespace": "name",
        "persistence": "persistence",
        "lowerWidth": "lowerWidth",
        "upperWidth": "upperWidth",
    },
     "pdok_waterwaysPG": {
        "__geometry__": "geom",
        "__unique__": "localId",
        "__unique_field__": "localId",
        "namespace": "name",
        "persistence": "persistence",
        "lowerWidth": "lowerWidth",
        "upperWidth": "upperWidth",
        },
     
    "pdok_forests": {
        "__geometry__": "geom",
        "__unique__": "id",
        "__unique_field__": "source_id",
        "id": "source_id",
        "naam": "name",
    },
    "rivm_energy_labels": {
        "__geometry__": "geom",
        "__unique__": "identificatie",
        "__unique_field__": "id",
        "dominant_label": "energyLabel",
        "hoogste_label": "energyLabelHighest",
        "laagste_label": "energyLabelLowest",
        "aant_labels": "energyLabelCount",
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
        "requires_bbox": True,
        "draw_bbox": True,
        "requires_model": "common.Province",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    {
        "key": "pdok_districts",
        "source": "CBS",
        "category": "Administrative boundaries",
        "name": "Districts - Wijken ",
        "description": "CBS districts polygons from the Wijken en Buurten dataset.",
        "target_model": "common.District",
        "url": "https://service.pdok.nl/cbs/wijkenbuurten/2025/wfs/v1_0", # UPDATE YEAR AS NEEDED
        "layer": "wijkenbuurten:wijken",
        "format": "wfs",
        "requires_bbox": True,
        "requires_model": "common.City",
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
        "url": "https://service.pdok.nl/cbs/wijkenbuurten/2025/wfs/v1_0", # UPDATE YEAR AS NEEDED
        "layer": "wijkenbuurten:buurten",
        "format": "wfs",
        "requires_bbox": True,
        "requires_model": "common.District",
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
      "requires_bbox": True,
      "params": {
          "filter": "Gebruiksfunctie eq 'A045364' and startswith(RegioS,'GM') and substringof('KW04',Perioden)",
          "select": ["RegioS", "Perioden", "SaldoVoorraad_21", "VergundeNieuwbouw_2"],
      },
      "enabled": True,
    },

    # ── Built environment (WFS - vector) ─────────────────────────────────────
    {
        "key": "pdok_buildings",
        "source": "pdok",
        "category": "Built environment",
        "name": "Buildings (BAG Panden)",
        "description": "All buildings from the Basisregistratie Adressen en Gebouwen (BAG). Large dataset — requires bounding box. WARNING: this may take a long time to load.",
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
        "name": "Road Network (Vervoersnetwerken)",
        "description": "General Road network from Inspire.",
        "target_model": "builtup.Street",
        "url": "https://service.pdok.nl/rws/vervoersnetwerken-wegen-netwerk/wfs/v1_0",
        "layer": "vervoersnetwerken:road_link",
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
        "name": "Water Bodies (Kadaster BRT Hydrografie)",
        "description": "Lakes, ponds, and other water bodies from Kadaster.",
        "target_model": "nature.WaterBodies",
        "url": "https://service.pdok.nl/kadaster/brt-hydrografie/wfs/v1_0",
        "layer": "brt-hydrografie:standingwater",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "requires_bbox": True,
        "enabled": True,
    },
    {
        "key": "pdok_waterwaysLN",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Watercourse Lines",
        "description": "Waterways and rivers from the Kadaster dataset.",
        "target_model": "nature.WaterBodies",
        "url": "https://service.pdok.nl/kadaster/brt-hydrografie/wfs/v1_0",
        "layer": "brt-hydrografie:watercourse_linestring",
        "format": "wfs",
        "params": {"srsName": "EPSG:{coordinate_system}".format(coordinate_system=coordinate_system)},
        "enabled": True,
    },
    
    {
        "key": "pdok_waterwaysPG",
        "source": "pdok",
        "category": "Nature & Environment",
        "name": "Watercourse Polygons",
        "description": "Waterways and rivers from the Kadaster dataset.",
        "target_model": "nature.WaterBodies",
        "url": "https://service.pdok.nl/kadaster/brt-hydrografie/wfs/v1_0",
        "layer": "brt-hydrografie:watercourse_linestring",
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
        "key": "rivm_energy_labels",
        "source": "rivm",
        "category": "Energy",
        "name": "Building Energy Labels (RVO EP-Online, via RIVM)",
        # PDOK never carried this dataset (the old service.pdok.nl/rvo/epontline
        # URL 404s and has no replacement there). RVO's own EP-Online API is
        # per-address and requires an API key. RIVM republishes the same
        # register, pre-aggregated to one polygon per BAG pand, as an open WFS
        # (this is what backs the "Energielabels van gebouwen" layer on
        # atlasleefomgeving.nl). Writes onto builtup.Building by id==identificatie,
        # so run "Buildings (BAG Panden)" first for rows to attach labels to.
        "description": "Per-building aggregate of registered EP-Online energy labels (dominant/highest/lowest label, label count), sourced from RVO and republished by RIVM. Updated monthly. Requires bounding box; import BAG Panden first so buildings exist to attach labels to.",
        "target_model": "builtup.Building",
        "url": "https://data.rivm.nl/geo/nl/wfs",
        "layer": "rvo_energielabels",
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
        "resolution_m": 0.5,
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
        "resolution_m": 0.5,
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
        "resolution_m": 5.0,
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
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
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

    # ── Spectral Indices (openEO) ─────────────────────────────────────────────
    # Formerly served via the Sentinel Hub Process API, which is now a paid
    # tier. Re-implemented as openEO band math against the Copernicus Data
    # Space Ecosystem's free openEO backend — see
    # https://documentation.dataspace.copernicus.eu/APIs/openEO/Python_Client/Python.html
    # Auth is a CDSE OIDC client_id/client_secret (client-credentials grant),
    # not a single bearer token.
    {
        "key": "sentinel2_ndvi_raster",
        "source": "sentinel2",
        "category": "Spectral Indices",
        "name": "NDVI (Vegetation Index)",
        "description": "Normalized Difference Vegetation Index computed from Sentinel-2 bands via openEO.",
        "target_model": "common.LandCoverRaster",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "NDVI",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "enabled": True,
    },
    {
        "key": "sentinel2_true_color_raster",
        "source": "sentinel2",
        "category": "Imagery",
        "name": "True Color (RGB)",
        "description": "Natural color composite from Sentinel-2 visible bands via openEO.",
        "target_model": "common.SatelliteImagery",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "TRUE_COLOR",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "enabled": True,
    },
    {
        "key": "sentinel2_ndwi_raster",
        "source": "sentinel2",
        "category": "Spectral Indices",
        "name": "NDWI (Water Index)",
        "description": "Normalized Difference Water Index for water body detection via openEO.",
        "target_model": "common.LandCoverRaster",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "NDWI",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
        "enabled": True,
    },
    {
        "key": "sentinel2_moisture_raster",
        "source": "sentinel2",
        "category": "Spectral Indices",
        "name": "Moisture Index",
        "description": "Normalized Difference Moisture Index for vegetation water content via openEO.",
        "target_model": "common.LandCoverRaster",
        "url": "https://openeo.dataspace.copernicus.eu",
        "format": "openeo",
        "openeo_process": "MOISTURE_INDEX",
        "params": {"srsName": "EPSG:4326"},
        "requires_bbox": True,
        "requires_date_range": True,
        "requires_auth": True,
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
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
        "resolution_m": 30.0,
        "satellite_type": "Landsat",
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
        "resolution_m": 30.0,
        "satellite_type": "Landsat",
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
        "resolution_m": 30.0,
        "satellite_type": "Landsat",
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
        "resolution_m": 10.0,
        "satellite_type": "Sentinel-2",
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
        "resolution_m": 9000.0,
        "satellite_type": "SMAP",
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
        "resolution_m": 100.0,
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
        "resolution_m": 500.0,
        "satellite_type": "VIIRS",
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
        "description": "ESA Copernicus satellite imagery. Spectral index/true color datasets run on CDSE's free openEO backend and need an OIDC client id/secret; WCS/WMS layers are open access.",
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

    "rivm": {
        "name": "RIVM",
        "full_name": "Rijksinstituut voor Volksgezondheid en Milieu",
        "description": "Dutch national institute for public health and the environment. Open WFS data, no authentication required.",
        "icon": "globe",
        "color": "indigo",
        "auth_required": False,
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