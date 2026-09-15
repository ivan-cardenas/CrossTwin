# Graph Report - CrossTwin  (2026-09-15)

## Corpus Check
- 9 files · ~105,849 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1101 nodes · 1678 edges · 164 communities (43 shown, 75 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 161 edges (avg confidence: 0.91)
- Token cost: 117,083 input · 0 output

## Community Hubs (Navigation)
- Housing & Zoning Domain
- Housing/Builtup Discussion Gaps
- Water Supply Calculations & Views
- Map Layer Styling & Metadata
- Map Layers Frontend (JS)
- Geodata Upload Forms & Views
- Architecture Diagrams Overview
- Urban Heat Calculations & Views
- Indicator Dashboard Cards
- Admin Hierarchy & App Registration
- Map Init & Import Templates
- Water Supply Infrastructure Models
- Urban Heat Raster Models
- Raster Export & COG Pipeline
- Metered Residential Water Tests
- Weather Interpolated Raster Base
- PDOK Geometry Import (Atom/WFS)
- Nature Domain Models
- Raster CRS & Reflection Rationale
- External Data Catalog & Views
- Graphify Skill Reference Docs
- Admin Hierarchy & Citations
- WMS Legend & Import Result
- Water Supply Infrastructure Models
- Weather Raster Signals
- Sentinel-2 Importer
- PostGIS Test Runner
- Paper Overview & References
- Google Earth Engine Auth & Import
- External Import Pipeline & Requirements
- Platform Stack & Data Sources
- Weather Precipitation & Station Models
- External Data Exceptions & GEE Importer
- Map Config JS
- Version & Git Info Utility
- External Import Discussion & Overrides
- Non-Revenue Water Losses Model
- Common Admin Registrations
- Nature Domain Paper Coverage
- CBS Importer
- PDOK WCS Importer
- Water Supply Infrastructure Models
- Weather Humidity Raster
- Weather Temperature Raster
- Weather Windspeed Raster
- Common App Config
- Common Models Digitalelevationmodel
- Map UI Legend Rendering
- Core App Config
- Energy Migration: Populate Labels
- Manage.py Entrypoint
- Weather App Config
- Builtup App Config
- Builtup Migration: Building ID Resync
- Common Geo Area Function
- Django Settings
- Energy App Config
- Housing App Config
- Importer App Config
- MainMap App Config
- Nature App Config
- Urban Heat App Config
- Watersupply App Config
- Consumption Per Capita & Signals
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Builtup Migration
- Common Migration
- Common Migration
- Common Migration
- Common Migration
- Common Migration
- Common Migration
- Common Migration
- Common Migration
- Common Migration
- Common Migration
- Common Models Landcoverclasses
- Admin Hierarchy & App Registration
- Digitaltwin Asgi
- Digitaltwin Wsgi
- Weather Domain Paper Coverage
- Energy Migration
- Energy Migration
- Housing Migration
- Housing Migration
- Nature Migration
- Nature Migration
- Nature Migration
- Nature Migration
- Nature Migration
- Urban Migration
- Urban Migration
- Urban Migration
- Watersupply Migration
- Watersupply Migration
- Watersupply Migration
- Watersupply Migration
- Watersupply Migration
- Weather Migration
- Weather Models Interpolatedrasterbase Get Field Name
- Appconfig
- Readme Base Spatial Model
- Todo Md

## God Nodes (most connected - your core abstractions)
1. `City` - 40 edges
2. `Neighborhood` - 33 edges
3. `Province` - 26 edges
4. `CrossTwin Platform` - 19 edges
5. `_get_province_data()` - 18 edges
6. `InterpolatedRasterBase` - 17 edges
7. `Meta` - 17 edges
8. `import_dataset()` - 17 edges
9. `Raster Pipeline` - 16 edges
10. `Building` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Visualization Layer (TiTiler/Mapbox GL)` --semantically_similar_to--> `Raster Pipeline`  [INFERRED] [semantically similar]
  ImporterArchitecture.html → CLAUDE.md
- `Processing & Export Zone (COG Conversion)` --semantically_similar_to--> `Raster Pipeline`  [INFERRED] [semantically similar]
  SystemArchitecuture.html → CLAUDE.md
- `Full Mapbox Style Per Layer` --shares_data_with--> `available_layers()`  [EXTRACTED]
  docs/map-layer-system.md → mainMap/views.py
- `Popup Formatting with Field Metadata` --implements--> `available_layers()`  [EXTRACTED]
  docs/map-layer-system.md → mainMap/views.py
- `calculate_green_area()` --rationale_for--> `LandCoverVector.percentage Province-Relative Limitation`  [EXTRACTED]
  urban_heat/calculations.py → docs/plan_HTMX_ADMIN.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **External Import Credentials + BBox Selection Flow** — importer_templates_external_data_html, importer_bbox_area_selector_ui, importer_templates_importer_external_data_fetch_openeo, importer_start_external_import_endpoint, importer_neighborhoods_geojson_endpoint [EXTRACTED 1.00]
- **Layer Catalog Style and Metadata Flow** — mainmap_views_layer_styles, mainmap_views_available_layers, common_static_js_layers_addlayer, common_static_js_layers_createpopupcontent, docs_map_layer_system_extract_unit [EXTRACTED 1.00]
- **Admin-Unit Click-to-Panel HTMX Flow** — common_static_js_map_init_onadminlayerloaded, mainmap_templates_mainmap_admin_panel_tools_registry, mainmap_templates_mainmap_sync_panel_btns, watersupply_views_get_province_data, common_admin_units_resolve_admin_unit [INFERRED 0.85]
- **Three-Layer Indicator Dashboard Pattern** — claude_indicator_pattern, claude_dag_gaps_watersupply, claude_dag_gaps_builtup_housing, claude_tasks_watersupply_expansion, claude_tasks_urban_heat_buildout [INFERRED 0.85]
- **Raster-to-COG Tiling Pipeline Pattern** — claude_raster_pipeline, systemarchitecuture_processing_zone, systemarchitecuture_serving_zone, importerarchitecture_visualization_layer, readme_titiler [INFERRED 0.85]
- **Central Model-Registry-Driven Architecture** — claude_model_registry_system, readme_model_registry_pattern, claude_domain_apps, claude_signal_driven_computations [INFERRED 0.85]
- **Reflection-Based Extensibility Pattern** — docs_crosstwin_paper_draft_model_registry, claude_raster_pipeline, docs_crosstwin_paper_draft_external_data_import_pipeline, docs_crosstwin_paper_draft_map_frontend [EXTRACTED 1.00]
- **Three-Layer Indicator Dashboard Pattern** — docs_crosstwin_paper_draft_watersupply_app, docs_crosstwin_paper_draft_housing_app, docs_crosstwin_paper_draft_calculations_py, docs_crosstwin_paper_draft_views_py [EXTRACTED 1.00]
- **DPSIR Implementation Gap Evidence** — docs_crosstwin_paper_draft_dpsir_coverage_gaps, docs_crosstwin_paper_draft_accessibility_model_missing, docs_crosstwin_paper_draft_opex_extraction_volume_bug, docs_crosstwin_paper_draft_housingaffordability_thresholds_todo [INFERRED 0.85]

## Communities (164 total, 75 thin omitted)

### Community 0 - "Housing & Zoning Domain"
Cohesion: 0.05
Nodes (49): Building, BuildingEnergyLabel, Facility, Meta, Park, Property, Proxy onto Building, filed under the Energy app so the energy-label fields…, Street (+41 more)

### Community 1 - "Housing/Builtup Discussion Gaps"
Cohesion: 0.05
Nodes (54): Missing Accessibility Model, AreaAffectedDrought Model, Building.connectivity Field, builtup App, calculate_collection_ratio() Function, calculations.py Layer, ConsumptionCapita Model, CoverageWaterSupply Model (+46 more)

### Community 2 - "Water Supply Calculations & Views"
Cohesion: 0.09
Nodes (41): cities_within(), neighborhoods_within(), common/admin_units.py (planned), Look up a Province/City/District/Neighborhood instance by level + name., City queryset covering the given administrative unit, at any level., Neighborhood queryset covering the given administrative unit, at any level., resolve_admin_unit(), calculate_available_freshwater() (+33 more)

### Community 3 - "Map Layer Styling & Metadata"
Cohesion: 0.07
Nodes (34): LandCoverVector, build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type (common.LandCoverClasses).…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…, _cog_statistics(), colormap_legend_stops() (+26 more)

### Community 4 - "Map Layers Frontend (JS)"
Cohesion: 0.09
Nodes (35): initializeUI(), activateToolLayers(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig(), addRasterLegend() (+27 more)

### Community 5 - "Geodata Upload Forms & Views"
Cohesion: 0.09
Nodes (31): atomic, build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., GeoUploadForm, get_target_model_choices(), MappingForm, Get choices for target model field., Dynamic form for field mapping. Fields are added dynamically in the view based… (+23 more)

### Community 6 - "Architecture Diagrams Overview"
Cohesion: 0.07
Nodes (38): API Routes, DAG Edge Coverage Gaps, DAG Gaps: builtup/housing apps, DAG Gaps: common app, DAG Gaps: urban_heat app, DAG Gaps: watersupply app, Domain Apps, DPSIR Causal Network (+30 more)

### Community 7 - "Urban Heat Calculations & Views"
Cohesion: 0.08
Nodes (31): DigitalSurfaceModel, LandCoverVector.percentage Province-Relative Limitation, calculate_green_area(), calculate_urban_morphology(), calculate_vegetation_coverage(), classify_pet(), classify_utci(), get_latest_meteorology() (+23 more)

### Community 8 - "Indicator Dashboard Cards"
Cohesion: 0.06
Nodes (38): Known Issues Doc, GEE Authentication Failure (Service Usage API), Plan: Admin-Level Map Panel Selection, Mapbox Click Handler Bound to Wrong Layer ID (Province-fill), Questions and Bugs Doc, Should common become Administrative Boundaries, DEM/DSM COG vs Server-Side Raster SQL Trade-off, How to Populate Housing Supply/Demand (+30 more)

### Community 9 - "Admin Hierarchy & App Registration"
Cohesion: 0.11
Nodes (16): Shared helpers for resolving and aggregating by administrative unit. Lets any…, City, DigitalElevationModelWMS, DigitalSurfaceModelWMS, District, LandCoverWMS, Meta, Province (+8 more)

### Community 10 - "Map Init & Import Templates"
Cohesion: 0.08
Nodes (27): updateCityName(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, changeBasemap(), getSavedCameraState(), initializeUrbanTwinMap(), onAdminLayerLoaded() (+19 more)

### Community 11 - "Water Supply Infrastructure Models"
Cohesion: 0.08
Nodes (15): ElectricityCost, WMSLayerAdmin, AreaAffectedDrought, CoverageWaterSupply, ImportedWater, Meta, PipeNetwork, SensibilityChoices (+7 more)

### Community 12 - "Urban Heat Raster Models"
Cohesion: 0.09
Nodes (18): calculate_nbs_coverage(), NBS coverage area and count. DAG edges: UTCI → NBS PET → NBS, MeanRadiantTemperature, Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, PET, Physiological Equivalent Temperature (PET) measurements (+10 more)

### Community 13 - "Raster Export & COG Pipeline"
Cohesion: 0.13
Nodes (16): BaseCommand, Command, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), interpolate_raster(), Build a COG filename from whatever satellite/process metadata the raster model… (+8 more)

### Community 14 - "Metered Residential Water Tests"
Cohesion: 0.24
Nodes (12): TestCase, MeteredResidential, make_city(), make_consumption_capita(), make_metered_residential(), make_neighborhood(), make_polygon(), make_province() (+4 more)

### Community 15 - "Weather Interpolated Raster Base"
Cohesion: 0.14
Nodes (10): InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:…, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child…, Convenience method to generate raster for a Province Args: Province: Province… (+2 more)

### Community 16 - "PDOK Geometry Import (Atom/WFS)"
Cohesion: 0.16
Nodes (13): GEOSGeometry, ensure_multipolygon(), get_model_class(), _import_atom_gml_features(), _import_geojson_features(), Stream a plu:SpatialPlan GML file (INSPIRE Planned Land Use) over HTTP and…, Shared per-feature import engine for any source that hands back GeoJSON Feature…, Convert Polygon to MultiPolygon if needed. (+5 more)

### Community 17 - "Nature Domain Models"
Cohesion: 0.15
Nodes (8): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, WaterBodies, WaterWaysLN, WaterWaysPG

### Community 18 - "Raster CRS & Reflection Rationale"
Cohesion: 0.17
Nodes (16): Raster Pipeline, Cloud-Optimised GeoTIFF (COG), CRS Mismatch Import Complexity (28992 vs 4326), EPSG:28992 (Amersfoort / RD New), EPSG:3857 Reprojection Bug and Fix, EPSG:4326 (WGS84), Extensibility-through-Reflection Design Principle, importer/ App (+8 more)

### Community 19 - "External Data Catalog & Views"
Cohesion: 0.20
Nodes (10): get_catalog_grouped(), Return the catalog grouped by category. Structure: { category: [datasets] }…, get_external_data(), get_neighborhoods_geojson(), views_external.py ================= View for the External Data Import page.…, Receives selected dataset keys via POST JSON, fetches data, imports it.…, Render the External Data catalog page. Users tick datasets they want, then POST…, Return all neighborhoods from common.Neighborhood as a GeoJSON… (+2 more)

### Community 20 - "Graphify Skill Reference Docs"
Cohesion: 0.21
Nodes (13): graphify Project Rule, graphify Integration Section, /graphify add and --watch, Extra Exports and Benchmark, Confidence Score Rubric, Extraction Subagent Prompt Spec, GitHub Clone and Cross-Repo Merge, Commit Hook and CLAUDE.md Integration (+5 more)

### Community 21 - "Admin Hierarchy & Citations"
Cohesion: 0.26
Nodes (13): Administrative Hierarchy (Province>City>District>Neighbourhood), INSPIRE Directive 2007/2/EC, City Model, common App, DigitalElevationModel, District Model, DigitalSurfaceModel, External Data Import Coverage (+5 more)

### Community 22 - "WMS Legend & Import Result"
Cohesion: 0.17
Nodes (8): default_wms_legend_url(), ImportResult, _legend_url_from_capabilities(), Register a WMS layer by creating/updating its row in the target WMS model. This…, Register a Sentinel-2 WMS layer by creating/updating its row in the target WMS…, Look up a layer's <LegendURL><OnlineResource xlink:href="..."/> from the WMS…, Resolve a legend image URL for a WMS layer, used as a fallback when a catalog…, Result object for import operations.

### Community 23 - "Water Supply Infrastructure Models"
Cohesion: 0.17
Nodes (3): AvailableFreshWater, ConsumptionCapita, OPEX

### Community 24 - "Weather Raster Signals"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 25 - "Sentinel-2 Importer"
Cohesion: 0.24
Nodes (8): datetime, load_raster_into_target_model(), Import handler for Sentinel-2 datasets., Look up the real acquisition timestamp of the most recent Sentinel-2 L2A scene…, Fetch raster from Sentinel-2 WCS (e.g., WorldCover)., Fetch processed Sentinel-2 imagery via the Copernicus Data Space Ecosystem's…, Load a downloaded raster file into its catalog entry's target_model. The…, Sentinel2Importer

### Community 26 - "PostGIS Test Runner"
Cohesion: 0.27
Nodes (5): _patched_prepare_database(), PostGISTestRunner, Replace the PostGIS backend's prepare_database so it does NOT try to CREATE…, Return the exact test DB name — respecting explicit TEST.NAME. Do NOT add…, DiscoverRunner

### Community 27 - "Paper Overview & References"
Cohesion: 0.22
Nodes (11): CrossTwin Paper Draft, Building Model, Bauer et al. 2021 - Digital Revolution of Earth-system Science, Dembski et al. 2020 - Urban Digital Twins for Smart Cities, EEA 1999 - Environmental Indicators Typology and Overview, Ledoux & Meijers 2011 - Topologically Consistent 3D City Models, van der Hoeven & van den Brink 2020 - Towards an Urban Digital Twin, common/DAG.dot Causal Graph (+3 more)

### Community 28 - "Google Earth Engine Auth & Import"
Cohesion: 0.22
Nodes (6): GEEAuthManager, import_dataset(), Export raster from GEE to local GeoTIFF., Main dispatcher for importing a dataset. Args: dataset_key: Key from…, Manages Google Earth Engine authentication., Initialize GEE with service account credentials.

### Community 29 - "External Import Pipeline & Requirements"
Cohesion: 0.18
Nodes (10): django-crispy-forms + crispy-tailwind, Django 5.2.12, earthengine-api 1.7.18, GDAL 3.11.4 (Windows wheel), geopandas 1.1.2, openeo 0.51.0, owslib 0.35.0, rasterio 1.4.4 (+2 more)

### Community 30 - "Platform Stack & Data Sources"
Cohesion: 0.22
Nodes (10): CrossTwin Platform, Django, Energy App, EnergyEfficiencyLabels Model, Google Earth Engine, HTMX, PostGIS, PostgreSQL (+2 more)

### Community 31 - "Weather Precipitation & Station Models"
Cohesion: 0.20
Nodes (5): Meta, PrecipitationRaster, Interpolated precipitation raster layer, WeatherStation, WMSLayer

### Community 32 - "External Data Exceptions & GEE Importer"
Cohesion: 0.22
Nodes (8): get_raster_field_name(), Find the name of the RasterField on a model., Exception, GEEImporter, _ImportBlocked, External Data Catalog & Import Logic =====================================…, Import handler for Google Earth Engine datasets., Raised by _import_geojson_features when the whole import can't proceed at all…

### Community 33 - "Map Config JS"
Cohesion: 0.25
Nodes (7): availableLayers, BASEMAPS, CONFIG, layerVisibility, loadedLayers, TOOL_CATEGORIES, TOOL_CONTENT

### Community 34 - "Version & Git Info Utility"
Cohesion: 0.32
Nodes (6): _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. 0–99 → v0.1, 100–199 →…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 35 - "External Import Discussion & Overrides"
Cohesion: 0.36
Nodes (8): CBS (Centraal Bureau voor de Statistiek), Data Freshness and Provenance, EXTERNAL_DATA_CATALOG, External Data Import Pipeline, MODEL_OVERRIDES Dict, Open Data Dependency, PDOK, pdok_cities Bounding-box Exception

### Community 36 - "Non-Revenue Water Losses Model"
Cohesion: 0.29
Nodes (4): LossesChoices, LossesTypes, NonRevenueWater, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 37 - "Common Admin Registrations"
Cohesion: 0.33
Nodes (5): CityAdmin, LandCoverClassesAdmin, NeighborhoodAdmin, ProvinceAdmin, SurfaceMaterialPropertiesAdmin

### Community 38 - "Nature Domain Paper Coverage"
Cohesion: 0.33
Nodes (6): Forests Model, GreenSpaces Model, nature App, ProtectedArea Model, WaterBodies Model, WaterWays Model

### Community 39 - "CBS Importer"
Cohesion: 0.33
Nodes (4): CBSImporter, Import handler for CBS StatLine OData datasets., Fetch tabular data from CBS OData API and import to Django model. Args:…, Fetch column definitions and units for a CBS table. Useful for building field…

### Community 40 - "PDOK WCS Importer"
Cohesion: 0.40
Nodes (4): PDOKImporter, Fetch raster data from PDOK WCS service, tiling the request when the area would…, Import handler for PDOK datasets - imports directly to Django models., Split [min_v, max_v] into evenly-sized segments, each no larger than…

### Community 50 - "Manage.py Entrypoint"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 63 - "Consumption Per Capita & Signals"
Cohesion: 0.67
Nodes (3): receiver, Recalculate total_consumption_m3_d for all records of this city whenever the…, update_consumption_on_population_change()

## Ambiguous Edges - Review These
- `syncHeaderHeight` → `LoadingManager (fetch/XHR interceptor)`  [AMBIGUOUS]
  Templates/base.html · relation: shares_data_with

## Knowledge Gaps
- **145 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `Migration` (+140 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 554 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **75 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `syncHeaderHeight` and `LoadingManager (fetch/XHR interceptor)`?**
  _Edge tagged AMBIGUOUS (relation: shares_data_with) - confidence is low._
- **Why does `Plan: Admin-Level Map Panel Selection` connect `Indicator Dashboard Cards` to `Water Supply Calculations & Views`, `Map Init & Import Templates`?**
  _High betweenness centrality (0.191) - this node is a cross-community bridge._
- **Why does `common/admin_units.py (planned)` connect `Water Supply Calculations & Views` to `Indicator Dashboard Cards`?**
  _High betweenness centrality (0.180) - this node is a cross-community bridge._
- **Why does `City` connect `Admin Hierarchy & App Registration` to `Housing & Zoning Domain`, `External Data Exceptions & GEE Importer`, `Water Supply Calculations & Views`, `Geodata Upload Forms & Views`, `CBS Importer`, `Water Supply Infrastructure Models`, `Urban Heat Raster Models`, `Metered Residential Water Tests`, `Nature Domain Models`, `Water Supply Infrastructure Models`, `Sentinel-2 Importer`?**
  _High betweenness centrality (0.168) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `City` (e.g. with `cities_within()` and `neighborhoods_within()`) actually correct?**
  _`City` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Neighborhood` (e.g. with `Building` and `Facility`) actually correct?**
  _`Neighborhood` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `Province` (e.g. with `cities_within()` and `neighborhoods_within()`) actually correct?**
  _`Province` has 12 INFERRED edges - model-reasoned connections that need verification._