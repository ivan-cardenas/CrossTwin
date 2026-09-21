# Graph Report - CrossTwin  (2026-09-21)

## Corpus Check
- 163 files · ~109,749 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 5, .css 3, .tif 2)

## Summary
- 1110 nodes · 1923 edges · 134 communities (53 shown, 39 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 216 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8de66ba3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- housing/calculations.py
- mainMap/views.py
- City
- watersupply/calculations.py
- Layers.js
- watersupply/models.py
- importer/views.py
- physicalEnv/models.py
- rasterOperations.py
- test_water_chain.py
- weather/views.py
- Model Registry System (MODEL/VECTOR/RASTER/WMS_REGISTRY)
- external_data.py
- urban_heat/calculations.py
- Indicator Pattern (calculations / views / HTMX templates)
- GEEAuthManager
- watersupply indicators_grid.html (HTMX swap partial)
- housing indicators_grid.html (HTMX swap partial)
- urban heat indicators_grid.html (HTMX swap partial)
- nature/models.py
- Meta
- .generate_from_measurements
- Map_init.js
- GenericImportStorageCrsTests
- housing/views.py
- import_dataset
- /graphify Command
- base.html (site shell template)
- weather/signals.py
- load_raster_into_target_model
- .setup_databases
- requirements.txt
- Meta
- mainMap.html (map view template)
- CrossTwin – Plan: model automation, population scenario, dashboard toggle, KNMI WBGT
- Config.js
- _get_git_info
- .save
- NonRevenueWater
- CBSImporter
- default_wms_legend_url
- watersupply/signals.py
- Digital twin concept: real city (left) mirrored by wireframe model (right)
- builtup/models.py
- external_data.html Template
- importer:upload_geodata view
- PrecipitationRaster
- TemperatureRaster
- AdministrativeConfig
- CoreConfig
- CrossTwin App Icon (192x192)
- MapUI.js
- 0002_populate_energy_labels.py
- manage.py
- InterpolatedRasterBase
- .fetch_atom
- Migration
- WeatherConfig
- BuiltupConfig
- get_area
- CrossTwin App Icon (apple-touch-icon)
- CrossTwin favicon 16x16
- CrossTwin favicon (32x32)
- settings.py
- EnergyConfig
- HousingConfig
- ImporterConfig
- MainmapConfig
- NatureConfig
- PhysicalEnvConfig
- UrbanheatConfig
- WatersupplyConfig
- administrative/migrations/0001_initial.py
- builtup/migrations/0001_initial.py
- CLAUDE.md (project guidance)
- asgi.py
- wsgi.py
- Energy/migrations/0001_initial.py
- housing/migrations/0001_initial.py
- nature/migrations/0001_initial.py
- physicalEnv/migrations/0001_initial.py
- urban_heat/migrations/0001_initial.py
- 0002_landsurfacetemperature_measurement_method_and_more.py
- 0003_landsurfacetemperature_cog_path_and_more.py
- watersupply/migrations/0001_initial.py
- weather/migrations/0001_initial.py
- 0002_wmslayer_has_time_dimension_and_more.py
- 0003_wmslayer_time_refresh_minutes.py
- 0004_wmslayer_api_key_setting.py
- AppConfig
- StyleSuggestion.md (design system suggestion)
- Project TODO List

## God Nodes (most connected - your core abstractions)
1. `City` - 38 edges
2. `Province` - 29 edges
3. `Neighborhood` - 28 edges
4. `make_city()` - 18 edges
5. `neighborhoods_within()` - 17 edges
6. `import_dataset()` - 17 edges
7. `Meta` - 17 edges
8. `_get_province_data()` - 17 edges
9. `InterpolatedRasterBase` - 17 edges
10. `Building` - 15 edges

## Surprising Connections (you probably didn't know these)
- `External Data Import (PDOK, RIVM, CBS, Sentinel-2, GEE)` --semantically_similar_to--> `Importer System (file upload + external data)`  [INFERRED] [semantically similar]
  README.md → CLAUDE.md
- `Visualization Layer (TiTiler/Mapbox GL)` --semantically_similar_to--> `Raster Pipeline (PostGIS raster to COG to TiTiler)`  [INFERRED] [semantically similar]
  ImporterArchitecture.html → CLAUDE.md
- `Data Import Zone (GeoTIFF/Vector/API/Tabular Sources)` --semantically_similar_to--> `External Data Import (PDOK, RIVM, CBS, Sentinel-2, GEE)`  [INFERRED] [semantically similar]
  SystemArchitecuture.html → README.md
- `Processing & Export Zone (COG Conversion)` --semantically_similar_to--> `Raster Pipeline (PostGIS raster to COG to TiTiler)`  [INFERRED] [semantically similar]
  SystemArchitecuture.html → CLAUDE.md
- `Application Layer (Django REST Parsers/Validation)` --semantically_similar_to--> `Importer System (file upload + external data)`  [INFERRED] [semantically similar]
  ImporterArchitecture.html → CLAUDE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **External Import Credentials + BBox Selection Flow** — importer_templates_external_data_html, importer_bbox_area_selector_ui, importer_templates_importer_external_data_fetch_openeo, importer_start_external_import_endpoint, importer_neighborhoods_geojson_endpoint [EXTRACTED 1.00]
- **Shared ? info button and popover help system** — templates_partials__info_btn, templates_partials__info_popover, watersupply_templates_watersupply_partials_indicators_grid, housing_templates_housing_partials_indicators_grid, urban_heat_templates_urban_heat_partials_indicators_grid [EXTRACTED 1.00]
- **Map toolbar to admin-unit indicator panel wiring** — mainmap_templates_mainmap_toolbar, mainmap_templates_mainmap_admin_panel_tools, mainmap_templates_mainmap_syncpanelbtns, mainmap_templates_mainmap_refreshactivepanel, mainmap_templates_mainmap_side_panel [EXTRACTED 1.00]
- **CrossTwin icon composition: physical city, digital wireframe, orbit ring** — core_static_ico_android_chrome_512x512_isometric_city_block, core_static_ico_android_chrome_512x512_cyan_wireframe_grid, core_static_ico_android_chrome_512x512_orbit_ring [INFERRED 0.85]
- **HTMX slider-driven what-if recalculation pattern** — watersupply_templates_watersupply_partials_indicators_panel_consumption_slider, housing_templates_housing_partials_indicators_panel_mortgage_slider, urban_heat_templates_urban_heat_partials_indicators_panel_vegetation_slider, claude_indicator_pattern [INFERRED 0.95]

## Communities (134 total, 39 thin omitted)

### Community 0 - "housing/calculations.py"
Cohesion: 0.10
Nodes (23): neighborhoods_within(), Neighborhood queryset covering the given administrative unit, at any level., Property, calculate_mortgage_indicators(), calculate_new_units(), calculate_property_indicators(), calculate_rent_indicators(), calculate_supply_demand() (+15 more)

### Community 1 - "mainMap/views.py"
Cohesion: 0.07
Nodes (38): Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…, _cog_statistics() (+30 more)

### Community 2 - "City"
Cohesion: 0.13
Nodes (18): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any…, Resolve the enclosing Province for an admin unit at any level. Needed for…, City, District (+10 more)

### Community 3 - "watersupply/calculations.py"
Cohesion: 0.09
Nodes (39): cities_within(), City queryset covering the given administrative unit, at any level., calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage(), calculate_drought_area(), calculate_energy_consumption() (+31 more)

### Community 4 - "Layers.js"
Cohesion: 0.10
Nodes (37): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+29 more)

### Community 5 - "watersupply/models.py"
Cohesion: 0.11
Nodes (11): WMSLayerAdmin, AreaAffectedDrought, AvailableFreshWater, ConsumptionCapita, ImportedWater, Meta, MeteredResidential, PipeNetwork (+3 more)

### Community 6 - "importer/views.py"
Cohesion: 0.05
Nodes (43): atomic, ModelRegistryTests, SimpleTestCase, A typo in allowed_apps is swallowed silently (LookupError), dropping the whole…, build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., get_catalog_grouped(), Return the catalog grouped by category. Structure: { category: [datasets] }… (+35 more)

### Community 7 - "physicalEnv/models.py"
Cohesion: 0.11
Nodes (11): LandCoverClassesAdmin, SurfaceMaterialPropertiesAdmin, DigitalElevationModel, DigitalElevationModelWMS, DigitalSurfaceModelWMS, LandCoverClasses, LandCoverRaster, LandCoverWMS (+3 more)

### Community 8 - "rasterOperations.py"
Cohesion: 0.14
Nodes (16): BaseCommand, Command, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), get_raster_field_name(), Build a COG filename from whatever satellite/process metadata the raster model… (+8 more)

### Community 9 - "test_water_chain.py"
Cohesion: 0.07
Nodes (26): EnvironmentalCosts, The most recent cost record (the model has no province/year), or None., DAG edges: Available_FW -> Total_Extraction Total_Extraction ->…, make_city(), make_consumption_capita(), make_district(), make_metered_residential(), make_neighborhood() (+18 more)

### Community 10 - "weather/views.py"
Cohesion: 0.16
Nodes (16): WMSLayer, _fetch_with_retry(), _find_dimension_values(), _last_n_time_steps(), _local_tag(), _parse_iso8601(), _parse_iso8601_duration(), Resolve the most recent time steps for an animated WMS layer. Fetches and… (+8 more)

### Community 11 - "Model Registry System (MODEL/VECTOR/RASTER/WMS_REGISTRY)"
Cohesion: 0.12
Nodes (18): Importer System (file upload + external data), Map Frontend (mainMap, Mapbox GL JS), Model Registry System (MODEL/VECTOR/RASTER/WMS_REGISTRY), Application Layer (Django REST Parsers/Validation), Data Layer (PostgreSQL/PostGIS/GeoDjango ORM), Import Layer (File Upload UI), Visualization Layer (TiTiler/Mapbox GL), Right actions panel (Upload Data, Retrieve Data from APIs) (+10 more)

### Community 12 - "external_data.py"
Cohesion: 0.18
Nodes (13): Exception, GEOSGeometry, ensure_multipolygon(), GEEImporter, _import_geojson_features(), _ImportBlocked, External Data Catalog & Import Logic =====================================…, Import handler for Google Earth Engine datasets. (+5 more)

### Community 13 - "urban_heat/calculations.py"
Cohesion: 0.09
Nodes (30): DigitalSurfaceModel, calculate_green_area(), calculate_nbs_coverage(), calculate_urban_morphology(), calculate_vegetation_coverage(), classify_pet(), classify_utci(), get_latest_meteorology() (+22 more)

### Community 14 - "Indicator Pattern (calculations / views / HTMX templates)"
Cohesion: 0.13
Nodes (16): CrossTwin Digital Twin Platform, core/DAG.dot causal network, Domain Apps (administrative, physicalEnv, watersupply, urban_heat, housing, builtup, ...), DPSIR Framework (Driver-Pressure-State-Impact-Response), Indicator Pattern (calculations / views / HTMX templates), MOCK_DATA fallback dicts, PostGISTestRunner, Raster Pipeline (PostGIS raster to COG to TiTiler) (+8 more)

### Community 15 - "GEEAuthManager"
Cohesion: 0.33
Nodes (3): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE with service account credentials.

### Community 16 - "watersupply indicators_grid.html (HTMX swap partial)"
Cohesion: 0.24
Nodes (15): DAG Edge Coverage Gaps (28 of 102 edges implemented), Nature-Based Solutions (NBS) indicator, Vegetation Coverage indicator, watersupply indicators_grid.html (HTMX swap partial), Non-Revenue Water (NRW / ILI) indicator, OPEX indicator, Service Time indicator, Supply Security indicator (+7 more)

### Community 17 - "housing indicators_grid.html (HTMX swap partial)"
Cohesion: 0.19
Nodes (15): housing indicators_grid.html (HTMX swap partial), Affordability (Price-to-Income) indicator, Affordability Stress distribution indicator, House Price Index indicator, Average Fixed Mortgage Rate indicator, New Housing Units / Supply Deficit indicator, Property Market indicator, Rental Market indicator (+7 more)

### Community 18 - "urban heat indicators_grid.html (HTMX swap partial)"
Cohesion: 0.21
Nodes (15): initGauges (housing gauges + mortgage bar), heat_indicators.html (standalone urban heat page), initGauges (urban heat standalone), urban heat indicators_grid.html (HTMX swap partial), Land Surface Temperature (LST) gauge, Current Meteorology indicator, PET gauge (Physiological Equivalent Temperature), Surface Urban Heat Island Intensity (SUHII) indicator (+7 more)

### Community 19 - "nature/models.py"
Cohesion: 0.16
Nodes (8): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, WaterBodies, WaterWaysLN, WaterWaysPG

### Community 20 - "Meta"
Cohesion: 0.08
Nodes (17): MeanRadiantTemperature, Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, PET, Physiological Equivalent Temperature (PET) measurements, Surface Urban Heat Island Intensity (SUHII)) measurements, Nature-Based Solutions (NBS) for urban heat mitigation (+9 more)

### Community 21 - ".generate_from_measurements"
Cohesion: 0.15
Nodes (8): interpolate_raster(), Interpolates raster data using Radial Basis Function (RBF) interpolation.…, HumidityRaster, Determine bounds for interpolation, Get measurements within time window for a specific field Args:…, Generate raster by interpolating measurements Must be implemented by child…, Generic interpolation method - works for all child classes, Interpolated relative humidity raster layer

### Community 22 - "Map_init.js"
Cohesion: 0.24
Nodes (11): updateCityName(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, changeBasemap(), getSavedCameraState(), initializeUrbanTwinMap(), onAdminLayerLoaded() (+3 more)

### Community 23 - "GenericImportStorageCrsTests"
Cohesion: 0.25
Nodes (6): GenericImportStorageCrsTests, GeoJsonFeatureImportStorageCrsTests, TestCase, _generic_import must store every geometry in COORDINATE_SYSTEM., PDOK/OGC feature imports honour the requested srsName but store in RD., _wgs84_frame()

### Community 24 - "housing/views.py"
Cohesion: 0.13
Nodes (20): Look up a Province/City/District/Neighborhood instance by level + name., resolve_admin_unit(), calculate_affordability(), calculate_house_price_index(), calculate_new_units_for_unit(), calculate_supply_demand_for_unit(), calculate_zoning(), House price index aggregated across neighborhoods. DAG edges: Housing_Demand ->… (+12 more)

### Community 25 - "import_dataset"
Cohesion: 0.12
Nodes (16): get_model_class(), import_dataset(), ImportResult, PDOKImporter, Fetch raster data from PDOK WCS service, tiling the request when the area would…, Register a WMS layer by creating/updating its row in the target WMS model. This…, Fetch tabular data from CBS OData API and import to Django model. Args:…, Register a Sentinel-2 WMS layer by creating/updating its row in the target WMS… (+8 more)

### Community 26 - "/graphify Command"
Cohesion: 0.21
Nodes (12): graphify Project Rule, /graphify add and --watch, Extra Exports and Benchmark, Confidence Score Rubric, Extraction Subagent Prompt Spec, GitHub Clone and Cross-Repo Merge, Commit Hook and CLAUDE.md Integration, graphify Query, Path, Explain (+4 more)

### Community 27 - "base.html (site shell template)"
Cohesion: 0.20
Nodes (12): housing_indicators.html (standalone housing page), Dark Glassmorphism Theme, Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono), base.html (site shell template), Template blocks (extra_css, extra_js, content) (+4 more)

### Community 28 - "weather/signals.py"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 29 - "load_raster_into_target_model"
Cohesion: 0.24
Nodes (8): datetime, load_raster_into_target_model(), Import handler for Sentinel-2 datasets., Look up the real acquisition timestamp of the most recent Sentinel-2 L2A scene…, Fetch raster from Sentinel-2 WCS (e.g., WorldCover)., Fetch processed Sentinel-2 imagery via the Copernicus Data Space Ecosystem's…, Load a downloaded raster file into its catalog entry's target_model. The…, Sentinel2Importer

### Community 30 - ".setup_databases"
Cohesion: 0.29
Nodes (5): _patched_prepare_database(), PostGISTestRunner, Replace the PostGIS backend's prepare_database so it does NOT try to CREATE…, Return the exact test DB name — respecting explicit TEST.NAME. Do NOT add…, DiscoverRunner

### Community 31 - "requirements.txt"
Cohesion: 0.18
Nodes (10): django-crispy-forms + crispy-tailwind, Django 5.2.12, earthengine-api 1.7.18, GDAL 3.11.4 (Windows wheel), geopandas 1.1.2, openeo 0.51.0, owslib 0.35.0, rasterio 1.4.4 (+2 more)

### Community 32 - "Meta"
Cohesion: 0.18
Nodes (6): Meta, Meteorology, Interpolated wind speed raster layer, Time-series weather measurements from stations, WeatherStation, WindSpeedRaster

### Community 33 - "mainMap.html (map view template)"
Cohesion: 0.31
Nodes (9): mainMap.html (map view template), ADMIN_PANEL_TOOLS registry (water, temperature, Housing), refreshActivePanel(), Side panel (#panel-body htmx target), syncPanelBtns(), Left thematic toolbar (hx-get triggers), WMS time scrubber dock, Year selector (ACTIVE_YEAR) (+1 more)

### Community 34 - "CrossTwin – Plan: model automation, population scenario, dashboard toggle, KNMI WBGT"
Cohesion: 0.10
Nodes (20): 1. Model `save()` audit + cross-model signals  ☐, 2. Population curve from CBS 85173NED  ☐, 3. Dashboard button toggles the indicators panel  ☐, 4. KNMI WBGT import ("latest heat force")  ☐, After every phase, Bugs found during exploration (not yet fixed), Change log (fill in during implementation), Context (+12 more)

### Community 35 - "Config.js"
Cohesion: 0.25
Nodes (7): availableLayers, BASEMAPS, CONFIG, layerVisibility, loadedLayers, TOOL_CATEGORIES, TOOL_CONTENT

### Community 36 - "_get_git_info"
Cohesion: 0.32
Nodes (6): _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. 0–99 → v0.1, 100–199 →…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 37 - ".save"
Cohesion: 0.11
Nodes (8): CoverageWaterSupply, DAG edges: Total_Water_Demand -> Supply_Security Total_Water_Prod ->…, DAG edges: Total_Population -> Total_Consumption ConsumptionCapita ->…, DAG edges: Total_Extraction/Total_Water_Prod -> OPEX Imported_Water -> OPEX,…, DAG edges: Total_Population -> Total_Water_Demand ConsumptionCapita ->…, Derived from the geometry: affected area (km2) and, if not given, the Province., Set productionDay/YR (Mm3) and costDay/YR (EUR) from the active wells of the…, TotalWaterDemand

### Community 38 - "NonRevenueWater"
Cohesion: 0.29
Nodes (4): LossesChoices, LossesTypes, NonRevenueWater, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 39 - "CBSImporter"
Cohesion: 0.50
Nodes (3): CBSImporter, Import handler for CBS StatLine OData datasets., Fetch column definitions and units for a CBS table. Useful for building field…

### Community 40 - "default_wms_legend_url"
Cohesion: 0.40
Nodes (4): default_wms_legend_url(), _legend_url_from_capabilities(), Look up a layer's <LegendURL><OnlineResource xlink:href="..."/> from the WMS…, Resolve a legend image URL for a WMS layer, used as a fallback when a catalog…

### Community 41 - "watersupply/signals.py"
Cohesion: 0.15
Nodes (26): OPEX, SupplySecurity, TotalWaterProduction, city_population_cascaded(), city_saved(), consumption_saved(), demand_saved(), extraction_changed() (+18 more)

### Community 42 - "Digital twin concept: real city (left) mirrored by wireframe model (right)"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 43 - "builtup/models.py"
Cohesion: 0.13
Nodes (11): Building, BuildingEnergyLabel, Facility, Meta, Park, Proxy onto Building, filed under the Energy app so the energy-label fields…, Street, ZoningArea (+3 more)

### Community 44 - "external_data.html Template"
Cohesion: 0.40
Nodes (5): Bbox Area-of-Interest Map Selector UI, importer:neighborhoods_geojson endpoint, importer:start_external_import endpoint, external_data.html Template, external_data.py fetch_openeo

### Community 45 - "importer:upload_geodata view"
Cohesion: 0.50
Nodes (5): FieldMapping.html Template, RasterMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 50 - "CrossTwin App Icon (192x192)"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 53 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 54 - "InterpolatedRasterBase"
Cohesion: 0.16
Nodes (7): InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Convert extent tuple to Polygon, Extract point data from measurements Args: measurements: QuerySet of…, Convenience method to generate raster for a Province Args: Province: Province…, Override in child classes to specify which measurement field to use, Override in child classes to specify metadata keys Returns tuple: (min_key,…

### Community 55 - ".fetch_atom"
Cohesion: 0.23
Nodes (7): _import_atom_gml_features(), Stream a plu:SpatialPlan GML file (INSPIRE Planned Land Use) over HTTP and…, SimpleTestCase, ToStorageSridTests, _to_multipolygon(), MultiPolygon, Polygon

### Community 60 - "CrossTwin App Icon (apple-touch-icon)"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 61 - "CrossTwin favicon 16x16"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 62 - "CrossTwin favicon (32x32)"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

## Ambiguous Edges - Review These
- `Domain Apps (administrative, physicalEnv, watersupply, urban_heat, housing, builtup, ...)` → `Dynamic Layer Categories (Heat, Green, Water, Groundwater)`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to

## Knowledge Gaps
- **101 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `availableLayers` (+96 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 500 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **39 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Domain Apps (administrative, physicalEnv, watersupply, urban_heat, housing, builtup, ...)` and `Dynamic Layer Categories (Heat, Green, Water, Groundwater)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `City` connect `City` to `housing/calculations.py`, `watersupply/calculations.py`, `watersupply/models.py`, `importer/views.py`, `CBSImporter`, `.save`, `watersupply/signals.py`, `test_water_chain.py`, `builtup/models.py`, `external_data.py`, `nature/models.py`, `load_raster_into_target_model`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Why does `Province` connect `City` to `housing/calculations.py`, `watersupply/calculations.py`, `watersupply/models.py`, `watersupply/signals.py`, `test_water_chain.py`, `external_data.py`, `InterpolatedRasterBase`, `GenericImportStorageCrsTests`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `Neighborhood` connect `City` to `housing/calculations.py`, `watersupply/calculations.py`, `watersupply/models.py`, `importer/views.py`, `.save`, `test_water_chain.py`, `builtup/models.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Province` (e.g. with `ProvinceAdmin` and `cities_within()`) actually correct?**
  _`Province` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 13 INFERRED edges - model-reasoned connections that need verification._