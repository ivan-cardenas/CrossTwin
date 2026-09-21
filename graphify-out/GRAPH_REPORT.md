# Graph Report - CrossTwin  (2026-09-21)

## Corpus Check
- 169 files · ~117,561 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 19 file(s) not represented in the graph (top: (none) 5, .css 3, .tif 2)

## Summary
- 1292 nodes · 2352 edges · 144 communities (62 shown, 40 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 235 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `69378057`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- housing/calculations.py
- mainMap/views.py
- City
- watersupply/calculations.py
- Layers.js
- test_water_chain.py
- importer/views.py
- physicalEnv/models.py
- rasterOperations.py
- make_city
- weather/views.py
- Model Registry System (MODEL/VECTOR/RASTER/WMS_REGISTRY)
- external_data.py
- urban_heat/views.py
- Indicator Pattern (calculations / views / HTMX templates)
- import_dataset
- watersupply indicators_grid.html (HTMX swap partial)
- housing indicators_grid.html (HTMX swap partial)
- urban heat indicators_grid.html (HTMX swap partial)
- Meta
- Meta
- test_charts.py
- Map_init.js
- get_model_class
- urban_heat/calculations.py
- ImportResult
- /graphify Command
- base.html (site shell template)
- weather/signals.py
- load_raster_into_target_model
- .setup_databases
- requirements.txt
- weather/models.py
- mainMap.html (map view template)
- CrossTwin – Plan: model automation, population scenario, dashboard toggle, KNMI WBGT
- Config.js
- _get_git_info
- rasterStyles.py
- PopulationDockTests
- core/views.py
- mainMap/urls.py
- watersupply/signals.py
- Digital twin concept: real city (left) mirrored by wireframe model (right)
- ExtractionAndProductionTests
- external_data.html Template
- importer:upload_geodata view
- factories.py
- TemperatureRaster
- AdministrativeConfig
- CoreConfig
- CrossTwin App Icon (192x192)
- MapUI.js
- 0002_populate_energy_labels.py
- manage.py
- InterpolatedRasterBase
- to_storage_srid
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
- calculate_nbs_coverage
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
- PopulationDrivesTheIndicatorsTests
- population_panel
- PDOKImporter
- StyleSuggestion.md (design system suggestion)
- Project TODO List
- core/utils.py
- resolve_admin_unit_at_point
- 0002_population_projection.py
- calculate_green_area
- get_thermal_indices
- StressCategory
- UTCI

## God Nodes (most connected - your core abstractions)
1. `City` - 42 edges
2. `make_city()` - 36 edges
3. `Province` - 32 edges
4. `Neighborhood` - 31 edges
5. `PopulationProjection` - 21 edges
6. `get_population()` - 21 edges
7. `_get_province_data()` - 18 edges
8. `neighborhoods_within()` - 17 edges
9. `import_dataset()` - 17 edges
10. `PopulationDockTests` - 17 edges

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

## Communities (144 total, 40 thin omitted)

### Community 0 - "housing/calculations.py"
Cohesion: 0.05
Nodes (49): neighborhoods_within(), Neighborhood queryset covering the given administrative unit, at any level., population_params(), (scenario, growth_adjust_pct) from a request's query parameters `pop_scenario`…, PopulationParamsTests, Building, BuildingEnergyLabel, Meta (+41 more)

### Community 1 - "mainMap/views.py"
Cohesion: 0.21
Nodes (11): build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…, available_layers(), _extract_unit(), _field_metadata() (+3 more)

### Community 2 - "City"
Cohesion: 0.11
Nodes (21): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any…, Resolve the enclosing Province for an admin unit at any level. Needed for…, City, District (+13 more)

### Community 3 - "watersupply/calculations.py"
Cohesion: 0.08
Nodes (41): cities_within(), Look up a Province/City/District/Neighborhood instance by level + name., City queryset covering the given administrative unit, at any level., resolve_admin_unit(), calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage() (+33 more)

### Community 4 - "Layers.js"
Cohesion: 0.08
Nodes (46): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+38 more)

### Community 5 - "test_water_chain.py"
Cohesion: 0.11
Nodes (16): ElectricityCost, EnvironmentalCosts, WMSLayerAdmin, AreaAffectedDrought, AvailableFreshWater, ConsumptionCapita, CoverageWaterSupply, ExtractionWater (+8 more)

### Community 6 - "importer/views.py"
Cohesion: 0.05
Nodes (40): atomic, CBSImporter, Import handler for CBS StatLine OData datasets., Fetch column definitions and units for a CBS table. Useful for building field…, GeoUploadForm, get_target_model_choices(), MappingForm, Get choices for target model field. (+32 more)

### Community 7 - "physicalEnv/models.py"
Cohesion: 0.10
Nodes (12): LandCoverClassesAdmin, SurfaceMaterialPropertiesAdmin, DigitalElevationModel, DigitalElevationModelWMS, DigitalSurfaceModelWMS, LandCoverClasses, LandCoverRaster, LandCoverWMS (+4 more)

### Community 8 - "rasterOperations.py"
Cohesion: 0.14
Nodes (16): BaseCommand, Command, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), get_raster_field_name(), Build a COG filename from whatever satellite/process metadata the raster model… (+8 more)

### Community 9 - "make_city"
Cohesion: 0.06
Nodes (23): get_population(), Projected population of `unit` in `year` (its current population if `year` is…, CityPopulationTests, CitySaveKeepsImportedPopulationTests, LowerLevelTests, PopulationTestBase, project(), ProvinceTests (+15 more)

### Community 10 - "weather/views.py"
Cohesion: 0.16
Nodes (16): WMSLayer, _fetch_with_retry(), _find_dimension_values(), _last_n_time_steps(), _local_tag(), _parse_iso8601(), _parse_iso8601_duration(), Resolve the most recent time steps for an animated WMS layer. Fetches and… (+8 more)

### Community 11 - "Model Registry System (MODEL/VECTOR/RASTER/WMS_REGISTRY)"
Cohesion: 0.12
Nodes (18): Importer System (file upload + external data), Map Frontend (mainMap, Mapbox GL JS), Model Registry System (MODEL/VECTOR/RASTER/WMS_REGISTRY), Application Layer (Django REST Parsers/Validation), Data Layer (PostgreSQL/PostGIS/GeoDjango ORM), Import Layer (File Upload UI), Visualization Layer (TiTiler/Mapbox GL), Right actions panel (Upload Data, Retrieve Data from APIs) (+10 more)

### Community 12 - "external_data.py"
Cohesion: 0.17
Nodes (11): get_catalog_grouped(), Return the catalog grouped by category. Structure: { category: [datasets] }…, External Data Catalog & Import Logic =====================================…, get_external_data(), get_neighborhoods_geojson(), views_external.py ================= View for the External Data Import page.…, Receives selected dataset keys via POST JSON, fetches data, imports it.…, Render the External Data catalog page. Users tick datasets they want, then POST… (+3 more)

### Community 13 - "urban_heat/views.py"
Cohesion: 0.17
Nodes (14): classify_pet(), classify_utci(), get_latest_meteorology(), Classify PET value into thermal stress category., Classify UTCI value into thermal stress category., Latest meteorological measurements within the administrative unit. DAG edges:…, _build_indicators(), _get_adminUnit_data() (+6 more)

### Community 14 - "Indicator Pattern (calculations / views / HTMX templates)"
Cohesion: 0.13
Nodes (16): CrossTwin Digital Twin Platform, core/DAG.dot causal network, Domain Apps (administrative, physicalEnv, watersupply, urban_heat, housing, builtup, ...), DPSIR Framework (Driver-Pressure-State-Impact-Response), Indicator Pattern (calculations / views / HTMX templates), MOCK_DATA fallback dicts, PostGISTestRunner, Raster Pipeline (PostGIS raster to COG to TiTiler) (+8 more)

### Community 15 - "import_dataset"
Cohesion: 0.18
Nodes (8): GEEAuthManager, GEEImporter, import_dataset(), Import handler for Google Earth Engine datasets., Export raster from GEE to local GeoTIFF., Main dispatcher for importing a dataset. Args: dataset_key: Key from…, Manages Google Earth Engine authentication., Initialize GEE with service account credentials.

### Community 16 - "watersupply indicators_grid.html (HTMX swap partial)"
Cohesion: 0.24
Nodes (15): DAG Edge Coverage Gaps (28 of 102 edges implemented), Nature-Based Solutions (NBS) indicator, Vegetation Coverage indicator, watersupply indicators_grid.html (HTMX swap partial), Non-Revenue Water (NRW / ILI) indicator, OPEX indicator, Service Time indicator, Supply Security indicator (+7 more)

### Community 17 - "housing indicators_grid.html (HTMX swap partial)"
Cohesion: 0.19
Nodes (15): housing indicators_grid.html (HTMX swap partial), Affordability (Price-to-Income) indicator, Affordability Stress distribution indicator, House Price Index indicator, Average Fixed Mortgage Rate indicator, New Housing Units / Supply Deficit indicator, Property Market indicator, Rental Market indicator (+7 more)

### Community 18 - "urban heat indicators_grid.html (HTMX swap partial)"
Cohesion: 0.21
Nodes (15): initGauges (housing gauges + mortgage bar), heat_indicators.html (standalone urban heat page), initGauges (urban heat standalone), urban heat indicators_grid.html (HTMX swap partial), Land Surface Temperature (LST) gauge, Current Meteorology indicator, PET gauge (Physiological Equivalent Temperature), Surface Urban Heat Island Intensity (SUHII) indicator (+7 more)

### Community 19 - "Meta"
Cohesion: 0.14
Nodes (8): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, WaterBodies, WaterWaysLN, WaterWaysPG

### Community 20 - "Meta"
Cohesion: 0.13
Nodes (10): MeanRadiantTemperature, Meta, PET, Physiological Equivalent Temperature (PET) measurements, Surface Urban Heat Island Intensity (SUHII)) measurements, Mean Radiant Temperature (MRT) measurements, Sky View Factor (SVF) measurements, SkyViewFactor (+2 more)

### Community 21 - "test_charts.py"
Cohesion: 0.07
Nodes (27): band_d(), build_population_chart(), pts(), x_of(), y_of(), build_population_stats(), _fmt(), monotone_segments() (+19 more)

### Community 22 - "Map_init.js"
Cohesion: 0.24
Nodes (11): updateCityName(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, changeBasemap(), getSavedCameraState(), initializeUrbanTwinMap(), onAdminLayerLoaded() (+3 more)

### Community 23 - "get_model_class"
Cohesion: 0.22
Nodes (9): Exception, get_model_class(), _import_geojson_features(), _ImportBlocked, Raised by _import_geojson_features when the whole import can't proceed at all…, Shared per-feature import engine for any source that hands back GeoJSON Feature…, Fetch vector data from PDOK WFS service and import directly to Django model.…, Get Django model class from 'app_label.ModelName' string. (+1 more)

### Community 24 - "urban_heat/calculations.py"
Cohesion: 0.20
Nodes (7): Street, DigitalSurfaceModel, calculate_urban_morphology(), # NOTE: percentage is stored relative to the *Province* total area, Building and street statistics relevant to canyon geometry. DAG edges:…, LandSurfaceTemperature, Land Surface Temperature (LST) measurements

### Community 25 - "ImportResult"
Cohesion: 0.14
Nodes (9): default_wms_legend_url(), ImportResult, _legend_url_from_capabilities(), Register a WMS layer by creating/updating its row in the target WMS model. This…, Fetch tabular data from CBS OData API and import to Django model. Args:…, Register a Sentinel-2 WMS layer by creating/updating its row in the target WMS…, Look up a layer's <LegendURL><OnlineResource xlink:href="..."/> from the WMS…, Resolve a legend image URL for a WMS layer, used as a fallback when a catalog… (+1 more)

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

### Community 32 - "weather/models.py"
Cohesion: 0.12
Nodes (10): interpolate_raster(), Interpolates raster data using Radial Basis Function (RBF) interpolation.…, Meta, Meteorology, PrecipitationRaster, Interpolated precipitation raster layer, Interpolated wind speed raster layer, Time-series weather measurements from stations (+2 more)

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

### Community 37 - "rasterStyles.py"
Cohesion: 0.27
Nodes (9): _cog_statistics(), _lookup_style(), raster_display_name(), Colormap + value-range resolution for raster tile rendering. Previously every…, Fetch band-1 min/max from TiTiler for products with no fixed range., Returns {colormap, rescale: (min, max) | None, label, unit, categorical} for a…, Shared index/model lookup used by both the tile colormap and the display name,…, Build a display name matching the legend label plus the acquisition date as MM-… (+1 more)

### Community 38 - "PopulationDockTests"
Cohesion: 0.13
Nodes (6): DashboardSummaryTests, _lonlat_of_rd(), PopulationDockTests, TestCase, WGS84 (lng, lat) of an EPSG:28992 point, as the map center is reported., The bottom dock: values, Curves-style graph with the 67% interval, what-if…

### Community 39 - "core/views.py"
Cohesion: 0.25
Nodes (6): colormap_legend_stops(), Sample `steps` evenly spaced (value, '#rrggbb') stops directly from the rio-…, get_raster_info(), get_raster_tiles(), Return raster metadata including bounds., Return TiTiler tile URL for a given raster layer.

### Community 40 - "mainMap/urls.py"
Cohesion: 0.22
Nodes (8): _display_field(), layer_bounds(), map_view(), model_geojson(), Generic GeoJSON endpoint for any registered model. URL:…, Returns the bounding box extent of a layer. URL:…, Pick the field on a related model that best represents it in a popup: the first…, Display the map page.

### Community 41 - "watersupply/signals.py"
Cohesion: 0.05
Nodes (42): The most recent cost record (the model has no province/year), or None., AppConfig, WatersupplyConfig, LossesChoices, LossesTypes, MeteredResidential, NonRevenueWater, OPEX (+34 more)

### Community 42 - "Digital twin concept: real city (left) mirrored by wireframe model (right)"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 43 - "ExtractionAndProductionTests"
Cohesion: 0.19
Nodes (4): ExtractionAndProductionTests, make_source(), make_well(), OpexTests

### Community 44 - "external_data.html Template"
Cohesion: 0.40
Nodes (5): Bbox Area-of-Interest Map Selector UI, importer:neighborhoods_geojson endpoint, importer:start_external_import endpoint, external_data.html Template, external_data.py fetch_openeo

### Community 45 - "importer:upload_geodata view"
Cohesion: 0.50
Nodes (5): FieldMapping.html Template, RasterMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 46 - "factories.py"
Cohesion: 0.11
Nodes (26): city_of(), The City an administrative unit belongs to (itself for a City), or None for a…, PopulationProjection, Projected total population of a City for one year and forecast variant. Loaded…, Scenario, _adjust(), _city_value(), normalize_scenario() (+18 more)

### Community 50 - "CrossTwin App Icon (192x192)"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 53 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 54 - "InterpolatedRasterBase"
Cohesion: 0.10
Nodes (13): HumidityRaster, InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:…, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child… (+5 more)

### Community 55 - "to_storage_srid"
Cohesion: 0.16
Nodes (11): GEOSGeometry, ensure_multipolygon(), _import_atom_gml_features(), Stream a plu:SpatialPlan GML file (INSPIRE Planned Land Use) over HTTP and…, Convert Polygon to MultiPolygon if needed., SimpleTestCase, ToStorageSridTests, Return `geom` expressed in settings.COORDINATE_SYSTEM, the only CRS geometries… (+3 more)

### Community 60 - "CrossTwin App Icon (apple-touch-icon)"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 61 - "CrossTwin favicon 16x16"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 62 - "CrossTwin favicon (32x32)"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

### Community 72 - "calculate_nbs_coverage"
Cohesion: 0.25
Nodes (6): calculate_nbs_coverage(), NBS coverage area and count. DAG edges: UTCI → NBS PET → NBS, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, Nature-Based Solutions (NBS) for urban heat mitigation, Nature-Based Solutions (NBS) for urban heat mitigation

### Community 102 - "PopulationDrivesTheIndicatorsTests"
Cohesion: 0.26
Nodes (3): PopulationDrivesTheIndicatorsTests, TestCase, Projected population (year, CBS variant, extra growth) reaches the dashboards.

### Community 115 - "population_panel"
Cohesion: 0.33
Nodes (7): dashboard_summary(), population_panel(), The administrative unit the population views talk about, as (level, unit,…, HTMX partial for the Dashboard panel: total population of the selected…, HTML for the bottom dock opened from the Population pill: today's population,…, _resolve_summary_unit(), _unit_context()

### Community 120 - "PDOKImporter"
Cohesion: 0.40
Nodes (4): PDOKImporter, Fetch raster data from PDOK WCS service, tiling the request when the area would…, Import handler for PDOK datasets - imports directly to Django models., Split [min_v, max_v] into evenly-sized segments, each no larger than…

### Community 137 - "core/utils.py"
Cohesion: 0.22
Nodes (5): ModelRegistryTests, SimpleTestCase, A typo in allowed_apps is swallowed silently (LookupError), dropping the whole…, build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps.

### Community 138 - "resolve_admin_unit_at_point"
Cohesion: 0.50
Nodes (4): Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), admin_unit_at_point(), Point-in-polygon lookup for the map center: resolve the smallest administrative…

### Community 140 - "calculate_green_area"
Cohesion: 0.50
Nodes (4): calculate_green_area(), calculate_vegetation_coverage(), Total green area (parks + green land cover) in km². DAG edges: LandCover →…, Vegetation coverage as percentage of the administrative unit's area. DAG edges:…

### Community 141 - "get_thermal_indices"
Cohesion: 0.50
Nodes (4): get_thermal_indices(), _raster_stats_sql(), Get min/max/mean/stddev from a raster clipped to a geometry., Aggregate raster statistics for all thermal indices. DAG edges: Meteorology →…

## Ambiguous Edges - Review These
- `Domain Apps (administrative, physicalEnv, watersupply, urban_heat, housing, builtup, ...)` → `Dynamic Layer Categories (Heat, Green, Water, Groundwater)`  [AMBIGUOUS]
  README.md · relation: conceptually_related_to

## Knowledge Gaps
- **103 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `Scenario` (+98 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 539 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **40 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Domain Apps (administrative, physicalEnv, watersupply, urban_heat, housing, builtup, ...)` and `Dynamic Layer Categories (Heat, Green, Water, Groundwater)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `City` connect `City` to `housing/calculations.py`, `weather/models.py`, `watersupply/calculations.py`, `test_water_chain.py`, `importer/views.py`, `.save`, `watersupply/signals.py`, `make_city`, `external_data.py`, `factories.py`, `Meta`, `load_raster_into_target_model`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `Neighborhood` connect `City` to `housing/calculations.py`, `weather/models.py`, `watersupply/calculations.py`, `test_water_chain.py`, `.save`, `external_data.py`, `factories.py`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `Province` connect `City` to `housing/calculations.py`, `weather/models.py`, `watersupply/calculations.py`, `test_water_chain.py`, `importer/views.py`, `.save`, `watersupply/signals.py`, `factories.py`, `InterpolatedRasterBase`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Province` (e.g. with `ProvinceAdmin` and `cities_within()`) actually correct?**
  _`Province` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 15 INFERRED edges - model-reasoned connections that need verification._