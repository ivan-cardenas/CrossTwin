# Graph Report - CrossTwin  (2026-11-03)

## Corpus Check
- 194 files · ~185,475 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: (none) 5, .css 4, .dot 2)

## Summary
- 2127 nodes · 4178 edges · 132 communities (97 shown, 24 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 347 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Administrative Hierarchy & Population
- Map Editing Backend
- Map Layers & Panels (JS)
- Housing Indicators
- Water Supply Indicators
- Built-up Indicators & Models
- File Upload Importer
- Water Supply Signal Cascade
- Landing City & DAG Graphic
- External Feature Import
- Urban Heat Indicators
- Water Supply Models
- External Dataset Import Core
- Building Edit Signals
- SOLWEIG Meteorology
- Household Size & Projections
- SOLWEIG Views & Runs
- Architecture Diagram Tooling
- Map Layer Catalog API
- Earth Engine LST Inputs
- Vector Style Overrides
- Map Settings Views
- Housing Demand Signals
- External Data Catalog & Views
- Water Demand Chain
- Raster Styles & Tiles
- Physical Environment Models
- Landing City Plan & Fallback SVG
- Thermal Comfort Raster Models
- SMW LST Equations
- WMS Tile Proxy
- Landing Page Bootstrap
- Sky View Factor (SVF)
- SOLWEIG Pipeline & Staleness
- New Units -> Land Cover
- Soil Infiltration (SCS-CN)
- Example DB Dump/Load
- LST Command & Pipeline
- Layer Cache Versioning
- Population Forecast Chart
- LST NDVI Inputs
- LST Map Tool Views
- Nature Models
- SVF DSM Window Planning
- SVF Map Tool Views
- Raster to COG Export
- SOLWEIG Tool (JS)
- README & Project Concepts
- Landing Three.js Scene
- Map Page Templates
- OpenStreetMap Importer
- Map Init & 3D Buildings
- TODO & Housing Panel
- DSM Building Patches
- Map Editing (JS)
- LST Tool (JS)
- External Import Map UI
- SOLWEIG Inputs
- KNMI Raster Importer
- Map Config (Config.js)
- Landing Scroll Stages
- Guided Tour & Actions Menu
- Map URLs & Dashboard Summary
- PostgreSQL Health Check
- Humidity Raster Interpolation
- Base & Built-up Templates
- Heat Dashboard Templates
- Map Settings Panel (JS)
- SVF Tool (JS)
- App Version Info
- Water Dashboard Templates
- Water Extraction
- LST Grid
- Thermal Comfort Runs
- Interpolated Raster Base
- Weather Raster Signals
- Bulk Import Writer
- Spatial Parent Index
- Admin Unit Point Lookup
- Zoning Areas
- Architecture Diagram Export
- Non-Revenue Water
- Wind & Weather Stations
- Layer & Tree Styles
- DB Stats Command
- Query Stats Middleware
- CBS Importer
- SOLWEIG UMEP Writers
- Upload Templates
- App Icon 512
- HILUCS Land Use Codes
- Watersheds
- Precipitation Raster
- Temperature Raster
- administrative AppConfig
- App Icon 192
- Django Settings
- housing AppConfig
- manage.py
- physicalEnv AppConfig
- Style Suggestion Notes
- Heat Stress Categories
- watersupply AppConfig
- weather AppConfig
- builtup AppConfig
- Geo Area Helper
- Apple Touch Icon
- Favicon 16
- Favicon 32
- Energy AppConfig
- importer AppConfig
- nature AppConfig
- Request Profiler
- urban_heat AppConfig
- ASGI Entry
- WSGI Entry
- Housing Supply vs Demand
- Residential Property Manager
- Rain Event Slider
- pyproject Package
- Style Suggestion Doc

## God Nodes (most connected - your core abstractions)
1. `City` - 51 edges
2. `Neighborhood` - 36 edges
3. `Province` - 28 edges
4. `say()` - 28 edges
5. `neighborhoods_within()` - 27 edges
6. `Building` - 23 edges
7. `buildCity()` - 23 edges
8. `import_dataset()` - 21 edges
9. `bump_layer_version()` - 20 edges
10. `LandCoverVector` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Average Persons per Home what-if slider` --semantically_similar_to--> `Consumption per Capita what-if slider`  [INFERRED] [semantically similar]
  housing/templates/housing/partials/indicators_panel.html → watersupply/templates/watersupply/partials/indicators_panel.html
- `TotalWaterProduction` --uses--> `ElectricityCost`  [INFERRED]
  watersupply/models.py → Energy/models.py
- `AreaAffectedDrought` --uses--> `Province`  [INFERRED]
  watersupply/models.py → administrative/models.py
- `TotalWaterProduction` --uses--> `Province`  [INFERRED]
  watersupply/models.py → administrative/models.py
- `InterpolatedRasterBase` --uses--> `Province`  [INFERRED]
  weather/models.py → administrative/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Dashboard and side panel share slider/grid markup and domain JS** — readme_indicator_dashboard_pattern, watersupply_templates_watersupply_water_indicators, watersupply_templates_watersupply_partials_indicators_panel, watersupply_templates_watersupply_partials_indicators_grid, core_static_js_indicators_water, templates_indicators_base [EXTRACTED 1.00]
- **Shared ? info button and popover help system** — templates_partials__info_btn, templates_partials__info_popover, watersupply_templates_watersupply_partials_indicators_grid, housing_templates_housing_partials_indicators_grid, urban_heat_templates_urban_heat_partials_indicators_grid [EXTRACTED 1.00]
- **External import area-of-interest picker flow** — importer_templates_importer_external_data_updateui, importer_templates_importer_external_data_pickerlevelfor, importer_templates_importer_external_data_setpickerlevel, importer_templates_importer_external_data_loadpickerlevel, importer_templates_importer_external_data_togglearea, importer_templates_importer_external_data_unionbbox [EXTRACTED 1.00]
- **Calculate-for-this-view tool cards (LST, SVF, SOLWEIG)** — mainmap_templates_mainmap_lst_card, mainmap_templates_mainmap_svf_card, mainmap_templates_mainmap_solweig_card, mainmap_templates_mainmap_actions_menu [EXTRACTED 1.00]
- **Map editing UI (feature form, backup bar, Editing.js, core.editing)** — mainmap_templates_mainmap_partials_feature_form, mainmap_templates_mainmap_partials_backup_bar, core_static_js_editing, core_editing [EXTRACTED 1.00]
- **Map settings panel (editable layers + style overrides)** — mainmap_templates_mainmap_settings_card, mainmap_templates_mainmap_partials_map_settings, mainmap_templates_mainmap_partials_settings_editable_row, mainmap_templates_mainmap_partials_settings_style_form, core_static_js_mapsettings [EXTRACTED 1.00]
- **Standalone dashboards extending indicators_base.html** — housing_templates_housing_housing_indicators, urban_heat_templates_urban_heat_heat_indicators, watersupply_templates_watersupply_water_indicators, templates_indicators_base [EXTRACTED 1.00]
- **Water dashboard what-if controls (consumption, rain_mm, season) driving indicator grid recalculation** — watersupply_templates_watersupply_partials_indicators_panel_consumption_slider, watersupply_templates_watersupply_partials_rain_slider, watersupply_templates_watersupply_partials_rain_slider_season_switch, watersupply_templates_watersupply_partials_indicators_grid [EXTRACTED 1.00]
- **CrossTwin icon composition: physical city, digital wireframe, orbit ring** — core_static_ico_android_chrome_512x512_isometric_city_block, core_static_ico_android_chrome_512x512_cyan_wireframe_grid, core_static_ico_android_chrome_512x512_orbit_ring [INFERRED 0.85]
- **Landing fallback sketch generation flow** — core_static_js_landing_plan, tools_landing_fallback_svg, core_static_img_landing_city_blueprint, mainmap_templates_mainmap_landing [INFERRED 0.85]

## Communities (132 total, 24 thin omitted)

### Community 0 - "Administrative Hierarchy & Population"
Cohesion: 0.07
Nodes (56): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, cities_within(), city_of(), province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any…, Resolve the enclosing Province for an admin unit at any level. Needed for… (+48 more)

### Community 1 - "Map Editing Backend"
Cohesion: 0.05
Nodes (60): active_backup(), backup(), _backup_bar(), backup_discard(), backup_restore(), _build_form(), _check_constraints(), _editable_model() (+52 more)

### Community 2 - "Map Layers & Panels (JS)"
Cohesion: 0.06
Nodes (64): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+56 more)

### Community 3 - "Housing Indicators"
Cohesion: 0.06
Nodes (52): neighborhoods_within(), Neighborhood queryset covering the given administrative unit, at any level., population_params(), (scenario, growth_adjust_pct) from a request's query parameters `pop_scenario`…, Property, calculate_affordability(), calculate_dwellings(), calculate_house_price_index() (+44 more)

### Community 4 - "Water Supply Indicators"
Cohesion: 0.07
Nodes (49): Area-weighted SCS result for a set of soil-group x land-cover pieces.…, summarize_infiltration(), calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage(), calculate_drought_area(), calculate_energy_consumption() (+41 more)

### Community 5 - "Built-up Indicators & Models"
Cohesion: 0.08
Nodes (38): Look up a Province/City/District/Neighborhood instance by level + name., resolve_admin_unit(), get_population(), Projected population of `unit` in `year` (its current population if `year` is…, calculate_building_age(), calculate_building_mix(), calculate_building_stock(), calculate_facilities() (+30 more)

### Community 6 - "File Upload Importer"
Cohesion: 0.08
Nodes (37): atomic, deferred_cascades(), Run the administrative population cascade, the land-cover urban-area recompute,…, GeoUploadForm, get_target_model_choices(), MappingForm, Get choices for target model field., Dynamic form for field mapping. Fields are added dynamically in the view based… (+29 more)

### Community 7 - "Water Supply Signal Cascade"
Cohesion: 0.10
Nodes (39): SupplySecurity, TotalWaterProduction, _cities_in_watersheds(), city_population_cascaded(), city_saved(), consumption_saved(), deferred_water_refresh(), demand_saved() (+31 more)

### Community 8 - "Landing City & DAG Graphic"
Cohesion: 0.10
Nodes (35): alongPath(), buildCity(), update(), geometryFrom(), HEAT_STOPS, heatColor(), heatMaterial(), HOUSE_COLORS (+27 more)

### Community 9 - "External Feature Import"
Cohesion: 0.08
Nodes (31): Exception, GEOSGeometry, _enrich_rows(), ensure_multipolygon(), get_model_class(), _gml_multipolygon(), _import_atom_gml_features(), _import_feature_rows() (+23 more)

### Community 10 - "Urban Heat Indicators"
Cohesion: 0.09
Nodes (34): calculate_green_area(), calculate_nbs_coverage(), calculate_urban_morphology(), calculate_vegetation_coverage(), classify_pet(), classify_utci(), classify_wbgt(), get_latest_meteorology() (+26 more)

### Community 11 - "Water Supply Models"
Cohesion: 0.08
Nodes (18): WMSLayerAdmin, Yearly recharge of a fresh-water source in Mm3/year: the depth of water that…, recharge_Mm3_yr(), AreaAffectedDrought, AvailableFreshWater, CoverageWaterSupply, ImportedWater, Meta (+10 more)

### Community 12 - "External Dataset Import Core"
Cohesion: 0.09
Nodes (22): GEEImporter, import_dataset(), ImportResult, PDOKImporter, Import handler for PDOK datasets - imports directly to Django models., Fetch vector data from PDOK WFS service and import directly to Django model.…, Split [min_v, max_v] into evenly-sized segments, each no larger than…, Fetch vector data from an OGC API Features service (PDOK's newer REST/JSON… (+14 more)

### Community 13 - "Building Edit Signals"
Cohesion: 0.10
Nodes (33): is_editor_change(), is_restoring(), True inside a map-editor save or delete. Receivers that must react to a user's…, True while restore_backup() runs. Receivers that undo an edit's side effects on…, building_height(), Height above ground of a builtup.Building: height_m, else floors x…, Record an editor change of one building. before: its footprint before this edit…, record_change() (+25 more)

### Community 14 - "SOLWEIG Meteorology"
Cohesion: 0.09
Nodes (27): _distance_km(), _era5_day(), era5_day_from_values(), era5_from_values(), era5_hourly(), knmi_day_values(), _knmi_hour(), knmi_hourly() (+19 more)

### Community 15 - "Household Size & Projections"
Cohesion: 0.08
Nodes (19): PopulationProjection, Projected total population of a City for one year and forecast variant. Loaded…, Scenario, average_household_size(), baseline_population(), demand_units(), housed_residents(), The population -> household size -> housing demand / residents chain of the… (+11 more)

### Community 16 - "SOLWEIG Views & Runs"
Cohesion: 0.16
Nodes (29): (west, south, east, north) in degrees -> (minx, miny, maxx, maxy) in the…, wgs84_to_storage(), centre(), Status of a run for the map tool; a run left 'running' by a dead process reads…, run_state(), BadRequest, _bbox(), _error() (+21 more)

### Community 17 - "Architecture Diagram Tooling"
Cohesion: 0.11
Nodes (19): apps(), Diagram, editing(), importer(), infiltration(), on_demand(), overview(), raster() (+11 more)

### Community 18 - "Map Layer Catalog API"
Cohesion: 0.10
Nodes (28): editable_keys(), Registry keys of the layers switched on in the settings panel (one query)., raster_display_name(), Build a display name matching the legend label plus the acquisition date as MM-…, available_layers(), _display_field(), _extract_unit(), _field_label() (+20 more)

### Community 19 - "Earth Engine LST Inputs"
Cohesion: 0.11
Nodes (22): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE for the given Cloud project. `ee.Authenticate()` is a one-time-…, check_download_size(), _collections(), download_bytes(), fetch_scene_inputs(), find_scenes() (+14 more)

### Community 20 - "Vector Style Overrides"
Cohesion: 0.10
Nodes (26): Form fields of a vector style: default value, current value, input kind., _vector_fields(), build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…, apply_vector_override() (+18 more)

### Community 21 - "Map Settings Views"
Cohesion: 0.13
Nodes (26): enable_blocker(), Why the layer `key` may not be switched on, or None when it may. A model whose…, LayerStyleOverride, A map style set in the settings panel, on top of the default in mainMap/styles/…, _colormaps(), _editable_row(), _forbidden(), _layer_name() (+18 more)

### Community 22 - "Housing Demand Signals"
Cohesion: 0.11
Nodes (25): HousingSupplyDemand, city_population_cascaded(), city_saved(), deferred_housing_refresh(), _dwellings_of_city(), _flush_housing_refresh(), household_size_changed(), projection_changed() (+17 more)

### Community 23 - "External Data Catalog & Views"
Cohesion: 0.10
Nodes (21): Console progress lines for the importers (upload wizard, external import), so…, One console line. Forced to ASCII: a character the Windows cp1252 console can't…, say(), get_catalog_grouped(), _kea_building(), _kea_neighborhood(), Mapping for a per-buurt KEA layer: one row per stored neighborhood, keyed on…, Return the catalog grouped by category. Structure: { category: [datasets] }… (+13 more)

### Community 24 - "Water Demand Chain"
Cohesion: 0.09
Nodes (22): calculate_total_demand(), _get_consumption_capita(), _get_consumption_record_years(), Per city of the unit, the ConsumptionCapita record used for `year`…, Per-capita consumption (L/person/day) for an admin unit and year. Mean over the…, Total water demand in m³/day across all cities in an admin unit., baseline_population(), consumption_m3_yr() (+14 more)

### Community 25 - "Raster Styles & Tiles"
Cohesion: 0.10
Nodes (23): build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., get_raster_info(), get_raster_tiles(), Return raster metadata including bounds., Return TiTiler tile URL for a given raster layer., apply_raster_override(), raster_override() (+15 more)

### Community 26 - "Physical Environment Models"
Cohesion: 0.09
Nodes (17): HILUCSLandUseAdmin, LandCoverClassesAdmin, SoilTypeAdmin, SurfaceMaterialPropertiesAdmin, DigitalElevationModelWMS, DigitalSurfaceModelWMS, DSMEdit, GroundwaterDepth (+9 more)

### Community 27 - "Landing City Plan & Fallback SVG"
Cohesion: 0.16
Nodes (23): city_blueprint.svg (landing no-WebGL city sketch), blueprintSegments(), boundaries(), buildPlan(), canalX(), circleLine(), crossing(), inDisc() (+15 more)

### Community 28 - "Thermal Comfort Raster Models"
Cohesion: 0.10
Nodes (16): Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, NeighborhoodHeat, PET, Physiological Equivalent Temperature (PET) measurements, Surface Urban Heat Island Intensity (SUHII)) measurements, Nature-Based Solutions (NBS) for urban heat mitigation (+8 more)

### Community 29 - "SMW LST Equations"
Cohesion: 0.12
Nodes (23): Constants of the Statistical Mono-Window (SMW) LST algorithm for Landsat 8/9.…, apply_qa_emissivity(), bare_ground_emissivity(), _bit_set(), cloud_mask(), fractional_vegetation_cover(), interpolate_tpw(), land_surface_temperature() (+15 more)

### Community 30 - "WMS Tile Proxy"
Cohesion: 0.13
Nodes (21): WMSLayer, _fetch_with_retry(), _find_dimension_values(), _last_n_time_steps(), _local_tag(), _parse_iso8601(), _parse_iso8601_duration(), Return the raw text of the <Dimension name="time"> for a given layer. (+13 more)

### Community 31 - "Landing Page Bootstrap"
Cohesion: 0.15
Nodes (22): effects, fallBack(), followScrollPlainly(), followScrollWithGsap(), gl, hudFigure, hudHeading, loadScript() (+14 more)

### Community 32 - "Sky View Factor (SVF)"
Cohesion: 0.13
Nodes (21): DigitalSurfaceModel, calculate_svf(), existing_svf(), horizon_shift_vector(), load_dsm(), Sky-view factor (SVF) from a Digital Surface Model, stored as an…, Sky-view factor of a surface model. height: 2D array of elevations in metres…, Elevation grid of a DigitalSurfaceModel row inside `bbox`, in the storage CRS.… (+13 more)

### Community 33 - "SOLWEIG Pipeline & Staleness"
Cohesion: 0.13
Nodes (21): _storage_box(), MeanRadiantTemperature, Mean Radiant Temperature (MRT) measurements, calculate(), device(), local_timezone(), _ndvi(), _progress() (+13 more)

### Community 34 - "New Units -> Land Cover"
Cohesion: 0.13
Nodes (19): _finalize_landcover(), Batch-import helpers shared by the file-upload and external-data importers. -…, _buffer_sql(), Land-cover overlay edits driven by other layers. urbanize_around() turns a…, Undo urbanize_around() for an editor building that moved or was deleted: every…, The 'urban fabric' class, matched case-insensitively like the PDOK BRT import's…, ST_Buffer of BUILDING_BUFFER_M metres: planar in RD New, through geography for…, percentage = polygon area / city area_km2 * 100 for the given rows. (+11 more)

### Community 35 - "Soil Infiltration (SCS-CN)"
Cohesion: 0.12
Nodes (18): LandCoverClasses, A soil unit of the Dutch soil map (Bodemkaart 1:50 000, BIS Nederland), stored…, SoilType, _area_sql(), ST_Area in m²: planar for a projected storage CRS (RD New), geography for a…, classify_soil_group(), curve_number(), infiltration_coefficient() (+10 more)

### Community 36 - "Example DB Dump/Load"
Cohesion: 0.19
Nodes (21): _check_target_db(), _connection_args(), _crosstwin_version(), _db_settings(), _django(), dump(), load(), main() (+13 more)

### Community 37 - "LST Command & Pipeline"
Cohesion: 0.15
Nodes (17): Smallest grid with corners on multiples of `resolution` that covers the extent., calculate_lst(), default_window(), grid_for(), LSTError, ndvi_layer(), RuntimeError, Grid over the part of the view the NDVI layers cover (LST is empty elsewhere). (+9 more)

### Community 38 - "Layer Cache Versioning"
Cohesion: 0.14
Nodes (19): bump_layer_version(), get_cache(), _label(), layer_version(), Versioned cache keys for data that only changes when rows are written. Every…, caches[alias], falling back to the default cache when the alias isn't…, Current cache version of a model's data. A missing version is seeded with the…, Invalidate every cached response built from these models' rows. (+11 more)

### Community 39 - "Population Forecast Chart"
Cohesion: 0.16
Nodes (19): band_d(), build_population_chart(), pts(), x_of(), y_of(), _fmt(), monotone_segments(), nice_step() (+11 more)

### Community 40 - "LST NDVI Inputs"
Cohesion: 0.14
Nodes (17): LandCoverRaster, ndvi_layers_in(), ndvi_mosaic(), _ndvi_queryset(), LST from Landsat 9 + CrossTwin's NDVI layer, stored as a LandSurfaceTemperature…, NDVI layers overlapping the view, newest first., Band 1 of a GDALRaster averaged onto `grid` (NaN outside it / at nodata)., NDVI on the grid; where layers overlap, the first (newest) one wins. (+9 more)

### Community 41 - "LST Map Tool Views"
Cohesion: 0.20
Nodes (18): BadRequest, _bbox(), _date(), _error(), _grid_json(), lst_calculate(), view(), lst_scenes() (+10 more)

### Community 42 - "Nature Models"
Cohesion: 0.15
Nodes (9): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, Tree, WaterBodies, WaterWaysLN (+1 more)

### Community 43 - "SVF DSM Window Planning"
Cohesion: 0.15
Nodes (19): _area(), _db_raster(), dsm_extent(), dsm_for_view(), _intersection(), plan(), ValueError, An expected failure the map tool shows as-is (no DSM, view too large...). (+11 more)

### Community 44 - "SVF Map Tool Views"
Cohesion: 0.19
Nodes (17): BadRequest, _bbox(), _dsm_json(), _error(), _existing_json(), _number(), _params(), require_GET (+9 more)

### Community 45 - "Raster to COG Export"
Cohesion: 0.15
Nodes (14): Command, BaseCommand, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), interpolate_raster(), Build a COG filename from whatever satellite/process metadata the raster model… (+6 more)

### Community 46 - "SOLWEIG Tool (JS)"
Cohesion: 0.30
Nodes (17): init(), calculate(), csrfToken(), duration(), fetchMet(), loadInfo(), open(), pause() (+9 more)

### Community 47 - "README & Project Concepts"
Cohesion: 0.15
Nodes (18): Landing stages (overview to what-if editing), CrossTwin README, DPSIR Framework (Driver-Pressure-State-Impact-Response), EPSG:28992 Amersfoort / RD New CRS, Example Data Package (crosstwin_example_data.zip), Viewport Loading of Large Layers (>=5000 features), Importer System (file upload + external catalog), Model Registry (MODEL/VECTOR/RASTER/WMS registries) (+10 more)

### Community 48 - "Landing Three.js Scene"
Cohesion: 0.21
Nodes (15): createLanding(), applyTier(), crossfadeTo(), dispose(), draw(), frame(), invalidate(), resize() (+7 more)

### Community 49 - "Map Page Templates"
Cohesion: 0.15
Nodes (14): mainMap.html (map page), Actions menu (drop-up: import, calculate, year), Legend stack (#legend-stack), LST tool card, dashboard_summary.html (population KPI card), population_panel.html (Curves-style forecast graph + stats), Population dock, Side panel (#panel-body HTMX target) (+6 more)

### Community 50 - "OpenStreetMap Importer"
Cohesion: 0.17
Nodes (9): OSMImporter, Import handler for OpenStreetMap through the Overpass API. The Overpass JSON is…, Overpass QL for `dataset` inside bbox [west, south, east, north] (WGS84)., Leading number of an OSM tag value: '12 m' -> 12.0, '7,5' -> 7.5, '40 ft' ->…, (Multi)polygon of a multipolygon relation from its member ways. A ring may be…, GeoJSON geometry of one Overpass element (out center or out geom)., Overpass elements -> GeoJSON features whose properties are the OSM tags plus…, OSM tags are strings ('12 m'); give numeric model fields a number, or drop the… (+1 more)

### Community 51 - "Map Init & 3D Buildings"
Cohesion: 0.22
Nodes (13): updateCityName(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, buildingColorForTool(), changeBasemap(), getSavedCameraState(), initializeUrbanTwinMap() (+5 more)

### Community 52 - "TODO & Housing Panel"
Cohesion: 0.17
Nodes (15): applyZone(), zoneStyle(), housing_indicators.html (Province Housing Dashboard), housing indicators_grid.html, Pipeline land take (greenfield vs infill), Housing Supply Coverage gauge (supply / demand units), Zoning & Land Value card (HILUCS shares), housing indicators_panel.html (+7 more)

### Community 53 - "DSM Building Patches"
Cohesion: 0.17
Nodes (13): apply_patches(), burn(), estimate_ground(), ground_grid(), patches_in(), Buildings -> DSM: map-editor building changes as an overlay on the DSM. A DSM…, Ground elevation on the grid of `height`: the DEM covering it (read on the…, Boolean mask of the cells whose centre lies in any of `geoms` (GEOS). (+5 more)

### Community 54 - "Map Editing (JS)"
Cohesion: 0.28
Nodes (13): _attachEditor(), _bindDrawEvents(), _cancelEdit(), _drawModeFor(), _featureUrl(), _hideOriginal(), _openEditorPanel(), _removeDrawControl() (+5 more)

### Community 55 - "LST Tool (JS)"
Cohesion: 0.33
Nodes (14): init(), calculate(), commonParams(), csrfToken(), findScenes(), open(), pct(), readJson() (+6 more)

### Community 56 - "External Import Map UI"
Cohesion: 0.15
Nodes (12): Catalog bbox_from (area-of-interest picker level), external_data.html (Import Public Data), clearBbox(), Import Selected click handler (POST start_external_import), initBboxMap(), loadPickerLevel(), pickerLevelFor(), setPickerLevel() (+4 more)

### Community 57 - "SOLWEIG Inputs"
Cohesion: 0.21
Nodes (12): _box(), LandCoverVector, _matches(), Any keyword at a word start of `name`: "road" must not match "broad-leaved…, build(), _footprints(), Inputs, landcover_grid() (+4 more)

### Community 58 - "KNMI Raster Importer"
Cohesion: 0.20
Nodes (10): get_raster_field_name(), Find the name of the RasterField on a model., datetime, KNMIImporter, load_raster_into_target_model(), KNMI Data Platform (Open Data API v1). Flow: list the newest file of a dataset…, UTC datetime encoded in a KNMI file name, or None if it has none., Convert a downloaded KNMI grid to a single-band float32 GeoTIFF in… (+2 more)

### Community 59 - "Map Config (Config.js)"
Cohesion: 0.15
Nodes (13): availableLayers, BASEMAPS, BUILDING_COLOR_BY_TOOL, CONFIG, HIDES_3D_BUILDINGS_APPS, HIDES_3D_BUILDINGS_KEYS, layerVisibility, loadedLayers (+5 more)

### Community 60 - "Landing Scroll Stages"
Cohesion: 0.25
Nodes (13): cameraAt(), CAMERAS, fitFactor(), HOLD_END, LAST_STAGE, layersAt(), locate(), mix() (+5 more)

### Community 61 - "Guided Tour & Actions Menu"
Cohesion: 0.20
Nodes (11): actionsMenu, actionsMenuBtn, ADMIN_PANEL_TOOLS, clearTourHighlight(), endTour(), findActiveAdminTool(), positionActionsMenu(), refreshActivePanel() (+3 more)

### Community 62 - "Map URLs & Dashboard Summary"
Cohesion: 0.14
Nodes (11): Like <int:>, but also matches negative ids (user-created Buildings, see…, SignedIntConverter, admin_unit_at_point(), dashboard_summary(), landing_view(), map_view(), Display the map page., Display the landing page. Static content: no database queries. (+3 more)

### Community 63 - "PostgreSQL Health Check"
Cohesion: 0.32
Nodes (13): _connect(), _create_extensions_help(), _diagnose_connection_error(), _install_postgis_help(), _install_postgres_help(), main(), _postgres_binaries(), Check that PostgreSQL is reachable with the .env settings and has PostGIS. Run… (+5 more)

### Community 64 - "Humidity Raster Interpolation"
Cohesion: 0.15
Nodes (7): HumidityRaster, Determine bounds for interpolation, Convert extent tuple to Polygon, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child…, Generic interpolation method - works for all child classes, Interpolated relative humidity raster layer

### Community 65 - "Base & Built-up Templates"
Cohesion: 0.18
Nodes (11): builtup_indicators.html (standalone dashboard), builtup indicators_grid.html, Built-up Coverage / FAR card, Park Area per Inhabitant card (WHO 9/50 m2), builtup indicators_panel.html (HTMX side panel), Additional Park Area slider (green_added_ha), Indicator Dashboard Three-Layer Pattern, base.html (site shell) (+3 more)

### Community 66 - "Heat Dashboard Templates"
Cohesion: 0.21
Nodes (10): applyZone(), zoneStyle(), initGauges() (global), _info_btn.html (reusable ? helper button), _info_popover.html (shared popover + delegated script), partials/_info_btn.html, Thermal comfort indices (LST, PET, UTCI, WBGT, SVF, SUHII), heat_indicators.html (Urban Heat Dashboard) (+2 more)

### Community 67 - "Map Settings Panel (JS)"
Cohesion: 0.23
Nodes (11): applyEditable(), applyStyle(), catalogEntry(), init(), preview(), readdLayer(), map_settings.html (Editable layers / Styles tabs), settings_editable_row.html (editable layer toggle) (+3 more)

### Community 68 - "SVF Tool (JS)"
Cohesion: 0.33
Nodes (12): init(), calculate(), csrfToken(), loadInfo(), open(), params(), readJson(), refreshButton() (+4 more)

### Community 69 - "App Version Info"
Cohesion: 0.21
Nodes (8): CoreConfig, AppConfig, _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. Counts half the commits:…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 70 - "Water Dashboard Templates"
Cohesion: 0.24
Nodes (11): applyRain(), applyZone(), rainStyle(), zoneStyle(), watersupply indicators_grid.html, Infiltration card (SCS Curve Number), Non-Revenue Water card (apparent/real losses, ILI), Supply Security gauge / Service Time (+3 more)

### Community 71 - "Water Extraction"
Cohesion: 0.18
Nodes (6): EnvironmentalCosts, The most recent cost record (the model has no province/year), or None., ExtractionWater, Database expression for a well's extracted volume in m3/day, the one definition…, DAG edges: Available_FW -> Total_Extraction Total_Extraction ->…, Set productionDay/YR (Mm3) and costDay/YR (EUR) from the active wells of the…

### Community 72 - "LST Grid"
Cohesion: 0.17
Nodes (6): Grid, The one raster grid every LST input is put on before the equations run., Affine in Earth Engine's order: [xScale, xShear, xOffset, yShear, yScale,…, [west, south, east, north] in EPSG:4326, for filtering image collections., North-up grid: (x0, y0) is the top-left corner, cells are `resolution` m square., LSTResult

### Community 73 - "Thermal Comfort Runs"
Cohesion: 0.17
Nodes (11): One SOLWEIG thermal-comfort calculation for a map view and hour…, ThermalComfortRun, plan(), ValueError, An expected failure the map tool shows as-is (no DSM, view too large...)., What a run over `view` (storage CRS) would read: the DSM, the covered view, the…, SolweigError, execute() (+3 more)

### Community 74 - "Interpolated Raster Base"
Cohesion: 0.20
Nodes (6): InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Get measurements within time window for a specific field Args:…, Convenience method to generate raster for a Province Args: Province: Province…, Override in child classes to specify which measurement field to use, Override in child classes to specify metadata keys Returns tuple: (min_key,…

### Community 75 - "Weather Raster Signals"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 76 - "Bulk Import Writer"
Cohesion: 0.27
Nodes (4): BulkWriter, Collects rows and writes them `batch_size` at a time. With a unique field, rows…, A writer when `Model` can safely be bulk-written, otherwise None (use the row…, Write what is left, replay the skipped signals and invalidate the layer cache.

### Community 77 - "Spatial Parent Index"
Cohesion: 0.22
Nodes (4): Point-in-polygon lookup against a fixed set of parent rows. Each parent's…, Load only what the lookup needs: pk, geom and any attributes read off the…, The parent containing `geom`'s representative point, or None., SpatialParentIndex

### Community 78 - "Admin Unit Point Lookup"
Cohesion: 0.25
Nodes (8): Built once per process: creating a GDAL/PROJ transformation is the slow part of…, Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), _wgs84_to_storage(), population_panel(), The administrative unit the population views talk about, as (level, unit,…, HTML for the bottom dock opened from the Population pill: today's population,…, _resolve_summary_unit()

### Community 79 - "Zoning Areas"
Cohesion: 0.32
Nodes (3): bag_usage_labels(), BAG gebruiksdoel as a list of labels (Building.BAG_USAGE_FUNCTIONS). WFS…, ZoningArea

### Community 80 - "Architecture Diagram Export"
Cohesion: 0.43
Nodes (7): browser(), main(), page(), Export docs/architecture/latest/*.svg to PNG and PDF with headless Chrome/Edge.…, One page per SVG, each page sized to its diagram (named @page rules)., run(), size()

### Community 81 - "Non-Revenue Water"
Cohesion: 0.25
Nodes (4): LossesChoices, LossesTypes, NonRevenueWater, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 82 - "Wind & Weather Stations"
Cohesion: 0.25
Nodes (4): Meta, Interpolated wind speed raster layer, WeatherStation, WindSpeedRaster

### Community 83 - "Layer & Tree Styles"
Cohesion: 0.33
Nodes (5): Map styling of the vector layers: Mapbox GL style layers, legend entries and…, build_tree_style(), Map style of nature.Tree: green dots when zoomed out, a 3D glTF tree per point…, style_layers for nature.Tree. The circle layer comes first: it is the click…, _uniform()

### Community 84 - "DB Stats Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Show the most expensive SQL statements recorded by pg_stat_statements…

### Community 86 - "CBS Importer"
Cohesion: 0.33
Nodes (4): CBSImporter, Import handler for CBS StatLine OData datasets., Fetch tabular data from CBS OData API and import to Django model. Args:…, Fetch column definitions and units for a CBS table. Useful for building field…

### Community 87 - "SOLWEIG UMEP Writers"
Cohesion: 0.33
Nodes (6): Write the arrays as SOLWEIG's single tile 0_0 (<dir>/<Name>/<Name>_0_0.tif).…, write_tiles(), The UMEP met file of one run: the hour before and the analysed hour, both with…, write_umep(), Run SOLWEIG-GPU on the inputs; returns (tmrt, utci) of the analysed hour on the…, run_solweig()

### Community 88 - "Upload Templates"
Cohesion: 0.50
Nodes (5): model_selector.js initModelSelector, FieldMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 89 - "App Icon 512"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 90 - "HILUCS Land Use Codes"
Cohesion: 0.40
Nodes (5): _hilucs_lookup(), hilucs_lookup(), parse_hilucs_href(), (code, label) of a HILUCS URI, or None if it is not one. The label is spelled…, __fk_lookup__ parser for HILUCS URIs (importer/external_data.py): returns…

### Community 91 - "Watersheds"
Cohesion: 0.40
Nodes (3): active_wells_with_watershed(), Active wells annotated with `ws`, the id of the watershed their water belongs…, Watershed

### Community 95 - "App Icon 192"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 98 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 100 - "Style Suggestion Notes"
Cohesion: 0.50
Nodes (4): Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono)

### Community 106 - "Apple Touch Icon"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 107 - "Favicon 16"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 108 - "Favicon 32"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

## Knowledge Gaps
- **96 isolated node(s):** `Scenario`, `availableLayers`, `loadedLayers`, `layerVisibility`, `CONFIG` (+91 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 877 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `feature_form.html (map feature editor)` connect `Map Editing Backend` to `Map Page Templates`, `Map Editing (JS)`?**
  _High betweenness centrality (0.218) - this node is a cross-community bridge._
- **Why does `Side panel (#panel-body HTMX target)` connect `Map Page Templates` to `Map Editing Backend`, `TODO & Housing Panel`, `Water Dashboard Templates`?**
  _High betweenness centrality (0.168) - this node is a cross-community bridge._
- **Why does `City` connect `Administrative Hierarchy & Population` to `New Units -> Land Cover`, `Housing Indicators`, `Water Supply Indicators`, `Built-up Indicators & Models`, `File Upload Importer`, `LST Command & Pipeline`, `Water Supply Signal Cascade`, `External Feature Import`, `Nature Models`, `Water Supply Models`, `Building Edit Signals`, `Housing Demand Signals`, `CBS Importer`, `Water Demand Chain`, `KNMI Raster Importer`, `Thermal Comfort Raster Models`?**
  _High betweenness centrality (0.156) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Province` (e.g. with `ProvinceAdmin` and `cities_within()`) actually correct?**
  _`Province` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `neighborhoods_within()` (e.g. with `City` and `District`) actually correct?**
  _`neighborhoods_within()` has 4 INFERRED edges - model-reasoned connections that need verification._