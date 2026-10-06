# Graph Report - CrossTwin  (2026-10-06)

## Corpus Check
- 2 files · ~106,999 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1475 nodes · 2648 edges · 119 communities (71 shown, 33 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 249 edges (avg confidence: 0.92)
- Token cost: 69,897 input · 0 output

## Community Hubs (Navigation)
- Map View Tests
- Built-up & Property Models
- Import Storage CRS Tests
- Thermal Comfort Rasters
- External Import Tests
- Chart Geometry Helpers
- Water Signal Cascade
- Water Supply Indicators
- WMS Tile Proxy
- Spatial Parent Index
- File Upload Importer
- Water Model Chain
- COG Raster Export
- Spatial Parent Tests
- Interpolated Weather Rasters
- Bulk Writer
- Nature Layers
- Storage SRID Conversion
- Administrative Hierarchy
- Urban Area Signal Tests
- Water Extraction & Production
- Water Derived Saves
- Housing Calculations
- KNMI Importer
- KNMI GeoTIFF Tests
- Weather Models
- WMS Proxy Tests
- PDOK Importer
- Non-Revenue Water
- Building Derived Field Tests
- Bbox Rounding
- Bulk Land Cover Import
- WBGT Heat Classification
- WMS Fetch Retry
- db_stats Command
- Query Stats Middleware
- Google Earth Engine Import
- Water OPEX
- Humidity Raster
- Deferred Cascade Batching
- Precipitation Raster
- Temperature Raster
- Administrative App Config
- Core App Config
- Signed Int URL Converter
- Map Editing Backend
- PhysicalEnv App Config
- Watersupply App Config
- Total Water Demand
- Weather App Config
- BuiltupConfig
- EnergyConfig
- HousingConfig
- ImporterConfig
- MainmapConfig
- NatureConfig
- UrbanheatConfig
- Map Layer Management
- Province Raster Generation
- Project Architecture Docs
- Population Chart Geometry
- GeoJSON Layer API
- Housing Views
- Map Editing Frontend
- Map Page Wiring & Tour
- Map Initialization
- Layer Cache Versioning
- Indicator Dashboard Templates
- Standalone Dashboard Pages
- Weather Raster Views
- Frontend Config
- Water Dashboard Views
- Version Info
- Water Panel & Slider JS
- Land Cover Styles
- WMS Legend Lookup
- Map UI Layer List
- Django Settings
- Django manage.py
- get_area
- Map URL Routes & Panels
- profile_requests.py
- External Data Import Page
- Map Page Layout
- require_POST
- asgi.py
- wsgi.py
- StyleSuggestion.md (design system sugges
- Shared Info Popover & Base
- Python Dependencies
- Housing Indicator Cards
- System Architecture Layers
- Water Indicator Cards
- App Icon Large
- App Icon Small
- Upload Templates
- CrossTwin App Icon (apple-touch-icon
- CrossTwin favicon 16x16
- CrossTwin favicon (32x32
- AppConfig
- File Upload Import
- TODO.md DAG gap analysis
- External Catalog Import
- Three-Layer Indicator Dashboard Pattern

## God Nodes (most connected - your core abstractions)
1. `City` - 50 edges
2. `Neighborhood` - 39 edges
3. `Province` - 38 edges
4. `District` - 25 edges
5. `Building` - 20 edges
6. `import_dataset()` - 20 edges
7. `ImportResult` - 19 edges
8. `PopulationDockTests` - 17 edges
9. `Meta` - 17 edges
10. `InterpolatedRasterBase` - 17 edges

## Surprising Connections (you probably didn't know these)
- `deferred_cascades()` --references--> `Deferred Cascades (bulk import batching)`  [EXTRACTED]
  importer/batching.py → README.md
- `model_geojson()` --references--> `model_geojson single-SQL GeoJSON endpoint`  [EXTRACTED]
  mainMap/views.py → README.md
- `Import Layer (File Upload UI)` --semantically_similar_to--> `Data Import Zone (GeoTIFF/Vector/API/Tabular Sources)`  [INFERRED] [semantically similar]
  ImporterArchitecture.html → SystemArchitecuture.html
- `PopulationDockTests` --uses--> `PopulationProjection`  [INFERRED]
  mainMap/tests.py → administrative/models.py
- `Building` --uses--> `Neighborhood`  [INFERRED]
  builtup/models.py → administrative/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **External import area-of-interest picker flow** — importer_templates_importer_external_data_updateui, importer_templates_importer_external_data_pickerlevelfor, importer_templates_importer_external_data_setpickerlevel, importer_templates_importer_external_data_loadpickerlevel, importer_templates_importer_external_data_togglearea, importer_templates_importer_external_data_unionbbox [EXTRACTED 1.00]
- **Domain what-if sliders driving HTMX #indicators-grid swap** — housing_templates_housing_partials_indicators_panel_mortgage_rate_slider, urban_heat_vegetation_slider, watersupply_consumption_slider, htmx_slider_recalculate_pattern [EXTRACTED 1.00]
- **Shared ? info button and popover help system** — templates_partials__info_btn, templates_partials__info_popover, watersupply_templates_watersupply_partials_indicators_grid, housing_templates_housing_partials_indicators_grid, urban_heat_templates_urban_heat_partials_indicators_grid [EXTRACTED 1.00]
- **External catalog data sources** — readme_pdok, readme_rivm, readme_cbs, readme_sentinel_2, readme_knmi_data_platform, readme_google_earth_engine [EXTRACTED 1.00]
- **Four model registries built by build_model_registry** — readme_model_registry_dict, readme_vector_registry, readme_raster_registry, readme_wms_registry [EXTRACTED 1.00]
- **Raster save to COG to TiTiler tile flow** — readme_raster_registry, readme_raster_pipeline, readme_cog, readme_titiler [EXTRACTED 1.00]
- **Standalone dashboards extending indicators_base.html** — housing_templates_housing_housing_indicators, urban_heat_templates_urban_heat_heat_indicators, watersupply_templates_watersupply_water_indicators, templates_indicators_base [EXTRACTED 1.00]
- **CrossTwin icon composition: physical city, digital wireframe, orbit ring** — core_static_ico_android_chrome_512x512_isometric_city_block, core_static_ico_android_chrome_512x512_cyan_wireframe_grid, core_static_ico_android_chrome_512x512_orbit_ring [INFERRED 0.85]
- **DAG gap tracking across docs** — todo [INFERRED 0.85]
- **Water panel slider -> recalculate -> grid swap flow** — watersupply_templates_watersupply_partials_indicators_panel_consumption_slider, watersupply_views_recalculate_indicators, watersupply_templates_watersupply_partials_indicators_grid, core_static_js_indicators_water [INFERRED 0.85]

## Communities (119 total, 33 thin omitted)

### Community 1 - "Map View Tests"
Cohesion: 0.06
Nodes (18): CityOfTests, DashboardSummaryTests, LayerBoundsTests, LayerStyleTests, ModelGeoJsonTests, PopulationDockTests, QueryStatsMiddlewareTests, _bbox_around_rd() (+10 more)

### Community 10 - "Built-up & Property Models"
Cohesion: 0.09
Nodes (22): Building, BuildingEnergyLabel, Facility, Meta, Park, Property, Street, ZoningArea (+14 more)

### Community 11 - "Import Storage CRS Tests"
Cohesion: 0.10
Nodes (12): AdminAreasGeojsonTests, BulkUpsertImportTests, GenericImportStorageCrsTests, GeoJsonFeatureImportStorageCrsTests, KNMIWbgtCatalogTests, _rd_feature(), _wgs84_frame(), TestCase (+4 more)

### Community 12 - "Thermal Comfort Rasters"
Cohesion: 0.07
Nodes (20): LandSurfaceTemperature, MeanRadiantTemperature, Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, PET, SkyViewFactor, StressCategory (+12 more)

### Community 14 - "External Import Tests"
Cohesion: 0.09
Nodes (5): CBSPopulationForecastImportTests, _FakeResponse, KNMIWbgtImportTests, CBS 85173NED: region column RegioIndeling2021, x 1000 scale, forecast variants., Just enough of requests.Response for KNMIImporter.

### Community 15 - "Chart Geometry Helpers"
Cohesion: 0.10
Nodes (28): PopulationProjection, Scenario, city_of(), _adjust(), annual_growth_rate(), _city_growth_factor(), _city_value(), extrapolate() (+20 more)

### Community 16 - "Water Signal Cascade"
Cohesion: 0.16
Nodes (25): ConsumptionCapita, TotalWaterProduction, city_population_cascaded(), city_saved(), consumption_saved(), demand_saved(), extraction_changed(), imported_changed() (+17 more)

### Community 17 - "Water Supply Indicators"
Cohesion: 0.10
Nodes (22): AreaAffectedDrought, AvailableFreshWater, SensibilityChoices, WaterTreatment, cities_within(), calculate_available_freshwater(), calculate_coverage(), calculate_drought_area() (+14 more)

### Community 18 - "WMS Tile Proxy"
Cohesion: 0.13
Nodes (19): WMSLayer, _fetch_with_retry(), _find_dimension_values(), _last_n_time_steps(), _local_tag(), _parse_iso8601(), _parse_iso8601_duration(), _retry_delay() (+11 more)

### Community 19 - "Spatial Parent Index"
Cohesion: 0.12
Nodes (19): CBSImporter, GEEImporter, _ImportBlocked, get_raster_field_name(), deferred_cascades(), _import_feature_rows(), _import_geojson_features(), to_storage_srid() (+11 more)

### Community 2 - "File Upload Importer"
Cohesion: 0.06
Nodes (41): ModelRegistryTests, GeoUploadForm, MappingForm, get_catalog_grouped(), get_target_model_choices(), gpd_read_any(), _build_mapping_form(), _cast_value() (+33 more)

### Community 20 - "Water Model Chain"
Cohesion: 0.11
Nodes (12): ElectricityCost, Meta, WMSLayerAdmin, ImportedWater, Meta, MeteredResidential, PipeNetwork, UsersLocation (+4 more)

### Community 21 - "COG Raster Export"
Cohesion: 0.12
Nodes (17): Command, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), interpolate_raster(), _reproject_and_cog(), auto_export_cog() (+9 more)

### Community 22 - "Spatial Parent Tests"
Cohesion: 0.14
Nodes (8): SpatialParentIndex, DeferredCascadeImportTests, SpatialParentIndexTests, _rd_square(), GEOSGeometry, Point-in-polygon lookup against a fixed set of parent rows. Each parent's…, The parent containing `geom`'s representative point, or None., Neighborhoods saved inside deferred_cascades() cascade once per parent, at the…

### Community 24 - "Interpolated Weather Rasters"
Cohesion: 0.14
Nodes (10): InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:…, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child…, Override in child classes to specify which measurement field to use (+2 more)

### Community 26 - "Bulk Writer"
Cohesion: 0.14
Nodes (7): BulkWriter, AdminBboxSourceCatalogTests, BulkImportRegistryTests, SimpleTestCase, Collects rows and writes them `batch_size` at a time. With a unique field, rows…, A writer when `Model` can safely be bulk-written, otherwise None (use the row…, Write what is left, replay the skipped signals and invalidate the layer cache.

### Community 27 - "Nature Layers"
Cohesion: 0.15
Nodes (8): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, WaterBodies, WaterWaysLN, WaterWaysPG

### Community 29 - "Storage SRID Conversion"
Cohesion: 0.17
Nodes (10): ToStorageSridTests, _square(), ensure_multipolygon(), _import_atom_gml_features(), _to_multipolygon(), MultiPolygon, Polygon, Load only what the lookup needs: pk, geom and any attributes read off the… (+2 more)

### Community 3 - "Administrative Hierarchy"
Cohesion: 0.11
Nodes (24): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, City, District, Meta, Neighborhood, Province (+16 more)

### Community 30 - "Urban Area Signal Tests"
Cohesion: 0.20
Nodes (6): UrbanAreaSetBasedUpdateTests, UrbanAreaSourceComputationTests, _square(), TestCase, physicalEnv.signals.landcover_changed: Neighborhood.urban_area is derived from…, The single-statement recompute (docs/PERFORMANCE.md §2): clipping, cascade…

### Community 35 - "Water Extraction & Production"
Cohesion: 0.16
Nodes (10): EnvironmentalCosts, ExtractionWater, calculate_co2_emission(), calculate_total_extraction(), calculate_total_production_day(), The most recent cost record (the model has no province/year), or None., Total CO₂ emissions from extraction pumps in kg CO₂/day. DAG edge:…, Total active extraction in m³/day from wells within the adminBund. DAG edges:… (+2 more)

### Community 36 - "Water Derived Saves"
Cohesion: 0.14
Nodes (6): CoverageWaterSupply, SupplySecurity, DAG edges: Total_Water_Demand -> Supply_Security Total_Water_Prod ->…, DAG edges: Total_Population -> Total_Consumption ConsumptionCapita ->…, Derived from the geometry: affected area (km2) and, if not given, the Province., Set productionDay/YR (Mm3) and costDay/YR (EUR) from the active wells of the…

### Community 4 - "Housing Calculations"
Cohesion: 0.08
Nodes (29): CentralBankPolicy, CreditSupplyConditions, HousePriceIndex, HousingAffordability, HousingProject, HousingSupplyDemand, Meta, Mortgage (+21 more)

### Community 41 - "KNMI Importer"
Cohesion: 0.26
Nodes (5): KNMIImporter, KNMIFilenameTests, datetime, KNMI Data Platform (Open Data API v1). Flow: list the newest file of a dataset…, UTC datetime encoded in a KNMI file name, or None if it has none.

### Community 42 - "KNMI GeoTIFF Tests"
Cohesion: 0.27
Nodes (4): KNMIToGeotiffTests, _write_grid(), Convert a downloaded KNMI grid to a single-band float32 GeoTIFF in…, Small synthetic grid over the Netherlands standing in for a KNMI file.

### Community 46 - "Weather Models"
Cohesion: 0.18
Nodes (6): Meta, Meteorology, WeatherStation, WindSpeedRaster, Interpolated wind speed raster layer, Time-series weather measurements from stations

### Community 5 - "PDOK Importer"
Cohesion: 0.08
Nodes (24): ImportResult, PDOKImporter, Sentinel2Importer, get_model_class(), import_dataset(), load_raster_into_target_model(), Fetch raster data from PDOK WCS service, tiling the request when the area would…, Register a WMS layer by creating/updating its row in the target WMS model. This… (+16 more)

### Community 50 - "Non-Revenue Water"
Cohesion: 0.20
Nodes (6): LossesChoices, LossesTypes, NonRevenueWater, calculate_nrw(), Non-Revenue Water breakdown. DAG edges: Real_Losses → NRW, ILI Apparent_Losses…, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 52 - "Building Derived Field Tests"
Cohesion: 0.31
Nodes (5): BuildingDerivedFieldsTests, _square(), TestCase, Fields Building.save() derives must be stored on every save path., A square MultiPolygon in the storage CRS (metres).

### Community 54 - "Bbox Rounding"
Cohesion: 0.31
Nodes (4): RoundBboxTests, _round_bbox(), SimpleTestCase, Round the numbers of the `bbox=` parameter in a raw query string, leaving…

### Community 6 - "WBGT Heat Classification"
Cohesion: 0.08
Nodes (31): ClassifyWbgtTests, WbgtIndicatorTests, WbgtRasterStatsTests, calculate_nbs_coverage(), classify_pet(), classify_utci(), classify_wbgt(), get_latest_meteorology() (+23 more)

### Community 61 - "db_stats Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Show the most expensive SQL statements recorded by pg_stat_statements…

### Community 64 - "Google Earth Engine Import"
Cohesion: 0.33
Nodes (3): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE for the given Cloud project. `ee.Authenticate()` is a one-time-…

### Community 65 - "Water OPEX"
Cohesion: 0.33
Nodes (4): OPEX, calculate_opex_recovery(), OPEX recovery percentage. DAG edges: OPEX → OPEX_Recovery CollectionRatio →…, DAG edges: Total_Extraction/Total_Water_Prod -> OPEX Imported_Water -> OPEX,…

### Community 7 - "Deferred Cascade Batching"
Cohesion: 0.07
Nodes (27): LandCoverClassesAdmin, SurfaceMaterialPropertiesAdmin, DigitalElevationModel, DigitalElevationModelWMS, DigitalSurfaceModel, DigitalSurfaceModelWMS, LandCoverClasses, LandCoverRaster (+19 more)

### Community 8 - "Map Editing Backend"
Cohesion: 0.10
Nodes (36): EditBackup, EditBackupRow, Meta, active_backup(), backup(), _backup_bar(), backup_discard(), backup_restore() (+28 more)

### Community 0 - "Map Layer Management"
Cohesion: 0.06
Nodes (63): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+55 more)

### Community 13 - "Project Architecture Docs"
Cohesion: 0.07
Nodes (34): build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., External data sources (PDOK, RIVM, CBS, Sentinel-2, KNMI, GEE), Affordability stress chain gap (Rent/Mortgage/Water tariff -> Affordability_Stress), Product / feature backlog (alerts, narratives, new dashboards), Urban heat DSM->SVF->Tmrt/PET->UTCI chain (SOLWEIG, unimplemented), Watersupply DAG gaps (Network->Real_Losses, WT_Efficiency->WT_Cost, ...), CrossTwin README (+26 more)

### Community 23 - "Population Chart Geometry"
Cohesion: 0.16
Nodes (19): band_d(), build_population_chart(), pts(), x_of(), y_of(), _fmt(), monotone_segments(), nice_step() (+11 more)

### Community 25 - "GeoJSON Layer API"
Cohesion: 0.16
Nodes (15): _cog_statistics(), colormap_legend_stops(), _lookup_style(), raster_display_name(), resolve_raster_style(), get_raster_info(), get_raster_tiles(), Colormap + value-range resolution for raster tile rendering. Previously every… (+7 more)

### Community 28 - "Housing Views"
Cohesion: 0.21
Nodes (14): resolve_admin_unit(), get_population(), population_params(), _build_indicators(), _get_adminUnit_data(), housing_indicators(), housing_indicators_json(), recalculate_indicators() (+6 more)

### Community 31 - "Map Editing Frontend"
Cohesion: 0.28
Nodes (13): _attachEditor(), _bindDrawEvents(), _cancelEdit(), _drawModeFor(), _featureUrl(), _hideOriginal(), _openEditorPanel(), _removeDrawControl() (+5 more)

### Community 32 - "Map Page Wiring & Tour"
Cohesion: 0.18
Nodes (12): clearTourHighlight(), endTour(), findActiveAdminTool(), positionActionsMenu(), refreshActivePanel(), renderTourStep(), setActionsMenuOpen(), startTour() (+4 more)

### Community 34 - "Map Initialization"
Cohesion: 0.24
Nodes (11): updateCityName(), add3DBuildings(), addExternalLayers(), changeBasemap(), getSavedCameraState(), initializeUrbanTwinMap(), onAdminLayerLoaded(), saveCameraState() (+3 more)

### Community 38 - "Layer Cache Versioning"
Cohesion: 0.24
Nodes (9): bump_layer_version(), get_cache(), _label(), layer_version(), _version_key(), Versioned cache keys for data that only changes when rows are written. Every…, caches[alias], falling back to the default cache when the alias isn't…, Current cache version of a model's data. A missing version is seeded with the… (+1 more)

### Community 39 - "Indicator Dashboard Templates"
Cohesion: 0.23
Nodes (9): applyZone(), zoneStyle(), initGauges() (global), Vegetation Coverage what-if slider, Urban Morphology aspect ratio (H/W), partials/_info_btn.html, partials/_info_popover.html, heat_indicators.html (Urban Heat Dashboard) (+1 more)

### Community 40 - "Standalone Dashboard Pages"
Cohesion: 0.20
Nodes (10): applyZone(), zoneStyle(), Mortgage Interest Rate what-if slider, #indicators-grid HTMX swap target, Consumption per Capita what-if slider, pop_scenario / pop_growth population what-if params, housing_indicators.html (Province Housing Dashboard), indicators_base.html (standalone dashboard shell) (+2 more)

### Community 44 - "Weather Raster Views"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 48 - "Frontend Config"
Cohesion: 0.22
Nodes (9): roundBboxInUrl(), roundCoord(), availableLayers, BASEMAPS, CONFIG, layerVisibility, loadedLayers, TOOL_CATEGORIES (+1 more)

### Community 51 - "Water Dashboard Views"
Cohesion: 0.31
Nodes (8): _build_indicators(), _get_adminUnit_data(), _population_context(), recalculate_indicators(), water_indicators(), Pure function: takes DB data dict, returns indicators dict., Template context that lets the panel's own controls keep the population what-if., Fetch all fixed DB values for an administrative unit/year. Returns a dict.…

### Community 55 - "Version Info"
Cohesion: 0.32
Nodes (6): _derive_version(), _get_git_info(), version_context(), Derive a semver-ish label from the raw commit count. 0–99 → v0.1, 100–199 →…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…

### Community 56 - "Water Panel & Slider JS"
Cohesion: 0.38
Nodes (6): applyZone(), zoneStyle(), Water Supply Indicators Panel (partial), consumption-slider (Consumption per Capita what-if), Population scenario what-if (pop_scenario / pop_growth), HTMX indicator recalculation pattern

### Community 62 - "Land Cover Styles"
Cohesion: 0.40
Nodes (5): build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…

### Community 67 - "WMS Legend Lookup"
Cohesion: 0.40
Nodes (4): default_wms_legend_url(), _legend_url_from_capabilities(), Look up a layer's <LegendURL><OnlineResource xlink:href="..."/> from the WMS…, Resolve a legend image URL for a WMS layer, used as a fallback when a catalog…

### Community 79 - "Django manage.py"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 9 - "Map URL Routes & Panels"
Cohesion: 0.08
Nodes (36): resolve_admin_unit_at_point(), _wgs84_to_storage(), admin_unit_at_point(), available_layers(), dashboard_summary(), _display_field(), _extract_unit(), _field_label() (+28 more)

### Community 33 - "External Data Import Page"
Cohesion: 0.15
Nodes (12): clearBbox(), Import Selected click handler (POST start_external_import), initBboxMap(), loadPickerLevel(), pickerLevelFor(), setPickerLevel(), toggleArea(), updateUI() (+4 more)

### Community 37 - "Map Page Layout"
Cohesion: 0.19
Nodes (13): #actions-menu (upload, API retrieve, year selector), #btn-dashboard, #legend-stack, #population-panel dock container, #side-panel / #panel-body, Left toolbar (topic tool buttons with hx-get indicator panels), applyPopulationControls() (window.POP_SCENARIO / POP_GROWTH), mainMap.html (map page) (+5 more)

### Community 43 - "Shared Info Popover & Base"
Cohesion: 0.18
Nodes (12): base.html (site shell template), LoadingManager (fetch/XHR overlay interceptor), _info_btn.html (reusable ? helper button), _info_popover.html (shared popover + delegated script), Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono) (+4 more)

### Community 45 - "Python Dependencies"
Cohesion: 0.18
Nodes (10): django-crispy-forms + crispy-tailwind, Django 5.2.12, earthengine-api 1.7.18, GDAL 3.11.4 (Windows wheel), geopandas 1.1.2, openeo 0.51.0, owslib 0.35.0, rasterio 1.4.4 (+2 more)

### Community 49 - "Housing Indicator Cards"
Cohesion: 0.29
Nodes (10): housing indicators_grid.html (HTMX swap partial), Affordability (Price-to-Income) indicator, Affordability Stress distribution indicator, House Price Index indicator, Average Fixed Mortgage Rate indicator, New Housing Units / Supply Deficit indicator, Property Market indicator, Rental Market indicator (+2 more)

### Community 53 - "System Architecture Layers"
Cohesion: 0.25
Nodes (9): Application Layer (Django REST Parsers/Validation), Data Layer (PostgreSQL/PostGIS/GeoDjango ORM), Import Layer (File Upload UI), Visualization Layer (TiTiler/Mapbox GL), Data Import Zone (GeoTIFF/Vector/API/Tabular Sources), Database Zone (Django Models/PostGIS), Processing & Export Zone (COG Conversion), Tile Serving & Frontend Zone (TiTiler/Mapbox/React) (+1 more)

### Community 59 - "Water Indicator Cards"
Cohesion: 0.52
Nodes (7): watersupply indicators_grid.html (HTMX swap partial), Non-Revenue Water (NRW / ILI) indicator, OPEX indicator, Service Time indicator, Supply Security indicator, Total Demand indicator, Total Supply indicator

### Community 66 - "App Icon Large"
Cohesion: 0.50
Nodes (5): Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves, CrossTwin App Icon (android-chrome-512x512)

### Community 74 - "App Icon Small"
Cohesion: 0.67
Nodes (4): Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background, CrossTwin App Icon (192x192)

### Community 77 - "Upload Templates"
Cohesion: 0.67
Nodes (4): FieldMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 86 - "CrossTwin App Icon (apple-touch-icon"
Cohesion: 1.00
Nodes (3): Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings, CrossTwin App Icon (apple-touch-icon)

### Community 87 - "CrossTwin favicon 16x16"
Cohesion: 0.67
Nodes (3): Browser tab icon (branding), CrossTwin favicon 16x16, Teal/blue cube-like glyph on light background

### Community 88 - "CrossTwin favicon (32x32"
Cohesion: 0.67
Nodes (3): Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform), CrossTwin favicon (32x32)

### Community 58 - "External Catalog Import"
Cohesion: 0.33
Nodes (7): CBS OData statistics, External Catalog Import, Google Earth Engine, KNMI Data Platform, PDOK, RIVM energy labels, Sentinel-2 via openEO (Copernicus Data Space)

### Community 68 - "Three-Layer Indicator Dashboard Pattern"
Cohesion: 0.40
Nodes (5): Draggable Translucent Map Overlays, Three-Layer Indicator Dashboard Pattern, MOCK_DATA fallback, What-if Overrides (consumption_override, interest_rate_override), No Inline Script Blocks Convention

## Knowledge Gaps
- **90 isolated node(s):** `Scenario`, `SensibilityChoices`, `WMSLayerAdmin`, `ProtectionType`, `LossesChoices` (+85 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 596 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **33 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `City` connect `Administrative Hierarchy` to `File Upload Importer`, `Housing Calculations`, `PDOK Importer`, `Water Derived Saves`, `Deferred Cascade Batching`, `Built-up & Property Models`, `Thermal Comfort Rasters`, `Chart Geometry Helpers`, `Water Signal Cascade`, `Water Supply Indicators`, `WMS Tile Proxy`, `Spatial Parent Index`, `Water Model Chain`, `Total Water Demand`, `Spatial Parent Tests`, `Bulk Land Cover Import`, `Nature Layers`, `Urban Area Signal Tests`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `Province` connect `Administrative Hierarchy` to `Housing Calculations`, `Deferred Cascade Batching`, `Import Storage CRS Tests`, `Chart Geometry Helpers`, `Water Signal Cascade`, `Water Supply Indicators`, `WMS Tile Proxy`, `Spatial Parent Index`, `Water Model Chain`, `Spatial Parent Tests`, `Interpolated Weather Rasters`, `Bulk Land Cover Import`, `Urban Area Signal Tests`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `recalculate_indicators()` connect `Water Dashboard Views` to `Water Panel & Slider JS`, `Water Indicator Cards`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 28 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `Province` (e.g. with `ProvinceAdmin` and `cities_within()`) actually correct?**
  _`Province` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `District` (e.g. with `cities_within()` and `city_of()`) actually correct?**
  _`District` has 14 INFERRED edges - model-reasoned connections that need verification._