# Graph Report - CrossTwin  (2026-10-27)

## Corpus Check
- 139 files · ~145,369 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 21 file(s) not represented in the graph (top: (none) 5, .css 3, .dot 2)

## Summary
- 1782 nodes · 3402 edges · 122 communities (87 shown, 24 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 283 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a514ab56`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- City
- Layers.js
- svf.py
- watersupply/signals.py
- physicalEnv/signals.py
- watersupply/calculations.py
- Editing.js
- importer/views.py
- editing.py
- watersupply/models.py
- housing/calculations.py
- builtup/views.py
- calculate_lst
- import_dataset
- gee.py
- smw.py
- external_data.py
- urban_heat/calculations.py
- Meta
- ConsumptionCapita
- settings_views.py
- weather/views.py
- mainMap/views.py
- charts.py
- Diagram
- lst/views.py
- _import_geojson_features
- builtup/models.py
- export_raster_to_cog
- OSMImporter
- nature/models.py
- say
- Grid
- cache.py
- example_db.py
- rasterStyles.py
- initBboxMap
- physicalEnv/views.py
- Map_init.js
- TODO - Unimplemented DAG Edges
- .save
- check_postgres.py
- InterpolatedRasterBase
- upload_geodata
- init
- deferred_cascades
- _import_atom_gml_features
- urban_heat/partials/indicators_grid.html
- load_raster_into_target_model
- watersupply indicators_panel.html (HTMX side panel)
- base.html (site shell template)
- weather/signals.py
- mainMap/urls.py
- CrossTwin README
- requirements.txt
- Config.js
- BulkWriter
- SoilType
- housing/partials/indicators_panel.html
- _geojson_sql
- builtup indicators_panel.html (HTMX side panel)
- _get_git_info
- arch_export.py
- weather/models.py
- overrides.py
- layerStyles.py
- resolve_admin_unit
- Command
- QueryStatsMiddleware
- PDOKImporter
- GeoUploadForm
- Digital twin concept: real city (left) mirrored by wireframe model (right)
- water.js
- MapSettings.js
- physicalEnv/admin.py
- pipeline.py
- NonRevenueWater
- core/signals.py
- TemperatureRaster
- resolve_admin_unit_at_point
- AdministrativeConfig
- sky_view_factor
- CrossTwin App Icon (192x192)
- settings.py
- .fetch
- importer:upload_geodata view
- manage.py
- PhysicalEnvConfig
- WatersupplyConfig
- StressCategory
- WeatherConfig
- BuiltupConfig
- get_area
- CrossTwin App Icon (apple-touch-icon)
- CrossTwin favicon 16x16
- CrossTwin favicon (32x32)
- EnergyConfig
- HousingConfig
- ImporterConfig
- NatureConfig
- profile_requests.py
- UrbanheatConfig
- watershed_share
- LayerStyleOverride
- asgi.py
- wsgi.py
- NeighborhoodHeat
- .get_queryset
- StyleSuggestion.md (design system suggestion)
- AppConfig
- crosstwin

## God Nodes (most connected - your core abstractions)
1. `City` - 50 edges
2. `Neighborhood` - 36 edges
3. `Province` - 28 edges
4. `say()` - 28 edges
5. `neighborhoods_within()` - 26 edges
6. `Building` - 21 edges
7. `import_dataset()` - 21 edges
8. `_get_adminUnit_data()` - 20 edges
9. `District` - 19 edges
10. `calculate_lst()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `watersupply indicators_panel.html (HTMX side panel)` --semantically_similar_to--> `builtup indicators_panel.html (HTMX side panel)`  [INFERRED] [semantically similar]
  watersupply/templates/watersupply/partials/indicators_panel.html → builtup/templates/builtup/partials/indicators_panel.html
- `watersupply indicators_grid.html` --conceptually_related_to--> `No inline <script> blocks convention`  [AMBIGUOUS]
  watersupply/templates/watersupply/partials/indicators_grid.html → README.md
- `SVF tool card (#svf-card)` --conceptually_related_to--> `DSM -> SVF -> Tmrt/PET -> UTCI chain gap (SOLWEIG)`  [INFERRED]
  mainMap/templates/mainMap.html → TODO.md
- `ElectricityCost` --uses--> `Province`  [INFERRED]
  Energy/models.py → administrative/models.py
- `TotalWaterProduction` --uses--> `ElectricityCost`  [INFERRED]
  watersupply/models.py → Energy/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **External import area-of-interest picker flow** — importer_templates_importer_external_data_updateui, importer_templates_importer_external_data_pickerlevelfor, importer_templates_importer_external_data_setpickerlevel, importer_templates_importer_external_data_loadpickerlevel, importer_templates_importer_external_data_togglearea, importer_templates_importer_external_data_unionbbox [EXTRACTED 1.00]
- **Shared ? info button and popover help system** — templates_partials__info_btn, templates_partials__info_popover, watersupply_templates_watersupply_partials_indicators_grid, housing_templates_housing_partials_indicators_grid, urban_heat_templates_urban_heat_partials_indicators_grid [EXTRACTED 1.00]
- **Map editing UI (feature form, backup bar, Editing.js, core.editing)** — mainmap_templates_mainmap_partials_feature_form, mainmap_templates_mainmap_partials_backup_bar, core_static_js_editing, core_editing [EXTRACTED 1.00]
- **Standalone dashboards extending indicators_base.html** — housing_templates_housing_housing_indicators, urban_heat_templates_urban_heat_heat_indicators, watersupply_templates_watersupply_water_indicators, templates_indicators_base [EXTRACTED 1.00]
- **Water dashboard what-if controls (consumption, rain_mm, season) driving indicator grid recalculation** — watersupply_templates_watersupply_partials_indicators_panel_consumption_slider, watersupply_templates_watersupply_partials_rain_slider, watersupply_templates_watersupply_partials_rain_slider_season_switch, watersupply_templates_watersupply_partials_indicators_grid [EXTRACTED 1.00]
- **CrossTwin icon composition: physical city, digital wireframe, orbit ring** — core_static_ico_android_chrome_512x512_isometric_city_block, core_static_ico_android_chrome_512x512_cyan_wireframe_grid, core_static_ico_android_chrome_512x512_orbit_ring [INFERRED 0.85]
- **Domain HTMX side-panel dashboards swapped into #panel-body** — mainmap_templates_mainmap_toolbar, mainmap_templates_mainmap_side_panel, builtup_templates_builtup_partials_indicators_panel, watersupply_templates_watersupply_partials_indicators_panel, housing_templates_housing_partials_indicators_grid [INFERRED 0.85]

## Communities (122 total, 24 thin omitted)

### Community 0 - "City"
Cohesion: 0.07
Nodes (51): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, cities_within(), city_of(), province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any…, Resolve the enclosing Province for an admin unit at any level. Needed for… (+43 more)

### Community 1 - "Layers.js"
Cohesion: 0.06
Nodes (64): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+56 more)

### Community 2 - "svf.py"
Cohesion: 0.11
Nodes (32): DigitalSurfaceModel, _area(), calculate_svf(), dsm_extent(), dsm_for_view(), existing_svf(), _intersection(), load_dsm() (+24 more)

### Community 3 - "watersupply/signals.py"
Cohesion: 0.10
Nodes (39): SupplySecurity, TotalWaterProduction, _cities_in_watersheds(), city_population_cascaded(), city_saved(), consumption_saved(), deferred_water_refresh(), demand_saved() (+31 more)

### Community 4 - "physicalEnv/signals.py"
Cohesion: 0.06
Nodes (60): bump_layer_version(), Invalidate every cached response built from these models' rows., is_restoring(), True while restore_backup() runs. Receivers that undo an edit's side effects on…, _finalize_landcover(), Batch-import helpers shared by the file-upload and external-data importers. -…, _buffer_sql(), Land-cover overlay edits driven by other layers. urbanize_around() turns a… (+52 more)

### Community 5 - "watersupply/calculations.py"
Cohesion: 0.07
Nodes (49): Area-weighted SCS result for a set of soil-group x land-cover pieces.…, summarize_infiltration(), active_wells_with_watershed(), calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage(), calculate_drought_area() (+41 more)

### Community 6 - "Editing.js"
Cohesion: 0.05
Nodes (54): _attachEditor(), _bindDrawEvents(), _cancelEdit(), _drawModeFor(), _featureUrl(), _hideOriginal(), _openEditorPanel(), _removeDrawControl() (+46 more)

### Community 7 - "importer/views.py"
Cohesion: 0.27
Nodes (6): build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., MappingForm, Dynamic form for field mapping. Fields are added dynamically in the view based…, gpd_read_any(), Read an uploaded file (GeoJSON, Shapefile zip, etc.) into a GeoDataFrame.…

### Community 8 - "editing.py"
Cohesion: 0.06
Nodes (52): active_backup(), backup(), _backup_bar(), backup_discard(), backup_restore(), _build_form(), _check_constraints(), editable_keys() (+44 more)

### Community 9 - "watersupply/models.py"
Cohesion: 0.09
Nodes (15): WMSLayerAdmin, Yearly recharge of a fresh-water source in Mm3/year: the depth of water that…, recharge_Mm3_yr(), AreaAffectedDrought, AvailableFreshWater, CoverageWaterSupply, ImportedWater, Meta (+7 more)

### Community 10 - "housing/calculations.py"
Cohesion: 0.06
Nodes (51): neighborhoods_within(), Neighborhood queryset covering the given administrative unit, at any level., population_params(), (scenario, growth_adjust_pct) from a request's query parameters `pop_scenario`…, Property, calculate_affordability(), calculate_house_price_index(), calculate_mortgage_indicators() (+43 more)

### Community 11 - "builtup/views.py"
Cohesion: 0.13
Nodes (25): get_population(), Projected population of `unit` in `year` (its current population if `year` is…, calculate_building_age(), calculate_building_mix(), calculate_building_stock(), calculate_facilities(), calculate_green_space(), calculate_street_network() (+17 more)

### Community 12 - "calculate_lst"
Cohesion: 0.19
Nodes (14): calculate_lst(), default_window(), grid_for(), LSTError, ndvi_layer(), RuntimeError, [from, to) around the NDVI acquisition; summer of its year when it has no date., The NDVI layers and grid of a run: a map view, or one NDVI layer's extent. (+6 more)

### Community 13 - "import_dataset"
Cohesion: 0.13
Nodes (14): import_dataset(), ImportResult, Register a WMS layer by creating/updating its row in the target WMS model. This…, Import handler for Sentinel-2 datasets., Look up the real acquisition timestamp of the most recent Sentinel-2 L2A scene…, Fetch raster from Sentinel-2 WCS (e.g., WorldCover)., Fetch processed Sentinel-2 imagery via the Copernicus Data Space Ecosystem's…, Register a Sentinel-2 WMS layer by creating/updating its row in the target WMS… (+6 more)

### Community 14 - "gee.py"
Cohesion: 0.11
Nodes (22): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE for the given Cloud project. `ee.Authenticate()` is a one-time-…, check_download_size(), _collections(), download_bytes(), fetch_scene_inputs(), find_scenes() (+14 more)

### Community 15 - "smw.py"
Cohesion: 0.12
Nodes (23): Constants of the Statistical Mono-Window (SMW) LST algorithm for Landsat 8/9.…, apply_qa_emissivity(), bare_ground_emissivity(), _bit_set(), cloud_mask(), fractional_vegetation_cover(), interpolate_tpw(), land_surface_temperature() (+15 more)

### Community 16 - "external_data.py"
Cohesion: 0.11
Nodes (22): GEOSGeometry, ensure_multipolygon(), GEEImporter, _hilucs_lookup(), _import_feature_rows(), _prepare_features(), External Data Catalog & Import Logic =====================================…, Resolve the mapping's __fk_lookup__ entries for one feature: a plain (non-… (+14 more)

### Community 17 - "urban_heat/calculations.py"
Cohesion: 0.10
Nodes (32): calculate_green_area(), calculate_nbs_coverage(), calculate_urban_morphology(), calculate_vegetation_coverage(), classify_pet(), classify_utci(), classify_wbgt(), get_latest_meteorology() (+24 more)

### Community 18 - "Meta"
Cohesion: 0.08
Nodes (16): MeanRadiantTemperature, Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, PET, Physiological Equivalent Temperature (PET) measurements, Surface Urban Heat Island Intensity (SUHII)) measurements, Nature-Based Solutions (NBS) for urban heat mitigation (+8 more)

### Community 19 - "ConsumptionCapita"
Cohesion: 0.09
Nodes (22): calculate_total_demand(), _get_consumption_capita(), _get_consumption_record_years(), Per city of the unit, the ConsumptionCapita record used for `year`…, Per-capita consumption (L/person/day) for an admin unit and year. Mean over the…, Total water demand in m³/day across all cities in an admin unit., baseline_population(), consumption_m3_yr() (+14 more)

### Community 20 - "settings_views.py"
Cohesion: 0.14
Nodes (24): enable_blocker(), Why the layer `key` may not be switched on, or None when it may. A model whose…, _colormaps(), _editable_row(), _forbidden(), _layer_name(), map_settings(), _parse_target() (+16 more)

### Community 21 - "weather/views.py"
Cohesion: 0.13
Nodes (21): WMSLayer, _fetch_with_retry(), _find_dimension_values(), _last_n_time_steps(), _local_tag(), _parse_iso8601(), _parse_iso8601_duration(), Return the raw text of the <Dimension name="time"> for a given layer. (+13 more)

### Community 22 - "mainMap/views.py"
Cohesion: 0.18
Nodes (16): raster_display_name(), Build a display name matching the legend label plus the acquisition date as MM-…, available_layers(), _extract_unit(), _field_label(), _field_meta_entry(), _field_metadata(), _humanize_field_name() (+8 more)

### Community 23 - "charts.py"
Cohesion: 0.16
Nodes (19): band_d(), build_population_chart(), pts(), x_of(), y_of(), _fmt(), monotone_segments(), nice_step() (+11 more)

### Community 24 - "Diagram"
Cohesion: 0.10
Nodes (21): _raster_statistics(), Band-1 min/max of the stored raster itself (GDAL skips nodata cells). The…, apps(), Diagram, editing(), importer(), infiltration(), on_demand() (+13 more)

### Community 25 - "lst/views.py"
Cohesion: 0.22
Nodes (18): BadRequest, _bbox(), _date(), _error(), _grid_json(), lst_calculate(), view(), lst_scenes() (+10 more)

### Community 26 - "_import_geojson_features"
Cohesion: 0.10
Nodes (16): Exception, Point-in-polygon lookup against a fixed set of parent rows. Each parent's…, Load only what the lookup needs: pk, geom and any attributes read off the…, The parent containing `geom`'s representative point, or None., SpatialParentIndex, _enrich_rows(), get_model_class(), _import_geojson_features() (+8 more)

### Community 27 - "builtup/models.py"
Cohesion: 0.05
Nodes (29): bag_usage_labels(), Building, BuildingEnergyLabel, Facility, Meta, NeighborhoodClimateRisk, Park, BAG gebruiksdoel as a list of labels (Building.BAG_USAGE_FUNCTIONS). WFS… (+21 more)

### Community 28 - "export_raster_to_cog"
Cohesion: 0.15
Nodes (14): Command, BaseCommand, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), interpolate_raster(), Build a COG filename from whatever satellite/process metadata the raster model… (+6 more)

### Community 29 - "OSMImporter"
Cohesion: 0.17
Nodes (9): OSMImporter, Import handler for OpenStreetMap through the Overpass API. The Overpass JSON is…, Overpass QL for `dataset` inside bbox [west, south, east, north] (WGS84)., Leading number of an OSM tag value: '12 m' -> 12.0, '7,5' -> 7.5, '40 ft' ->…, (Multi)polygon of a multipolygon relation from its member ways. A ring may be…, GeoJSON geometry of one Overpass element (out center or out geom)., Overpass elements -> GeoJSON features whose properties are the OSM tags plus…, OSM tags are strings ('12 m'); give numeric model fields a number, or drop the… (+1 more)

### Community 30 - "nature/models.py"
Cohesion: 0.15
Nodes (9): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, Tree, WaterBodies, WaterWaysLN (+1 more)

### Community 31 - "say"
Cohesion: 0.10
Nodes (21): Console progress lines for the importers (upload wizard, external import), so…, One console line. Forced to ASCII: a character the Windows cp1252 console can't…, say(), get_catalog_grouped(), _kea_building(), _kea_neighborhood(), Mapping for a per-buurt KEA layer: one row per stored neighborhood, keyed on…, Return the catalog grouped by category. Structure: { category: [datasets] }… (+13 more)

### Community 32 - "Grid"
Cohesion: 0.13
Nodes (9): Grid, The one raster grid every LST input is put on before the equations run., Smallest grid with corners on multiples of `resolution` that covers the extent., Affine in Earth Engine's order: [xScale, xShear, xOffset, yShear, yScale,…, [west, south, east, north] in EPSG:4326, for filtering image collections., North-up grid: (x0, y0) is the top-left corner, cells are `resolution` m square., LSTResult, Grid over the part of the view the NDVI layers cover (LST is empty elsewhere). (+1 more)

### Community 33 - "cache.py"
Cohesion: 0.23
Nodes (11): get_cache(), _label(), layer_version(), Versioned cache keys for data that only changes when rows are written. Every…, caches[alias], falling back to the default cache when the alias isn't…, Current cache version of a model's data. A missing version is seeded with the…, _version_key(), model_geojson() (+3 more)

### Community 34 - "example_db.py"
Cohesion: 0.19
Nodes (21): _check_target_db(), _connection_args(), _crosstwin_version(), _db_settings(), _django(), dump(), load(), main() (+13 more)

### Community 35 - "rasterStyles.py"
Cohesion: 0.13
Nodes (19): get_raster_info(), get_raster_tiles(), Return raster metadata including bounds., Return TiTiler tile URL for a given raster layer., apply_raster_override(), raster_override(), Override data for a raster style key, or None., (colormap, rescale, label, unit) with an override's colormap / range applied. (+11 more)

### Community 36 - "initBboxMap"
Cohesion: 0.15
Nodes (12): Catalog bbox_from (area-of-interest picker level), external_data.html (Import Public Data), clearBbox(), Import Selected click handler (POST start_external_import), initBboxMap(), loadPickerLevel(), pickerLevelFor(), setPickerLevel() (+4 more)

### Community 37 - "physicalEnv/views.py"
Cohesion: 0.19
Nodes (17): BadRequest, _bbox(), _dsm_json(), _error(), _existing_json(), _number(), _params(), require_GET (+9 more)

### Community 38 - "Map_init.js"
Cohesion: 0.24
Nodes (11): updateCityName(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, changeBasemap(), getSavedCameraState(), initializeUrbanTwinMap(), onAdminLayerLoaded() (+3 more)

### Community 39 - "TODO - Unimplemented DAG Edges"
Cohesion: 0.16
Nodes (14): housing indicators_grid.html, Average Fixed Mortgage Rate card (annuity, 30y), Pipeline land take (greenfield vs infill) display, Zoning & Land Value card (HILUCS shares), Population dock, No inline <script> blocks convention, TODO - Unimplemented DAG Edges, Indicator threshold alerting system (backlog) (+6 more)

### Community 40 - ".save"
Cohesion: 0.12
Nodes (7): The most recent cost record (the model has no province/year), or None., MeteredResidential, DAG edges: Available_FW -> Total_Extraction Total_Extraction ->…, DAG edges: Total_Extraction/Total_Water_Prod -> OPEX Imported_Water -> OPEX,…, Derived from the geometry: affected area (km2) and, if not given, the Province., Set productionDay/YR (Mm3) and costDay/YR (EUR) from the active wells of the…, Watershed

### Community 41 - "check_postgres.py"
Cohesion: 0.32
Nodes (13): _connect(), _create_extensions_help(), _diagnose_connection_error(), _install_postgis_help(), _install_postgres_help(), main(), _postgres_binaries(), Check that PostgreSQL is reachable with the .env settings and has PostGIS. Run… (+5 more)

### Community 42 - "InterpolatedRasterBase"
Cohesion: 0.10
Nodes (13): HumidityRaster, InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:…, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child… (+5 more)

### Community 43 - "upload_geodata"
Cohesion: 0.14
Nodes (16): atomic, _build_mapping_form(), _get_expected_geom_type(), _get_model_spec(), _raster_import(), Read a raster file and optionally reproject it. Returns a dict with raster…, The import's outcome on one line, plus its first errors., Import a raster file into a Django model with RasterField stored in PostGIS.… (+8 more)

### Community 44 - "init"
Cohesion: 0.33
Nodes (12): init(), calculate(), csrfToken(), loadInfo(), open(), params(), readJson(), refreshButton() (+4 more)

### Community 45 - "deferred_cascades"
Cohesion: 0.18
Nodes (11): deferred_cascades(), Run the administrative population cascade, the land-cover urban-area recompute…, _cast_value(), _fit_geometry_type(), _generic_import(), Best-effort cast to Django field type., Resolve FK by name (case-insensitive) or id. Works for City-like foreign keys.…, Convert between single and multi geometries to match the target field: a Point… (+3 more)

### Community 46 - "_import_atom_gml_features"
Cohesion: 0.24
Nodes (5): _gml_multipolygon(), _import_atom_gml_features(), WGS84 MultiPolygon of every gml:Polygon below `elem` (None if there are none,…, Stream an INSPIRE Planned Land Use GML file over HTTP and import the…, Polygon

### Community 47 - "urban_heat/partials/indicators_grid.html"
Cohesion: 0.23
Nodes (9): applyZone(), zoneStyle(), initGauges() (global), partials/_info_btn.html, partials/_info_popover.html, Thermal comfort indices (LST, PET, UTCI, WBGT, SVF, SUHII), heat_indicators.html (Urban Heat Dashboard), Vegetation Coverage what-if slider (+1 more)

### Community 48 - "load_raster_into_target_model"
Cohesion: 0.20
Nodes (10): get_raster_field_name(), Find the name of the RasterField on a model., datetime, KNMIImporter, load_raster_into_target_model(), KNMI Data Platform (Open Data API v1). Flow: list the newest file of a dataset…, UTC datetime encoded in a KNMI file name, or None if it has none., Convert a downloaded KNMI grid to a single-band float32 GeoTIFF in… (+2 more)

### Community 49 - "watersupply indicators_panel.html (HTMX side panel)"
Cohesion: 0.29
Nodes (11): Watersupply gaps (collection ratio, WT_Efficiency, Apparent_Losses -> ILI), Consumption per Capita what-if slider, watersupply indicators_grid.html, Infiltration card (SCS Curve Number), Non-Revenue Water card (ILI), Supply Security / Service Time cards, watersupply indicators_panel.html (HTMX side panel), Consumption per Capita slider (+3 more)

### Community 50 - "base.html (site shell template)"
Cohesion: 0.18
Nodes (12): Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono), base.html (site shell template), Template blocks (extra_css, extra_js, content), Header height CSS variable sync, HTMX 1.9.10 library (+4 more)

### Community 51 - "weather/signals.py"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 52 - "mainMap/urls.py"
Cohesion: 0.29
Nodes (4): Like <int:>, but also matches negative ids (user-created Buildings, see…, SignedIntConverter, map_view(), Display the map page.

### Community 53 - "CrossTwin README"
Cohesion: 0.27
Nodes (11): CrossTwin README, DAG edge coverage (31 of 103 edges implemented), deferred_cascades() bulk-write batching, DPSIR Causal Framework (core/DAG.dot), Cached GeoJSON API with viewport loading, Importer System (file upload + external catalog), Model Registry (MODEL/VECTOR/RASTER/WMS_REGISTRY), Raster to COG Pipeline (+3 more)

### Community 54 - "requirements.txt"
Cohesion: 0.18
Nodes (10): django-crispy-forms + crispy-tailwind, Django 5.2.12, earthengine-api 1.7.18, GDAL 3.11.4 (Windows wheel), geopandas 1.1.2, openeo 0.51.0, owslib 0.35.0, rasterio 1.4.4 (+2 more)

### Community 55 - "Config.js"
Cohesion: 0.22
Nodes (9): availableLayers, BASEMAPS, CONFIG, layerVisibility, loadedLayers, roundBboxInUrl(), roundCoord(), TOOL_CATEGORIES (+1 more)

### Community 56 - "BulkWriter"
Cohesion: 0.27
Nodes (4): BulkWriter, Collects rows and writes them `batch_size` at a time. With a unique field, rows…, A writer when `Model` can safely be bulk-written, otherwise None (use the row…, Write what is left, replay the skipped signals and invalidate the layer cache.

### Community 57 - "SoilType"
Cohesion: 0.24
Nodes (7): build_soil_style_and_legend(), Colours of the soil map (physicalEnv.SoilArea), taken from the legend of the…, (style_layers, legend) for physicalEnv.SoilArea: a `match` on the…, A soil unit of the Dutch soil map (Bodemkaart 1:50 000, BIS Nederland), stored…, SoilType, classify_soil_group(), Hydrologic soil group 'A'-'D' of a Dutch soil map name, or None if it names no…

### Community 58 - "housing/partials/indicators_panel.html"
Cohesion: 0.25
Nodes (7): applyZone(), zoneStyle(), housing_indicators.html (Province Housing Dashboard), Mortgage Interest Rate what-if slider, pop_scenario / pop_growth population what-if params, indicators_base.html (standalone dashboard shell), #indicators-grid HTMX swap target

### Community 59 - "_geojson_sql"
Cohesion: 0.20
Nodes (10): _display_field(), _geojson_sql(), layer_bounds(), _manager_filter(), Pick the field on a related model that best represents it in a popup: the first…, About one screen pixel at `zoom`, in the storage CRS's units (metres, or…, (sql, params) restricting `t` to the rows of the model's default manager, or…, (sql, params) returning the layer as one FeatureCollection JSON text. - FK… (+2 more)

### Community 60 - "builtup indicators_panel.html (HTMX side panel)"
Cohesion: 0.22
Nodes (8): builtup_indicators.html (standalone dashboard), builtup indicators_grid.html, Built-up Coverage / FAR card, Park Area per Inhabitant card (WHO 9/50 m2), builtup indicators_panel.html (HTMX side panel), Additional Park Area slider (green_added_ha), Three-Layer Indicator Dashboard Pattern, MOCK_DATA fallback

### Community 61 - "_get_git_info"
Cohesion: 0.21
Nodes (8): CoreConfig, AppConfig, _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. Counts half the commits:…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 62 - "arch_export.py"
Cohesion: 0.43
Nodes (7): browser(), main(), page(), Export docs/architecture/latest/*.svg to PNG and PDF with headless Chrome/Edge.…, One page per SVG, each page sized to its diagram (named @page rules)., run(), size()

### Community 63 - "weather/models.py"
Cohesion: 0.13
Nodes (8): Meta, Meteorology, PrecipitationRaster, Interpolated precipitation raster layer, Interpolated wind speed raster layer, Time-series weather measurements from stations, WeatherStation, WindSpeedRaster

### Community 64 - "overrides.py"
Cohesion: 0.12
Nodes (23): Form fields of a vector style: default value, current value, input kind., _vector_fields(), build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…, apply_vector_override() (+15 more)

### Community 65 - "layerStyles.py"
Cohesion: 0.33
Nodes (5): Map styling of the vector layers: Mapbox GL style layers, legend entries and…, build_tree_style(), Map style of nature.Tree: green dots when zoomed out, a 3D glTF tree per point…, style_layers for nature.Tree. The circle layer comes first: it is the click…, _uniform()

### Community 66 - "resolve_admin_unit"
Cohesion: 0.20
Nodes (11): Look up a Province/City/District/Neighborhood instance by level + name., resolve_admin_unit(), build_population_stats(), Numbers shown next to the graph: today, the selected year, the change and the…, dashboard_summary(), population_panel(), The administrative unit the population views talk about, as (level, unit,…, HTMX partial for the Dashboard panel: total population of the selected… (+3 more)

### Community 67 - "Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Show the most expensive SQL statements recorded by pg_stat_statements…

### Community 69 - "PDOKImporter"
Cohesion: 0.29
Nodes (5): PDOKImporter, Import handler for PDOK datasets - imports directly to Django models., Fetch vector data from PDOK WFS service and import directly to Django model.…, Split [min_v, max_v] into evenly-sized segments, each no larger than…, Fetch raster data from PDOK WCS service, tiling the request when the area would…

### Community 70 - "GeoUploadForm"
Cohesion: 0.25
Nodes (6): GeoUploadForm, get_target_model_choices(), Get choices for target model field., Form for uploading geodata files (GeoJSON or Shapefile)., Validate uploaded file has correct extension., Validate source CRS is a valid EPSG code.

### Community 71 - "Digital twin concept: real city (left) mirrored by wireframe model (right)"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 72 - "water.js"
Cohesion: 0.60
Nodes (4): applyRain(), applyZone(), rainStyle(), zoneStyle()

### Community 73 - "MapSettings.js"
Cohesion: 0.46
Nodes (6): applyEditable(), applyStyle(), catalogEntry(), init(), preview(), readdLayer()

### Community 74 - "physicalEnv/admin.py"
Cohesion: 0.40
Nodes (4): HILUCSLandUseAdmin, LandCoverClassesAdmin, SoilTypeAdmin, SurfaceMaterialPropertiesAdmin

### Community 75 - "pipeline.py"
Cohesion: 0.14
Nodes (17): LandCoverRaster, ndvi_layers_in(), ndvi_mosaic(), _ndvi_queryset(), LST from Landsat 9 + CrossTwin's NDVI layer, stored as a LandSurfaceTemperature…, NDVI layers overlapping the view, newest first., Band 1 of a GDALRaster averaged onto `grid` (NaN outside it / at nodata)., NDVI on the grid; where layers overlap, the first (newest) one wins. (+9 more)

### Community 76 - "NonRevenueWater"
Cohesion: 0.25
Nodes (4): LossesChoices, LossesTypes, NonRevenueWater, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 77 - "core/signals.py"
Cohesion: 0.33
Nodes (6): auto_export_cog(), invalidate_layer_cache(), One console line about the COG export, e.g. [cog] LandSurfaceTemperature id=3:…, (Re)create the COG whenever a raster row is saved, so the map never shows a…, Orphan the cached GeoJSON of a vector layer whenever one of its rows changes., _say()

### Community 79 - "resolve_admin_unit_at_point"
Cohesion: 0.33
Nodes (6): Built once per process: creating a GDAL/PROJ transformation is the slow part of…, Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), _wgs84_to_storage(), admin_unit_at_point(), Point-in-polygon lookup for the map center: resolve the smallest administrative…

### Community 81 - "sky_view_factor"
Cohesion: 0.33
Nodes (6): horizon_shift_vector(), Sky-view factor of a surface model. height: 2D array of elevations in metres…, Pixel offsets visited by the horizon search, per azimuth. Returns {azimuth_deg:…, SVF of the `rows` x `cols` interior of `padded` (heights in cell units)., sky_view_factor(), _svf_block()

### Community 82 - "CrossTwin App Icon (192x192)"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 84 - ".fetch"
Cohesion: 0.33
Nodes (4): CBSImporter, Import handler for CBS StatLine OData datasets., Fetch tabular data from CBS OData API and import to Django model. Args:…, Fetch column definitions and units for a CBS table. Useful for building field…

### Community 85 - "importer:upload_geodata view"
Cohesion: 0.67
Nodes (4): FieldMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 86 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 93 - "CrossTwin App Icon (apple-touch-icon)"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 94 - "CrossTwin favicon 16x16"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 95 - "CrossTwin favicon (32x32)"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

### Community 102 - "watershed_share"
Cohesion: 0.50
Nodes (4): Neighborhoods served by a watershed: those whose point on surface lies in it.…, Share (0-1) of a watershed's water that goes to the population of adminBund.…, _watershed_neighborhoods(), watershed_share()

## Ambiguous Edges - Review These
- `No inline <script> blocks convention` → `housing indicators_grid.html`  [AMBIGUOUS]
  housing/templates/housing/partials/indicators_grid.html · relation: conceptually_related_to
- `No inline <script> blocks convention` → `watersupply indicators_grid.html`  [AMBIGUOUS]
  watersupply/templates/watersupply/partials/indicators_grid.html · relation: conceptually_related_to
- `DAG edge coverage (31 of 103 edges implemented)` → `Per-app DAG edge gap analysis`  [AMBIGUOUS]
  TODO.md · relation: conceptually_related_to

## Knowledge Gaps
- **72 isolated node(s):** `Scenario`, `availableLayers`, `loadedLayers`, `layerVisibility`, `CONFIG` (+67 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 755 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `No inline <script> blocks convention` and `housing indicators_grid.html`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `No inline <script> blocks convention` and `watersupply indicators_grid.html`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `DAG edge coverage (31 of 103 edges implemented)` and `Per-app DAG edge gap analysis`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `City` connect `City` to `watersupply/signals.py`, `physicalEnv/signals.py`, `watersupply/calculations.py`, `importer/views.py`, `watersupply/models.py`, `housing/calculations.py`, `calculate_lst`, `deferred_cascades`, `external_data.py`, `load_raster_into_target_model`, `ConsumptionCapita`, `.fetch`, `builtup/models.py`, `nature/models.py`, `weather/models.py`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Why does `feature_form.html (map feature editor)` connect `Editing.js` to `editing.py`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 20 INFERRED edges - model-reasoned connections that need verification._