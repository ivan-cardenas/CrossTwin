# Graph Report - .  (2026-05-13)

## Corpus Check
- 157 files · ~55,574 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 712 nodes · 999 edges · 114 communities (81 shown, 33 thin omitted)
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 231 edges (avg confidence: 0.54)
- Token cost: 12,500 input · 3,200 output

## Community Hubs (Navigation)
- [[_COMMUNITY_External Data Catalog & Import|External Data Catalog & Import]]
- [[_COMMUNITY_Raster Generation & Metadata|Raster Generation & Metadata]]
- [[_COMMUNITY_Platform Architecture & Dependencies|Platform Architecture & Dependencies]]
- [[_COMMUNITY_Water Supply Calculations|Water Supply Calculations]]
- [[_COMMUNITY_Environmental & Economic Models|Environmental & Economic Models]]
- [[_COMMUNITY_Geospatial Upload Forms|Geospatial Upload Forms]]
- [[_COMMUNITY_Map Frontend JavaScript|Map Frontend JavaScript]]
- [[_COMMUNITY_Housing Indicator Calculations|Housing Indicator Calculations]]
- [[_COMMUNITY_Urban Heat Raster Models|Urban Heat Raster Models]]
- [[_COMMUNITY_Nature & Thermal Comfort|Nature & Thermal Comfort]]
- [[_COMMUNITY_Django App Configurations|Django App Configurations]]
- [[_COMMUNITY_Built Environment Models|Built Environment Models]]
- [[_COMMUNITY_Housing Finance Models|Housing Finance Models]]
- [[_COMMUNITY_Elevation & WMS Layers|Elevation & WMS Layers]]
- [[_COMMUNITY_Water Infrastructure Models|Water Infrastructure Models]]
- [[_COMMUNITY_Test Factories & Fixtures|Test Factories & Fixtures]]
- [[_COMMUNITY_COG Export Command|COG Export Command]]
- [[_COMMUNITY_Administrative & Meteorology Models|Administrative & Meteorology Models]]
- [[_COMMUNITY_PostGIS Test Infrastructure|PostGIS Test Infrastructure]]
- [[_COMMUNITY_Nature & Protected Areas|Nature & Protected Areas]]
- [[_COMMUNITY_Raster Signal Handlers|Raster Signal Handlers]]
- [[_COMMUNITY_Map API Views|Map API Views]]
- [[_COMMUNITY_Database Migrations|Database Migrations]]
- [[_COMMUNITY_Map Configuration State|Map Configuration State]]
- [[_COMMUNITY_Model Registry & Raster API|Model Registry & Raster API]]
- [[_COMMUNITY_Version & Git Metadata|Version & Git Metadata]]
- [[_COMMUNITY_Admin Panel Classes|Admin Panel Classes]]
- [[_COMMUNITY_Administrative Hierarchy Saves|Administrative Hierarchy Saves]]
- [[_COMMUNITY_Population Signal Cascade|Population Signal Cascade]]
- [[_COMMUNITY_Django Entry Point|Django Entry Point]]
- [[_COMMUNITY_Geospatial Utilities|Geospatial Utilities]]
- [[_COMMUNITY_Django Settings|Django Settings]]
- [[_COMMUNITY_Isolated Model Admin|Isolated Model Admin]]
- [[_COMMUNITY_OPEX Water Model|OPEX Water Model]]
- [[_COMMUNITY_Pipe Network Model|Pipe Network Model]]
- [[_COMMUNITY_Water Consumption Signals|Water Consumption Signals]]
- [[_COMMUNITY_Environmental Costs Migration|Environmental Costs Migration]]
- [[_COMMUNITY_Neighborhood Schema Migration|Neighborhood Schema Migration]]
- [[_COMMUNITY_District ID Migration|District ID Migration]]
- [[_COMMUNITY_ASGI Config|ASGI Config]]
- [[_COMMUNITY_WSGI Config|WSGI Config]]
- [[_COMMUNITY_Housing Supply Migration|Housing Supply Migration]]
- [[_COMMUNITY_Watershed Schema Migration|Watershed Schema Migration]]
- [[_COMMUNITY_Extraction Water Migration|Extraction Water Migration]]
- [[_COMMUNITY_Imported Water Migration|Imported Water Migration]]
- [[_COMMUNITY_Coverage Migration|Coverage Migration]]
- [[_COMMUNITY_GEE Authentication|GEE Authentication]]
- [[_COMMUNITY_PDOK WFS Fetch|PDOK WFS Fetch]]
- [[_COMMUNITY_PDOK WCS Raster Fetch|PDOK WCS Raster Fetch]]
- [[_COMMUNITY_PDOK ATOM Raster Download|PDOK ATOM Raster Download]]
- [[_COMMUNITY_WMS Layer Registration|WMS Layer Registration]]
- [[_COMMUNITY_CBS OData Fetch|CBS OData Fetch]]
- [[_COMMUNITY_CBS Column Definitions|CBS Column Definitions]]
- [[_COMMUNITY_Sentinel-2 WCS Fetch|Sentinel-2 WCS Fetch]]
- [[_COMMUNITY_Sentinel Hub Process API|Sentinel Hub Process API]]
- [[_COMMUNITY_Sentinel-2 WMS Registration|Sentinel-2 WMS Registration]]
- [[_COMMUNITY_GEE Raster Export|GEE Raster Export]]
- [[_COMMUNITY_NRW Loss Factory|NRW Loss Factory]]
- [[_COMMUNITY_Province Raster Generator|Province Raster Generator]]
- [[_COMMUNITY_PostGIS Spatial Database|PostGIS Spatial Database]]

## God Nodes (most connected - your core abstractions)
1. `City` - 54 edges
2. `Neighborhood` - 54 edges
3. `Province` - 36 edges
4. `ElectricityCost` - 26 edges
5. `EnvironmentalCosts` - 23 edges
6. `InterpolatedRasterBase` - 17 edges
7. `_get_province_data()` - 16 edges
8. `_get_province_data()` - 13 edges
9. `import_dataset()` - 13 edges
10. `EnergyEfficiencyLabels` - 12 edges

## Surprising Connections (you probably didn't know these)
- `DPSIR Causal Framework` --semantically_similar_to--> `Water Indicators Dashboard Template`  [INFERRED] [semantically similar]
  CLAUDE.md → watersupply/templates/watersupply/water_indicators.html
- `DPSIR Causal Framework` --semantically_similar_to--> `Urban Heat Indicators Dashboard Template`  [INFERRED] [semantically similar]
  CLAUDE.md → urban_heat/templates/urban_heat/heat_indicators.html
- `Water Indicators Panel Partial` --semantically_similar_to--> `Urban Heat Indicators Panel Partial`  [INFERRED] [semantically similar]
  watersupply/templates/watersupply/partials/indicators_panel.html → urban_heat/templates/urban_heat/partials/indicators_panel.html
- `ZoningArea` --uses--> `Neighborhood`  [INFERRED]
  builtup/models.py → common/models.py
- `Meta` --uses--> `Neighborhood`  [INFERRED]
  builtup/models.py → common/models.py

## Hyperedges (group relationships)
- **HTMX Indicator Dashboard Pattern** — rationale_htmx_dashboard, water_indicators_html, water_indicators_grid_html, water_indicators_panel_html, heat_indicators_html, heat_indicators_grid_html, heat_indicators_panel_html [EXTRACTED 0.95]
- **COG Raster Processing Pipeline** — rationale_raster_pipeline, dep_rasterio, dep_rio_cogeo, dep_titiler [EXTRACTED 1.00]
- **Importer Upload Workflow** — importer_upload_html, importer_fieldmapping_html, importer_rastermapping_html, importer_upload_result_html, importer_external_data_html [INFERRED 0.85]

## Communities (114 total, 33 thin omitted)

### Community 0 - "External Data Catalog & Import"
Cohesion: 0.06
Nodes (36): get_catalog_grouped(), Return the catalog grouped by source, then by category.     Structure: { source, CBSImporter, ensure_multipolygon(), export_raster(), fetch_atom(), fetch_process_api(), fetch_wcs() (+28 more)

### Community 1 - "Raster Generation & Metadata"
Cohesion: 0.06
Nodes (19): generate_for_Province(), HumidityRaster, InterpolatedRasterBase, PrecipitationRaster, Calculate bounds polygon from the raster's extent, Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field                  Args (+11 more)

### Community 2 - "Platform Architecture & Dependencies"
Cohesion: 0.08
Nodes (38): Base HTML Template, CrossTwin Platform, Django Web Framework, Google Earth Engine API, FastAPI (TiTiler), GeoPandas, HTMX Library, Mapbox GL JS (+30 more)

### Community 3 - "Water Supply Calculations"
Cohesion: 0.09
Nodes (34): calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage(), calculate_drought_area(), calculate_energy_consumption(), calculate_nrw(), calculate_opex_recovery() (+26 more)

### Community 4 - "Environmental & Economic Models"
Cohesion: 0.12
Nodes (18): EnvironmentalCosts, Province, ElectricityCost, WMSLayerAdmin, AreaAffectedDrought, AvailableFreshWater, ConsumptionCapita, ImportedWater (+10 more)

### Community 5 - "Geospatial Upload Forms"
Cohesion: 0.09
Nodes (28): GeoUploadForm, get_target_model_choices(), MappingForm, Dynamic form for field mapping.     Fields are added dynamically in the view ba, Get choices for target model field., Form for uploading geodata files (GeoJSON or Shapefile)., Validate uploaded file has correct extension., Validate source CRS is a valid EPSG code. (+20 more)

### Community 6 - "Map Frontend JavaScript"
Cohesion: 0.09
Nodes (17): fetch(), updateCityName(), initializeUI(), addLayer(), addRasterLayer(), addRasterLayerFromConfig(), addWmsLayer(), addWmsLegend() (+9 more)

### Community 7 - "Housing Indicator Calculations"
Cohesion: 0.1
Nodes (28): calculate_affordability(), calculate_house_price_index(), calculate_mortgage_indicators(), calculate_new_units(), calculate_new_units_province(), calculate_property_indicators(), calculate_rent_indicators(), calculate_supply_demand() (+20 more)

### Community 8 - "Urban Heat Raster Models"
Cohesion: 0.07
Nodes (18): LandSurfaceTemperature, MeanRadiantTemperature, Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, PET, Land Surface Temperature (LST) measurements, Surface Urban Heat Island Intensity (SUHII)) measurements (+10 more)

### Community 9 - "Nature & Thermal Comfort"
Cohesion: 0.11
Nodes (26): calculate_green_area(), calculate_nbs_coverage(), calculate_urban_morphology(), calculate_vegetation_coverage(), classify_pet(), classify_utci(), get_latest_meteorology(), get_thermal_indices() (+18 more)

### Community 10 - "Django App Configurations"
Cohesion: 0.08
Nodes (12): AppConfig, BuiltupConfig, CommonConfig, CoreConfig, EnergyConfig, HousingConfig, ImporterConfig, MainmapConfig (+4 more)

### Community 11 - "Built Environment Models"
Cohesion: 0.19
Nodes (11): Building, Facility, Meta, Park, Property, Street, ZoningArea, City (+3 more)

### Community 12 - "Housing Finance Models"
Cohesion: 0.1
Nodes (9): CentralBankPolicy, CreditSupplyConditions, HousePriceIndex, HousingAffordability, HousingProject, HousingSupplyDemand, Meta, Mortgage (+1 more)

### Community 13 - "Elevation & WMS Layers"
Cohesion: 0.11
Nodes (9): DigitalElevationModel, DigitalElevationModelWMS, DigitalSurfaceModel, DigitalSurfaceModelWMS, LandCoverClasses, LandCoverRaster, LandCoverVector, LandCoverWMS (+1 more)

### Community 14 - "Water Infrastructure Models"
Cohesion: 0.12
Nodes (6): CoverageWaterSupply, ExtractionWater, generate_random_event(), MeteredResidential, NonRevenueWater, TotalWaterDemand

### Community 15 - "Test Factories & Fixtures"
Cohesion: 0.24
Nodes (11): TestCase, make_city(), make_consumption_capita(), make_metered_residential(), make_neighborhood(), make_polygon(), make_province(), make_users_location() (+3 more)

### Community 16 - "COG Export Command"
Cohesion: 0.13
Nodes (12): BaseCommand, Command, export_all_rasters(), export_raster_to_cog(), get_raster_field_name(), interpolate_raster(), Export any model instance with a RasterField to a COG.          instance:  the, Export all rasters that don't have a COG yet. (+4 more)

### Community 17 - "Administrative & Meteorology Models"
Cohesion: 0.19
Nodes (7): Neighborhood, WMSLayer, Meta, Meteorology, Time-series weather measurements from stations, WeatherStation, WMSLayer

### Community 18 - "PostGIS Test Infrastructure"
Cohesion: 0.25
Nodes (5): _patched_prepare_database(), PostGISTestRunner, Replace the PostGIS backend's prepare_database so it does NOT try to     CREATE, Return the exact test DB name — respecting explicit TEST.NAME.         Do NOT a, DiscoverRunner

### Community 19 - "Nature & Protected Areas"
Cohesion: 0.18
Nodes (6): Forests, Meta, ProtectedArea, ProtectionType, WaterBodies, WaterWays

### Community 20 - "Raster Signal Handlers"
Cohesion: 0.25
Nodes (10): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), Create a view that always shows the latest raster, Create a database view for a single raster, Delete the view when a raster is deleted (+2 more)

### Community 21 - "Map API Views"
Cohesion: 0.2
Nodes (8): available_layers(), layer_bounds(), map_view(), model_geojson(), Display the map page., Returns the bounding box extent of a layer.     URL: /api/<app_label>/<model_na, Generic GeoJSON endpoint for any registered model.     URL: /api/<app_label>/<m, Returns a list of all available layers (models with geometry fields).     URL:

### Community 23 - "Map Configuration State"
Cohesion: 0.25
Nodes (7): availableLayers, BASEMAPS, CONFIG, layerVisibility, loadedLayers, TOOL_CATEGORIES, TOOL_CONTENT

### Community 24 - "Model Registry & Raster API"
Cohesion: 0.25
Nodes (6): build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., get_raster_info(), get_raster_tiles(), Return TiTiler tile URL for a given raster layer., Return raster metadata including bounds.

### Community 25 - "Version & Git Metadata"
Cohesion: 0.38
Nodes (6): _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count.     0–99   → v0.1,  100–19, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime.     In dev, version_context()

### Community 26 - "Admin Panel Classes"
Cohesion: 0.33
Nodes (5): CityAdmin, LandCoverClassesAdmin, NeighborhoodAdmin, ProvinceAdmin, SurfaceMaterialPropertiesAdmin

### Community 28 - "Population Signal Cascade"
Cohesion: 0.53
Nodes (5): city_changed(), district_changed(), neighborhood_changed(), Recompute currentPopulation and populationDensity for a parent record     by sum, _recompute_population()

## Knowledge Gaps
- **172 isolated node(s):** `Run administrative tasks.`, `ProvinceAdmin`, `CityAdmin`, `NeighborhoodAdmin`, `LandCoverClassesAdmin` (+167 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **33 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Neighborhood` connect `Administrative & Meteorology Models` to `Isolated Model Admin`, `OPEX Water Model`, `Pipe Network Model`, `Environmental & Economic Models`, `Raster Generation & Metadata`, `Urban Heat Raster Models`, `Built Environment Models`, `Elevation & WMS Layers`, `Water Infrastructure Models`, `Administrative Hierarchy Saves`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `City` connect `Built Environment Models` to `Isolated Model Admin`, `OPEX Water Model`, `Pipe Network Model`, `Environmental & Economic Models`, `Raster Generation & Metadata`, `Urban Heat Raster Models`, `Elevation & WMS Layers`, `Water Infrastructure Models`, `Administrative & Meteorology Models`, `Administrative Hierarchy Saves`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `InterpolatedRasterBase` connect `Raster Generation & Metadata` to `Administrative & Meteorology Models`, `Built Environment Models`, `Environmental & Economic Models`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 51 inferred relationships involving `City` (e.g. with `ZoningArea` and `Meta`) actually correct?**
  _`City` has 51 INFERRED edges - model-reasoned connections that need verification._
- **Are the 51 inferred relationships involving `Neighborhood` (e.g. with `ZoningArea` and `Meta`) actually correct?**
  _`Neighborhood` has 51 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `Province` (e.g. with `ElectricityCost` and `Meta`) actually correct?**
  _`Province` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `ElectricityCost` (e.g. with `Province` and `City`) actually correct?**
  _`ElectricityCost` has 24 INFERRED edges - model-reasoned connections that need verification._