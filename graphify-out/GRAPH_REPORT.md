# Graph Report - CrossTwin  (2026-11-24)

## Corpus Check
- 247 files · ~277,059 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3390 nodes · 6606 edges · 221 communities (154 shown, 54 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 500 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Builtup Signals and Canyons
- Water Supply Models and Signals
- Map Layers and Events
- PhysicalEnv Signals and DSM
- Map Views and Charts
- SOLWEIG Meteorology Inputs
- Map Editing Backup
- Green Spaces and Heat Indicators
- Water Supply Indicators
- Water Supply Chain Equations
- Landing City Builder
- Live Weather Service
- Core Console and Views
- Urban Heat Raster Models
- Soil Infiltration (SCS)
- Administrative Units
- Land Cover and Albedo
- Urbanisation Grid Refresh
- Building Heights and SVF Inputs
- SOLWEIG Views
- Housing Signals and Property
- PhysicalEnv Admin and Models
- Edited DSM COG
- Architecture Diagrams Tooling
- LST Grid
- Urbanisation Dashboard and What-if
- External Data Import Core
- SOLWEIG Pipeline
- Editable Layer Settings
- External Catalog and Console
- Housing Indicators
- Landing Plan Layout
- Spatial Parent Index
- Housing Models and Admin
- Map Style Overrides
- LST SMW Equations
- Builtup Indicators
- External Data Enrichment
- LST Pipeline and NDVI
- Landing Scroll Wiring
- Import Page UI
- Map Page Templates
- Population Projections
- File Upload Importer
- PhysicalEnv Views
- Example DB Packaging
- OSM Importer
- LST Earth Engine Inputs
- Indicator Help and Water JS
- Raster COG Export
- KNMI Importer
- Map Edit Journal Signals
- LST Views
- Thermal Comfort Tool JS
- Raster Styles
- Nature Models
- Interpolated Weather Rasters
- Map Initialisation
- Housing Chain Equations
- Population Cascade Signals
- Layer Cache Versioning
- Landing Scene Renderer
- Map Calculation Cards
- Map Editor JS
- Housing Panel JS
- LST Tool JS
- Bulk Import Finalizers
- Map Settings Models
- DSM Patch Overlay
- Heat Panel JS
- Landing Camera Stages
- Weather Pill
- Model Registry and Upload Form
- Map Frontend Config
- Map Page Wiring
- SVF Tool JS
- Postgres Check Tool
- Degree of Urbanisation Views
- Builtup Models
- Landing Page Docs
- Info Popover
- Population Dock Panels
- SOLWEIG Raster Inputs
- Weather Raster Views
- DEGURBA Classifier
- Builtup Indicator Cards
- Degree of Urbanisation Tool JS
- Sky View Factor
- Meteorology Model
- Bulk Writer
- Feature Editor Form
- Green Area Land Cover
- Population Projection Model
- Background Worker
- Earth Engine Auth
- Builtup Dashboard JS
- Console Feed JS
- Map Settings JS
- Indicator Help Tag
- Version Labels
- HILUCS Land Use Codes
- Architecture Export
- Non-Revenue Water
- Street Canyon Equations
- GEE Importer
- Layer and Tree Styles
- Fill Tree Heights Command
- DB Stats Command
- Query Stats Middleware
- Deferred Cascades
- Land Cover Styles
- Environmental Costs
- Supply Security Equations
- Upload Templates
- App Icon 512
- Energy Models
- Importer Geometry Utils
- Humidity Raster
- Precipitation Raster
- Temperature Raster
- Admin Unit Point Lookup
- App Icon 192
- Django Settings
- Housing App Config
- CBS Importer
- FK Lookup Resolution
- Manage Entry Point
- Style Suggestions
- Water Supply App Config
- Weather App Config
- Geo Area Helper
- Apple Touch Icon
- Favicon 16
- Favicon 32
- Energy App Config
- Importer App Config
- Nature App Config
- Request Profiler
- Urban Heat App Config
- Admin Unit Resolver
- City Name JS
- Draggable Overlays
- Model Selector JS
- ASGI Config
- WSGI Config
- Import Templates
- Setup and Example Data
- Housing Affordability Gaps
- Household Size Edges
- Water Loss Edges
- Province Raster Generation
- Core Admin
- HTTP Method Decorator
- Core Models
- URL Config
- Energy Views
- Importer Admin
- Importer Models
- Explore Filters
- MainMap Admin
- Feature Form Template
- Nature Views
- Project Package
- PostGIS Test Runner
- GET Decorator
- Style Suggestion Doc
- TiTiler App
- Infiltration Edge
- PET to NBS Gap
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 182
- Community 183
- Community 184
- Community 185
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 195
- Community 197
- Community 200
- Community 201
- Community 205
- Community 206
- Community 208
- Community 210
- Community 211
- Community 212
- Community 213
- Community 214
- Community 215
- Community 216
- Community 217
- Community 218
- Community 219
- Community 220

## God Nodes (most connected - your core abstractions)
1. `Building` - 44 edges
2. `LandCoverVector` - 34 edges
3. `Property` - 29 edges
4. `init()` - 28 edges
5. `init()` - 28 edges
6. `City` - 26 edges
7. `buildCity()` - 23 edges
8. `Neighborhood` - 21 edges
9. `import_dataset()` - 21 edges
10. `is_extrapolated()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `neighborhoods_at()` --uses--> `Neighborhood`  [INFERRED]
  builtup/calculations/urbanisation.py → administrative/models.py
- `Importer system (file upload + external catalog)` --conceptually_related_to--> `earthengine-api / openeo`  [INFERRED]
  README.md → requirements.txt
- `New_Green_Area -> LandCover (editor green spaces)` --semantically_similar_to--> `Urban-fabric buffer around editor buildings (urbanize_around / release_ring)`  [INFERRED] [semantically similar]
  TODO.md → README.md
- `city_factors()` --uses--> `City`  [INFERRED]
  builtup/calculations/urbanisation.py → administrative/models.py
- `mirror_city_rates()` --uses--> `City`  [INFERRED]
  builtup/calculations/urbanisation.py → administrative/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Climate scenario flow** — weather_templates_weather_partials_climate_panel_climate_scenarios_panel, mainmap_templates_mainmap_partials_climate_effects_climate_effects_table, mainmap_templates_mainmap_partials_climate_run_climate_scenario_run_partial, mainmap_templates_mainmap_partials_climate_run_list_stored_climate_runs_list [EXTRACTED 0.85]
- **Indicator side panels** — builtup_templates_builtup_partials_indicators_panel_built_up_indicators_panel, housing_templates_housing_partials_indicators_panel_housing_indicators_panel, urban_heat_templates_urban_heat_partials_indicators_panel_urban_heat_indicators_panel, watersupply_templates_watersupply_partials_indicators_panel_water_supply_indicators_panel [EXTRACTED 0.85]
- **Info help popover flow** — templates_partials_info_btn, core_indicator_help, core_static_js_info_popover, templates_indicators_base [EXTRACTED 1.00]
- **Map editing UI (feature form, backup bar, Editing.js, core.editing)** — mainmap_templates_mainmap_partials_feature_form, core_static_js_editing, core_editing [EXTRACTED 1.00]
- **Map settings panel (editable layers + style overrides)** — mainmap_templates_mainmap_settings_card, mainmap_templates_mainmap_partials_map_settings, mainmap_templates_mainmap_partials_settings_editable_row, mainmap_templates_mainmap_partials_settings_style_form, core_static_js_mapsettings [EXTRACTED 1.00]
- **CrossTwin icon composition: physical city, digital wireframe, orbit ring** — core_static_ico_android_chrome_512x512_isometric_city_block, core_static_ico_android_chrome_512x512_cyan_wireframe_grid, core_static_ico_android_chrome_512x512_orbit_ring [INFERRED 0.85]
- **Domain indicator side panels sharing grid + JS pattern** — readme_indicator_dashboard_pattern [INFERRED 0.85]
- **Landing fallback sketch generation flow** — core_static_js_landing_plan, tools_landing_fallback_svg, core_static_img_landing_city_blueprint, mainmap_templates_mainmap_landing [INFERRED 0.85]

## Communities (221 total, 54 thin omitted)

### Community 0 - "Builtup Signals and Canyons"
Cohesion: 0.04
Nodes (100): The population cascade uses queryset.update(), which never fires…, neighborhoods_near(), neighborhoods_with_residents(), The subset of the given neighborhoods that hold at least one property with…, Neighborhoods holding a property within distance_m of any of the geometries., AvailableFreshWater, OPEX, SupplySecurity (+92 more)

### Community 1 - "Water Supply Models and Signals"
Cohesion: 0.06
Nodes (73): is_editor_change(), is_restoring(), True inside a map-editor save or delete. Receivers that must react to a user's…, True while restore_backup() runs. Receivers that undo an edit's side effects on…, building_height(), Record an editor change of one tree or forest (DSMVegetationPatch). source:…, Record an editor change of one building. before: its footprint before this edit…, Height above ground of a builtup.Building: height_m, else floors x… (+65 more)

### Community 2 - "Map Layers and Events"
Cohesion: 0.06
Nodes (57): BuiltupConfig, AppConfig, The urban canyon of one street: height-to-width ratio H/W. H = mean of the…, Set every field from the street and its street_inputs() row…, StreetCanyon, building_canyon_deleted(), building_canyon_presave(), building_canyon_saved() (+49 more)

### Community 3 - "PhysicalEnv Signals and DSM"
Cohesion: 0.06
Nodes (56): KNMI'23 scenario of the Scenarios panel (`?climate=2050_Hd`); the current…, demand_m3_d(), Daily residential water demand in m3/day: L/person/day / 1000 * persons., Daily total water demand in m3/day: residential demand x the small business…, residential_demand_m3_d(), calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio() (+48 more)

### Community 4 - "Map Views and Charts"
Cohesion: 0.05
Nodes (51): datetime, _era5_day(), era5_day_from_values(), era5_from_values(), era5_hourly(), knmi_day_values(), _knmi_hour(), knmi_hourly() (+43 more)

### Community 5 - "SOLWEIG Meteorology Inputs"
Cohesion: 0.06
Nodes (53): build_population_stats(), Numbers shown next to the graph: today, the selected year, the change and the…, admin_unit_at_point(), available_layers(), building_mask(), _building_mask_sql(), climate_effect_rows(), dashboard_summary() (+45 more)

### Community 6 - "Map Editing Backup"
Cohesion: 0.06
Nodes (43): atomic, fit_geometry_type(), get_area(), Convert between single and multi geometries to match the target field: a Point…, Returns the area in square kilometers., GeoUploadForm, get_target_model_choices(), MappingForm (+35 more)

### Community 7 - "Green Spaces and Heat Indicators"
Cohesion: 0.06
Nodes (34): EnvironmentalCosts, The most recent cost record (the model has no province/year), or None., WMSLayerAdmin, Production as a percentage of demand (0 when there is no demand)., Hours of supply per day: full service when production covers demand, otherwise…, service_time_hours(), supply_security_pct(), active_wells_with_watershed() (+26 more)

### Community 8 - "Water Supply Indicators"
Cohesion: 0.06
Nodes (40): coverage_pct(), ili(), The population -> consumption -> demand -> supply security -> service time…, part / total in percent, one decimal (0 without a total)., Share of the water users inside the network's service area, in percent (0…, Unavoidable Annual Real Losses in m³/day (IWA, Lambert et al. 1999): (18 Lm +…, Infrastructure Leakage Index = CARL / UARL (two decimals; None without UARL).…, Whether the system is large and dense enough for the UARL equation. (+32 more)

### Community 9 - "Water Supply Chain Equations"
Cohesion: 0.07
Nodes (45): layout_metrics(), Dwellings in a building of that gross floor area: whole units, at least one., Spacematrix-style metrics of a generated layout (areas in m², lengths in m)., units_in(), as_multipolygon(), _block_depth(), _bowed(), _concentric_streets() (+37 more)

### Community 10 - "Landing City Builder"
Cohesion: 0.08
Nodes (37): change_tone(), _bad(), climate_run_create(), climate_run_delete(), climate_run_detail(), climate_run_heat(), climate_run_list(), climate_run_recalculate() (+29 more)

### Community 11 - "Live Weather Service"
Cohesion: 0.07
Nodes (40): MultiPolygon, NamedTuple, Area-weighted albedo of an editor building's urban-fabric ring: the footprint…, ring_albedo(), _buffer_sql(), convert_area(), green_area(), _green_area_class() (+32 more)

### Community 12 - "Core Console and Views"
Cohesion: 0.08
Nodes (37): Outdoor WBGT (°C) per cell from the met (scalars), the 1.2 m wind and SOLWEIG's…, wbgt_outdoor_c(), pet_kwargs(), The pet_steady keyword arguments of a stored person (None/{} = STANDARD_PERSON)., One SOLWEIG thermal-comfort calculation for a map view and hour…, DAG edges: Climate_Change -> Meteorology -> Tmrt, UTCI, PET, WBGT met_scenario…, ThermalComfortRun, calculate() (+29 more)

### Community 13 - "Urban Heat Raster Models"
Cohesion: 0.10
Nodes (35): alongPath(), buildCity(), update(), geometryFrom(), HEAT_STOPS, heatColor(), heatMaterial(), HOUSE_COLORS (+27 more)

### Community 14 - "Soil Infiltration (SCS)"
Cohesion: 0.09
Nodes (36): population_params(), (scenario, growth_adjust_pct) from a request's query parameters `pop_scenario`…, calculate_affordability(), calculate_dwellings(), calculate_house_price_index(), calculate_household_size(), calculate_mortgage_indicators(), calculate_new_units() (+28 more)

### Community 15 - "Administrative Units"
Cohesion: 0.07
Nodes (27): HILUCSLandUseAdmin, LandCoverClassesAdmin, SoilTypeAdmin, SurfaceMaterialPropertiesAdmin, DigitalElevationModel, DigitalElevationModelWMS, DigitalSurfaceModelWMS, DSMVegetationPatch (+19 more)

### Community 16 - "Land Cover and Albedo"
Cohesion: 0.07
Nodes (30): builtup_indicators.html (standalone dashboard), Help texts behind the "?" buttons of the indicator dashboards and side panels.…, anyTouched(), applyZone(), resetWeather(), showValue(), syncResetButton(), weatherInputs() (+22 more)

### Community 17 - "Urbanisation Grid Refresh"
Cohesion: 0.09
Nodes (35): Property, Proxy onto builtup.Property limited to dwellings (BAG woonfunctie), its own map…, ResidentialProperty, city_population_cascaded(), city_saved(), climate_run_saved(), deferred_housing_refresh(), _dwellings_of_city() (+27 more)

### Community 18 - "Building Heights and SVF Inputs"
Cohesion: 0.05
Nodes (38): Built-up indicators grid, Indicator cards, Info help: builtup.age, coverage, degurba, facilities, streets, stock, Additional park area what-if slider, Built-up indicators panel, Housing indicators grid, Info help: housing.affordability, hpi, mortgage, zoning, stress, Average persons per home what-if slider (+30 more)

### Community 19 - "SOLWEIG Views"
Cohesion: 0.10
Nodes (37): active_backup(), backup(), _backup_bar(), backup_discard(), backup_restore(), _build_form(), _check_constraints(), editable_keys() (+29 more)

### Community 20 - "Housing Signals and Property"
Cohesion: 0.13
Nodes (37): _heat_inputs(), (area, observed met dict) of the heat model: the SOLWEIG plan of the view and…, (west, south, east, north) in degrees -> (minx, miny, maxx, maxy) in the…, wgs84_to_storage(), centre(), Results that the editor's building changes made stale inside `view` (storage…, stale_results(), BadRequest (+29 more)

### Community 21 - "PhysicalEnv Admin and Models"
Cohesion: 0.08
Nodes (35): absorbed_radiation_w_m2(), apparent_temperature_c(), clamp_weather(), globe_temperature_c(), Heat stress from the weather alone, for the heat panel's weather what-if. Pure…, Psychrometric wet-bulb temperature (°C), Stull (2011); scalars or numpy arrays., Globe temperature (°C) that gives `tmrt_c` (ISO 7726 forced convection), per…, Q of the apparent temperature: shortwave absorbed per unit body surface. (+27 more)

### Community 22 - "Edited DSM COG"
Cohesion: 0.10
Nodes (36): _adds_nothing(), apply_to_daily_rain(), apply_to_day_values(), apply_to_et(), apply_to_weather(), change_tone(), deltas(), design_rain_mm() (+28 more)

### Community 23 - "Architecture Diagrams Tooling"
Cohesion: 0.14
Nodes (32): allocate(), _background(), _background_job(), _bump(), _cells_over(), _class_population_sql(), classify_grid(), _collect() (+24 more)

### Community 24 - "LST Grid"
Cohesion: 0.10
Nodes (26): curve_number(), group_rate_mm_h(), impervious_fraction(), infiltration_coefficient(), is_drained(), _matches(), scs_runoff_mm(), soil_landcover_composition() (+18 more)

### Community 25 - "Urbanisation Dashboard and What-if"
Cohesion: 0.08
Nodes (18): calculate_supply_demand(), Housing supply vs demand for a city and year. DAG edges: Total_Population ->…, CentralBankPolicy, CreditSupplyConditions, HousePriceIndex, HousingAffordability, HousingSupplyDemand, Meta (+10 more)

### Community 26 - "External Data Import Core"
Cohesion: 0.09
Nodes (29): build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…, Map styling of the vector layers: Mapbox GL style layers, legend entries and…, apply_raster_override(), apply_vector_override() (+21 more)

### Community 27 - "SOLWEIG Pipeline"
Cohesion: 0.11
Nodes (31): calculate_svf(), _db_raster(), existing_svf(), horizon_shift_vector(), _intersection(), plan(), ValueError, Sky-view factor (SVF) from a Digital Surface Model, stored as an… (+23 more)

### Community 28 - "Editable Layer Settings"
Cohesion: 0.10
Nodes (19): import_dataset(), ImportResult, PDOKImporter, Import handler for PDOK datasets - imports directly to Django models., Split [min_v, max_v] into evenly-sized segments, each no larger than…, Fetch raster data from PDOK WCS service, tiling the request when the area would…, Register a WMS layer by creating/updating its row in the target WMS model. This…, Fetch tabular data from CBS OData API and import to Django model. Args:… (+11 more)

### Community 29 - "External Catalog and Console"
Cohesion: 0.11
Nodes (29): enable_blocker(), Why the layer `key` may not be switched on, or None when it may. A model whose…, _colormaps(), _editable_row(), _forbidden(), _layer_name(), map_settings(), _parse_target() (+21 more)

### Community 30 - "Housing Indicators"
Cohesion: 0.10
Nodes (21): _raster_statistics(), Band-1 min/max of the stored raster itself (GDAL skips nodata cells). The…, apps(), Diagram, editing(), importer(), infiltration(), on_demand() (+13 more)

### Community 31 - "Landing Plan Layout"
Cohesion: 0.09
Nodes (28): calculate_canyon_aspect(), calculate_green_area(), calculate_nbs_coverage(), calculate_urban_morphology(), calculate_vegetation_coverage(), classify_pet(), classify_utci(), classify_wbgt() (+20 more)

### Community 32 - "Spatial Parent Index"
Cohesion: 0.08
Nodes (19): CoreConfig, AppConfig, add(), clear(), FeedHandler, install(), NotDjango, Console feed: the server's own progress lines, shown under the map loader. The… (+11 more)

### Community 33 - "Housing Models and Admin"
Cohesion: 0.10
Nodes (19): _delete_heat_outputs(), The run's SOLWEIG runs and their rasters (COG files go with the post_delete…, MeanRadiantTemperature, _measurement_label(), Meta, NeighborhoodHeat, PET, Wet Bulb Globe Temperature (WBGT) - heat-stress measure combining air… (+11 more)

### Community 34 - "Map Style Overrides"
Cohesion: 0.10
Nodes (21): Grid, Smallest grid with corners on multiples of `resolution` that covers the extent., Affine in Earth Engine's order: [xScale, xShear, xOffset, yShear, yScale,…, [west, south, east, north] in EPSG:4326, for filtering image collections., North-up grid: (x0, y0) is the top-left corner, cells are `resolution` m square., grid_for(), LSTError, ndvi_layer() (+13 more)

### Community 35 - "LST SMW Equations"
Cohesion: 0.19
Nodes (28): init(), afterStore(), blockingReason(), clearLayers(), close(), commit(), editableOutline(), ensureLayers() (+20 more)

### Community 36 - "Builtup Indicators"
Cohesion: 0.12
Nodes (25): ADMIN_PANEL_TOOLS, clearTourHighlight(), CLIMATE_HORIZONS, CLIMATE_PUBLISHED, climateChipLabel(), climateKey(), endTour(), findActiveAdminTool() (+17 more)

### Community 37 - "External Data Enrichment"
Cohesion: 0.21
Nodes (27): init(), calculate(), calculateScenario(), checkedGarments(), csrfToken(), duration(), fetchMet(), fillOptions() (+19 more)

### Community 38 - "LST Pipeline and NDVI"
Cohesion: 0.09
Nodes (20): Yearly recharge of a fresh-water source in Mm3/year: the depth of water that…, Yearly recharge depth (cm/yr) of an area from a year of daily rain, a year's…, The yearly water balance behind recharge_depth_cm_yr, in mm over the area:…, yearly_water_balance_mm of a station year (`balance` from…, recharge_depth_cm_yr(), recharge_Mm3_yr(), scenario_water_balance(), yearly_water_balance_mm() (+12 more)

### Community 39 - "Landing Scroll Wiring"
Cohesion: 0.14
Nodes (25): calculate_building_age(), calculate_building_mix(), calculate_building_stock(), calculate_facilities(), calculate_green_space(), calculate_street_network(), _pct(), Distribution of construction years over the Dutch typology periods. DAG edges:… (+17 more)

### Community 40 - "Import Page UI"
Cohesion: 0.14
Nodes (26): add3DBuildingEdges(), add3DBuildings(), addBuildingMask(), addExternalLayers(), ADMIN_LEVELS, bindBuildingMaskEvents(), BUILDING_EDGE_LAYER_IDS, buildingColorForTool() (+18 more)

### Community 41 - "Map Page Templates"
Cohesion: 0.11
Nodes (25): _fill_tree_heights(), _finalize_landcover(), _finalize_soil(), _mark_heat_input(), Batch-import helpers shared by the file-upload and external-data importers. -…, Replays watersupply's soil/land-cover receivers: one extent for the whole batch., Measures the height of bulk-written trees that have none from the DSM (it…, _refresh_freshwater_over() (+17 more)

### Community 42 - "Population Projections"
Cohesion: 0.13
Nodes (25): _fill(), fill_from_dsm(), fill_under_dsm(), footprint_heights(), _label(), Building heights from the DSM, for buildings whose source gives none. BAG…, fill_from_dsm's work; returns the buildings that got a height., Height above ground of each footprint on one grid, or None. surface, ground:… (+17 more)

### Community 43 - "File Upload Importer"
Cohesion: 0.09
Nodes (21): Console progress lines for the importers (upload wizard, external import), so…, One console line. Forced to ASCII: a character the Windows cp1252 console can't…, say(), get_catalog_grouped(), _kea_building(), _kea_neighborhood(), Mapping for a per-buurt KEA layer: one row per stored neighborhood, keyed on…, Return the catalog grouped by category. Structure: { category: [datasets] }… (+13 more)

### Community 44 - "PhysicalEnv Views"
Cohesion: 0.11
Nodes (25): _background(), cog_window(), edited_cog_name(), enqueue(), _job(), _patch_extents(), patch_window(), Buildings -> DSM, Vegetation_Coverage -> DSM: the editor's patches written into… (+17 more)

### Community 45 - "Example DB Packaging"
Cohesion: 0.11
Nodes (23): WMSLayer, _fetch_with_retry(), _find_dimension_values(), _last_n_time_steps(), live_weather(), _local_tag(), _parse_iso8601(), _parse_iso8601_duration() (+15 more)

### Community 46 - "OSM Importer"
Cohesion: 0.18
Nodes (19): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, cities_within(), city_of(), neighborhoods_within(), province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any… (+11 more)

### Community 47 - "LST Earth Engine Inputs"
Cohesion: 0.12
Nodes (25): is_extrapolated(), population_curve(), projection_years(), Sorted years for which projections exist for the cities behind `unit`., True when the population of `unit` in `year` is not a published CBS value but…, [{'year', 'population'}, ...] over every projected year; [] if none imported., band_d(), build_population_chart() (+17 more)

### Community 48 - "Indicator Help and Water JS"
Cohesion: 0.12
Nodes (15): _sql(), street_inputs(), streets_near(), Building, BuildingEnergyLabel, _CurrentCells, _LocalCells, Meta (+7 more)

### Community 49 - "Raster COG Export"
Cohesion: 0.17
Nodes (22): city_blueprint.svg (landing no-WebGL city sketch), blueprintSegments(), boundaries(), buildPlan(), canalX(), circleLine(), crossing(), inDisc() (+14 more)

### Community 50 - "KNMI Importer"
Cohesion: 0.09
Nodes (21): Exception, CBSImporter, default_wms_legend_url(), _enrich_rows(), ensure_multipolygon(), _heights_after_dsm(), _ImportBlocked, _legend_url_from_capabilities() (+13 more)

### Community 51 - "Map Edit Journal Signals"
Cohesion: 0.12
Nodes (23): Constants of the Statistical Mono-Window (SMW) LST algorithm for Landsat 8/9.…, apply_qa_emissivity(), bare_ground_emissivity(), _bit_set(), cloud_mask(), fractional_vegetation_cover(), interpolate_tpw(), land_surface_temperature() (+15 more)

### Community 52 - "LST Views"
Cohesion: 0.12
Nodes (20): build_model_registry(), The queryset with its RasterField columns deferred. The map reads raster rows…, Build MODEL_REGISTRY dynamically from specified apps., without_raster_data(), _cog_version(), console_feed(), displayed_cog_path(), get_raster_info() (+12 more)

### Community 53 - "Thermal Comfort Tool JS"
Cohesion: 0.12
Nodes (19): LandCoverRaster, The one raster grid every LST input is put on before the equations run., calculate_lst(), default_window(), LSTResult, ndvi_mosaic(), LST from Landsat 9 + CrossTwin's NDVI layer, stored as a LandSurfaceTemperature…, Band 1 of a GDALRaster averaged onto `grid` (NaN outside it / at nodata). (+11 more)

### Community 54 - "Raster Styles"
Cohesion: 0.18
Nodes (23): _check_target_db(), _clear_user_references(), _connection_args(), _crosstwin_version(), _db_settings(), _django(), dump(), load() (+15 more)

### Community 55 - "Nature Models"
Cohesion: 0.16
Nodes (21): effects, fallBack(), followScrollPlainly(), followScrollWithGsap(), gl, hudFigure, hudHeading, loadScript() (+13 more)

### Community 56 - "Interpolated Weather Rasters"
Cohesion: 0.13
Nodes (22): addCategoricalLegend(), addCoordinatesToBounds(), addRasterLegend(), addWmsLayer(), addWmsLegend(), _dateFmt, _dateTimeFmt, fetchAvailableLayers() (+14 more)

### Community 57 - "Map Initialisation"
Cohesion: 0.15
Nodes (21): busy(), True while edits are queued or being written into an edited COG (this process)., BadRequest, _bbox(), dsm_edited_status(), _dsm_json(), _error(), _existing_json() (+13 more)

### Community 58 - "Housing Chain Equations"
Cohesion: 0.13
Nodes (18): Command, BaseCommand, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), get_raster_field_name(), interpolate_raster() (+10 more)

### Community 59 - "Population Cascade Signals"
Cohesion: 0.16
Nodes (21): apply_patches(), _apply_vegetation(), _box(), _building_mask(), burn(), _clear_around_buildings(), clearance_zone(), crown_heights() (+13 more)

### Community 60 - "Layer Cache Versioning"
Cohesion: 0.14
Nodes (11): OSMImporter, Import handler for OpenStreetMap through the Overpass API. The Overpass JSON is…, Overpass QL for `dataset` inside bbox [west, south, east, north] (WGS84)., Leading number of an OSM tag value: '12 m' -> 12.0, '7,5' -> 7.5, '40 ft' ->…, (Multi)polygon of a multipolygon relation from its member ways. A ring may be…, GeoJSON geometry of one Overpass element (out center or out geom)., Overpass elements -> GeoJSON features whose properties are the OSM tags plus…, OSM tags are strings ('12 m'); give numeric model fields a number, or drop the… (+3 more)

### Community 61 - "Landing Scene Renderer"
Cohesion: 0.12
Nodes (18): The observed hour (local, aware) of a run; the season's default day when empty., _when(), default_analysis_date(), month_fits_heat_mode(), normalize_heat(), A valid heat mode, HEAT_AVERAGE for anything else., The heat key figures of a scenario as display rows, one per station (`station`…, Meteorological season of a month (1-12); summer when unknown. (+10 more)

### Community 62 - "Map Calculation Cards"
Cohesion: 0.17
Nodes (17): check_download_size(), _collections(), download_bytes(), fetch_scene_inputs(), find_scenes(), GEEError, get_scene(), RuntimeError (+9 more)

### Community 63 - "Map Editor JS"
Cohesion: 0.15
Nodes (19): _adjust(), annual_growth_rate(), _city_growth_factor(), _city_value(), extrapolate(), get_population(), normalize_scenario(), population_by_year() (+11 more)

### Community 64 - "Housing Panel JS"
Cohesion: 0.17
Nodes (16): applyPopulationControls(), climateCsrf(), climateRunPost(), initPopulationHover(), lensToolIds(), loadDashboardPopulation(), loadPopulationPanel(), populationRequestParams() (+8 more)

### Community 65 - "LST Tool JS"
Cohesion: 0.12
Nodes (16): average_household_size(), baseline_population(), demand_units(), dwelling_gap(), housed_residents(), The population -> household size -> housing demand / residents chain of the…, Homes still to build for a population: needed - stock (negative = surplus).…, (population, partial) the stored housing chain uses for `city` in `year`.… (+8 more)

### Community 66 - "Bulk Import Finalizers"
Cohesion: 0.16
Nodes (17): MainmapConfig, AppConfig, journal_created_canyon(), journal_created_dsm_patch(), journal_created_landcover(), journal_rewritten_canyon(), journal_rewritten_dsm_patch(), journal_rewritten_landcover() (+9 more)

### Community 67 - "Map Settings Models"
Cohesion: 0.13
Nodes (18): raster_layer_entry(), The layer-catalog entry of one raster row (also returned by the map's LST tool)., body_surface_area(), clothing_clo(), describe(), options(), PersonError, ValueError (+10 more)

### Community 68 - "DSM Patch Overlay"
Cohesion: 0.20
Nodes (18): BadRequest, _bbox(), _date(), _error(), _grid_json(), lst_calculate(), view(), lst_scenes() (+10 more)

### Community 69 - "Heat Panel JS"
Cohesion: 0.20
Nodes (17): _body(), _feature(), generator_commit(), generator_preview(), generator_projects(), generator_remove(), _json(), _outline() (+9 more)

### Community 70 - "Landing Camera Stages"
Cohesion: 0.13
Nodes (9): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, Every green space polygon, parks included: a park is a green space with type =…, WaterBodies, WaterWaysLN (+1 more)

### Community 71 - "Weather Pill"
Cohesion: 0.15
Nodes (17): HeatInputChange, Heat stress of a stored KNMI'23 climate scenario run…, When an input of the heat model last changed (land cover, soil, the DSM,…, ScenarioHeat, climate_run_saved(), _drop_cog(), _input_changed(), mark_heat_input_changed() (+9 more)

### Community 72 - "Model Registry and Upload Form"
Cohesion: 0.12
Nodes (18): Legend stack, Map loader + console feed, mainMap.html map page, dashboard_summary.html (population KPI card), map_settings.html (Editable layers / Styles tabs), settings_editable_row.html (editable layer toggle), settings_style_form.html (vector/raster style override form), Map settings card (+10 more)

### Community 73 - "Map Frontend Config"
Cohesion: 0.18
Nodes (16): Typology defaults < style preset < the given values (None/'' ignored). Raises…, resolve_params(), _alongside(), check(), _close_pairs(), daylight_spacing(), _finding(), fire_spread() (+8 more)

### Community 74 - "Map Page Wiring"
Cohesion: 0.18
Nodes (15): bump_layer_version(), get_cache(), _label(), layer_version(), Versioned cache keys for data that only changes when rows are written. Every…, caches[alias], falling back to the default cache when the alias isn't…, Current cache version of a model's data. A missing version is seeded with the…, Invalidate every cached response built from these models' rows. (+7 more)

### Community 75 - "SVF Tool JS"
Cohesion: 0.21
Nodes (15): createLanding(), applyTier(), crossfadeTo(), dispose(), draw(), frame(), invalidate(), resize() (+7 more)

### Community 76 - "Postgres Check Tool"
Cohesion: 0.15
Nodes (14): _fill_building_heights(), get_model_class(), _import_feature_rows(), _import_geojson_features(), _keep_existing(), The per-feature half of _import_geojson_features: build each feature's field…, Fetch vector data from PDOK WFS service and import directly to Django model.…, Resolve the mapping's __fk_lookup__ entries for one feature: a plain (non-… (+6 more)

### Community 77 - "Degree of Urbanisation Views"
Cohesion: 0.21
Nodes (15): _journal_if_backup(), materialise(), Store a generated neighbourhood layout (builtup/calculations/generative.py) as…, core.editing.journal, or a no-op when there is no restore point (one query…, Delete the streets, buildings and dwellings generated for a project…, Replace the project's generated rows with a fresh layout of `outline` (GEOS…, remove(), _to_geos() (+7 more)

### Community 78 - "Builtup Models"
Cohesion: 0.25
Nodes (13): _attachEditor(), _bindDrawEvents(), _cancelEdit(), _drawModeFor(), _featureUrl(), _hideOriginal(), _openEditorPanel(), _removeDrawControl() (+5 more)

### Community 79 - "Landing Page Docs"
Cohesion: 0.30
Nodes (14): init(), calculate(), commonParams(), csrfToken(), findScenes(), open(), pct(), readJson() (+6 more)

### Community 80 - "Info Popover"
Cohesion: 0.29
Nodes (14): animate(), bboxParam(), bindInteractions(), ensureLayers(), init(), reload(), scheduleReload(), setActive() (+6 more)

### Community 81 - "Population Dock Panels"
Cohesion: 0.13
Nodes (8): Point-in-polygon lookup against a fixed set of parent rows. Each parent's…, Load only what the lookup needs: pk, geom and any attributes read off the…, The parent containing `geom`'s representative point, or None., SpatialParentIndex, _gml_multipolygon(), _import_atom_gml_features(), WGS84 MultiPolygon of every gml:Polygon below `elem` (None if there are none,…, Stream an INSPIRE Planned Land Use GML file over HTTP and import the…

### Community 82 - "SOLWEIG Raster Inputs"
Cohesion: 0.15
Nodes (11): EditableLayer, EditBackup, EditBackupRow, LayerStyleOverride, Meta, The state of one object when the backup was made. `original` holds the row as…, A vector layer staff may edit on the map, switched on in the map's settings…, Restore point for what-if edits made with the map editor (core/editing.py,… (+3 more)

### Community 83 - "Weather Raster Views"
Cohesion: 0.17
Nodes (14): build(), _footprints(), Inputs, landcover_grid(), plan(), ValueError, CrossTwin layers -> the SOLWEIG input rasters of one view, on one grid. window…, SOLWEIG land-cover classes on the grid, or None without land-cover polygons. (+6 more)

### Community 84 - "DEGURBA Classifier"
Cohesion: 0.14
Nodes (14): availableLayers, BASEMAPS, BUILDING_COLOR_BY_TOOL, BUILDING_COLOR_DEFAULT, CONFIG, HIDES_3D_BUILDINGS_APPS, HIDES_3D_BUILDINGS_KEYS, layerVisibility (+6 more)

### Community 85 - "Builtup Indicator Cards"
Cohesion: 0.24
Nodes (14): cameraAt(), CAMERAS, fitFactor(), HOLD_END, LAST_STAGE, layersAt(), locate(), mix() (+6 more)

### Community 86 - "Degree of Urbanisation Tool JS"
Cohesion: 0.32
Nodes (13): applyPrecipEffect(), fmt(), init(), load(), openHeatPanel(), precipKind(), radarLayer(), radarVisible() (+5 more)

### Community 87 - "Sky View Factor"
Cohesion: 0.14
Nodes (14): BBOX_FROM_LEVEL picker level (coarsest wins), Area of Interest bbox map panel, Date Range panel, Import button handler (start_external_import), Import first notice and confirm, initBboxMap(), Import Public Data page, Copernicus openEO credentials panel (+6 more)

### Community 88 - "Meteorology Model"
Cohesion: 0.18
Nodes (13): aspect_ratio(), canyon(), canyon_height(), canyon_width(), classify_unit(), Pure equations of the street canyon (no ORM queries). H = (H_left + H_right) /…, Mean of the two side heights in metres; a side without buildings is 0., (W in metres, source): 'street' (typed width), 'facade' (measured) or 'default'. (+5 more)

### Community 89 - "Bulk Writer"
Cohesion: 0.18
Nodes (7): bag_usage_labels(), DAG edges: Buildings -> Canyon_Aspect, Streets -> Canyon_Aspect. Re-reads the…, BAG gebruiksdoel as a list of labels (Building.BAG_USAGE_FUNCTIONS). WFS…, Degree of Urbanisation of an admin unit (DAG node Degree_Urbanisation): its…, DAG edges: Total_Population -> Degree_Urbanisation, Buildings ->…, Set every derived field from the population per class and the urban area (m²)., Urbanisation

### Community 90 - "Feature Editor Form"
Cohesion: 0.14
Nodes (14): Building Stock card, Building Type Mix card, Built-up Coverage gauge (FAR), Construction Period card, Built-up indicators grid partial, info_help template tag usage, Park Area per Inhabitant gauge (WHO thresholds), Street Network density card (+6 more)

### Community 91 - "Green Area Land Cover"
Cohesion: 0.25
Nodes (14): applyLensToNewLayers(), closeLens(), filterLayersByLens(), focusCardLayers(), isWeatherPillLayer(), layerModelKey(), lensApps(), lensShows() (+6 more)

### Community 92 - "Population Projection Model"
Cohesion: 0.27
Nodes (12): baselineYear(), isBaselinePopulation(), isBaselineTime(), leaveEdit(), MAP_MODES, panelWhatifMoved(), planWhatifs(), POP_VARIANT_LABELS (+4 more)

### Community 93 - "Background Worker"
Cohesion: 0.30
Nodes (12): init(), calculate(), csrfToken(), loadInfo(), open(), params(), readJson(), refreshButton() (+4 more)

### Community 94 - "Earth Engine Auth"
Cohesion: 0.22
Nodes (13): RuntimeError, current_weather(), current_weather_or_none(), describe(), enabled(), LiveWeatherError, parse_current(), Live weather at a point from Open-Meteo's forecast API (current conditions, a… (+5 more)

### Community 95 - "Builtup Dashboard JS"
Cohesion: 0.32
Nodes (13): _connect(), _create_extensions_help(), _diagnose_connection_error(), _install_postgis_help(), _install_postgres_help(), main(), _postgres_binaries(), Check that PostgreSQL is reachable with the .env settings and has PostGIS. Run… (+5 more)

### Community 96 - "Console Feed JS"
Cohesion: 0.28
Nodes (12): city_changed(), _defer(), deferred_population_cascade(), district_changed(), _flush_population_cascade(), neighborhood_changed(), receiver, Postpone the District -> City -> Province cascade until the block ends, then… (+4 more)

### Community 97 - "Map Settings JS"
Cohesion: 0.15
Nodes (13): CrossTwin README, tools/check_postgres.py PostGIS check, External Data Sources (PDOK, CBS, KNMI, BIS, OSM, Sentinel-2, GEE, Klimaateffectatlas), model_geojson cached GeoJSON endpoint, GeoJSON Layer Cache (2-minute TTL), Model registry (core/utils.py build_model_registry), Raster to COG pipeline, Two-server setup (Django + TiTiler) (+5 more)

### Community 98 - "Indicator Help Tag"
Cohesion: 0.18
Nodes (8): baseline_population(), consumption_m3_yr(), Population the stored chain uses for `city` in `year`: the CBS median forecast…, Yearly residential water consumption in m3/year (households only, no small…, ConsumptionCapita, DAG edges: Total_Population, ConsumptionCapita -> Total_Water_Demand (yearly…, The record to use for `city` in `year`: that year's, else the latest earlier…, TotalWaterDemand

### Community 99 - "Version Labels"
Cohesion: 0.24
Nodes (12): addLayer(), addRasterLayer(), addRasterLayerFromConfig(), bindViewportReload(), reloadLayer(), reloadViewportLayer(), selectNoLayers(), showLoader() (+4 more)

### Community 100 - "HILUCS Land Use Codes"
Cohesion: 0.17
Nodes (12): climate_run_label(), _cog_statistics(), _lookup_style(), raster_display_name(), raster_style_key(), Shared index/model lookup used by both the tile colormap and the display name,…, The key a raster's style default lives under, and so its staff override…, Build a display name matching the legend label plus the acquisition date as MM-… (+4 more)

### Community 101 - "Architecture Export"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 102 - "Non-Revenue Water"
Cohesion: 0.44
Nodes (10): _border(), classify(), _component_sums(), _components(), density(), _fill_holes(), _keep(), _smooth() (+2 more)

### Community 103 - "Street Canyon Equations"
Cohesion: 0.27
Nodes (10): True while a background refresh is queued or running (this process)., rebuild(), refreshing(), status(), degurba_calculate(), degurba_info(), _json(), require_GET (+2 more)

### Community 104 - "GEE Importer"
Cohesion: 0.20
Nodes (11): Degree of Urbanisation card, Degree of Urbanisation card, Anthropogenic_Heat -> Meteorology gap, Climate_Change -> Meteorology partial edge, Degree of Urbanisation, DPSIR causal graph DAG.dot, Gaps: New_Units -> Buildings -> Streets -> LandCover, Housing demand from household size (+3 more)

### Community 105 - "Layer and Tree Styles"
Cohesion: 0.25
Nodes (9): Implementation status of every edge of core/DAG.dot, for the DAG viewer.…, build(), causal_levels(), main(), parse(), Write docs/dag_view.html: an interactive view of core/DAG.dot with the…, Nodes (id -> label, category, comment) and edges (a, b, attrs, comment), legend…, Longest path from a source over the non-lagged edges (the graph is acyclic… (+1 more)

### Community 106 - "Fill Tree Heights Command"
Cohesion: 0.42
Nodes (10): init(), afterEdit(), calculate(), csrfToken(), loadInfo(), open(), readJson(), render() (+2 more)

### Community 107 - "DB Stats Command"
Cohesion: 0.29
Nodes (11): addAnimatedWmsLayer(), applyWmsFrame(), fetchWmsTimeSteps(), mercatorTileBbox(), prefetchWmsFrames(), renderWmsScrubberDock(), scheduleWmsTimeRefresh(), scrubWmsAnimation() (+3 more)

### Community 108 - "Query Stats Middleware"
Cohesion: 0.24
Nodes (11): createMultiFeaturePopupContent(), createPopupContent(), _featureTitleKey(), _formatValue(), initFeaturePopup(), _popupEditButton(), _popupHead(), _popupTable() (+3 more)

### Community 109 - "Deferred Cascades"
Cohesion: 0.18
Nodes (11): Layers panel, Main map page template, Edit backup bar, Restore point backup, No-backup warning (permanent changes), CBS projection variants, Population dock panel, Population projection graph (+3 more)

### Community 110 - "Land Cover Styles"
Cohesion: 0.20
Nodes (10): climate_effects(), The admin unit of a panel URL, or None (demo / unknown)., Effects of a KNMI'23 scenario on the Water Supply and Urban Heat indicators of…, _resolve_unit(), describe(), is_interpolated(), population_year(), Whether a scenario key is an interpolated decade (not a published KNMI'23… (+2 more)

### Community 111 - "Environmental Costs"
Cohesion: 0.18
Nodes (6): Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:…, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child…, Generic interpolation method - works for all child classes

### Community 112 - "Supply Security Equations"
Cohesion: 0.29
Nodes (7): _finding(), _ha(), Site check of the neighbourhood generator: may a neighbourhood be built on this…, SiteCheck of a GEOS (Multi)Polygon outline in the storage CRS., site_constraints(), SiteCheck, ZoningArea

### Community 113 - "Upload Templates"
Cohesion: 0.22
Nodes (9): city_factors(), dashboard(), whatif_unit(), One grid cell of the Degree of Urbanisation, at 100 m (CrossTwin's local…, Map layer: Degree of Urbanisation on 100 m cells (CrossTwin's local variant),…, Map layer: Degree of Urbanisation on 1 km cells (original method, same data),…, UrbanisationCell, UrbanisationCellLocal (+1 more)

### Community 114 - "App Icon 512"
Cohesion: 0.20
Nodes (6): ElectricityCost, EUR/kWh for `province_id` in `year`: the province's record, else a national…, energy_cost_EUR_yr(), Yearly electricity cost of pumping: kWh/day x 365 x EUR/kWh. DAG edge:…, DAG edges: Total_Extraction/Total_Water_Prod -> OPEX Energy_Consumption -> OPEX…, Set productionDay/YR (Mm3) and costDay/YR (EUR) from the active wells of the…

### Community 115 - "Energy Models"
Cohesion: 0.27
Nodes (4): BulkWriter, Collects rows and writes them `batch_size` at a time. With a unique field, rows…, A writer when `Model` can safely be bulk-written, otherwise None (use the row…, Write what is left, replay the skipped signals and invalidate the layer cache.

### Community 116 - "Importer Geometry Utils"
Cohesion: 0.22
Nodes (5): InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Convenience method to generate raster for a Province Args: Province: Province…, Override in child classes to specify which measurement field to use, Override in child classes to specify metadata keys Returns tuple: (min_key,…

### Community 117 - "Humidity Raster"
Cohesion: 0.22
Nodes (3): PopulationProjection, Projected total population of a City for one year and forecast variant. Loaded…, Scenario

### Community 118 - "Precipitation Raster"
Cohesion: 0.22
Nodes (4): BackgroundWorker, Coalescing background workers for derived data that a map edit must not wait…, Queue `item`; start the thread when it is idle., True while items are queued or a batch is running (this process).

### Community 119 - "Temperature Raster"
Cohesion: 0.28
Nodes (5): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE for the given Cloud project. `ee.Authenticate()` is a one-time-…, initialize(), Authenticate once per process, like the importer's GEE sources.

### Community 120 - "Admin Unit Point Lookup"
Cohesion: 0.31
Nodes (5): KNMIImporter, KNMI Data Platform (Open Data API v1). Flow: list the newest file of a dataset…, UTC datetime encoded in a KNMI file name, or None if it has none., Convert a downloaded KNMI grid to a single-band float32 GeoTIFF in…, Import the newest file of the dataset described by a catalog entry.

### Community 121 - "App Icon 192"
Cohesion: 0.29
Nodes (4): BaseCommand, Tree, Command, Measure the height of stored trees that have none from the DSM…

### Community 122 - "Django Settings"
Cohesion: 0.50
Nodes (7): begin(), busy(), end(), poll(), render(), schedule(), settle()

### Community 123 - "Housing App Config"
Cohesion: 0.46
Nodes (6): applyEditable(), applyStyle(), catalogEntry(), init(), preview(), readdLayer()

### Community 124 - "CBS Importer"
Cohesion: 0.32
Nodes (6): _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. Counts half the commits:…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 125 - "FK Lookup Resolution"
Cohesion: 0.29
Nodes (8): Actions menu (import, calculate for this view, year selector), Bottom bar (indicator pills, camera buttons), LST tool card, Thermal Comfort (SOLWEIG) card, SVF tool card, LST -> PET edge removed from DAG, DSM -> SVF -> Tmrt/PET/UTCI chain (SOLWEIG on demand), Vegetation_Coverage -> DSM (DSMVegetationPatch)

### Community 126 - "Manage Entry Point"
Cohesion: 0.29
Nodes (8): Delete confirmation, Feature editor side-panel form, deferred_cascades bulk import batching, Key conventions (SRID, save(), DO_NOTHING, update(), no inline scripts), Signal-driven computation, Urban-fabric buffer around editor buildings (urbanize_around / release_ring), Sentinel-2 broadband albedo on LandCoverVector (RS_Imagery -> LandCover partial), New_Green_Area -> LandCover (editor green spaces)

### Community 127 - "Style Suggestions"
Cohesion: 0.29
Nodes (7): hilucs_lookup(), hilucs_q(), parse_hilucs_href(), INSPIRE HILUCS (Hierarchical INSPIRE Land Use Classification System) helpers. A…, (code, label) of a HILUCS URI, or None if it is not one. The label is spelled…, __fk_lookup__ parser for HILUCS URIs (importer/external_data.py): returns…, Q matching rows whose HILUCS FK `field` is one of `codes` or below it in the…

### Community 128 - "Water Supply App Config"
Cohesion: 0.43
Nodes (7): browser(), main(), page(), Export docs/architecture/latest/*.svg to PNG and PDF with headless Chrome/Edge.…, One page per SVG, each page sized to its diagram (named @page rules)., run(), size()

### Community 129 - "Weather App Config"
Cohesion: 0.39
Nodes (7): _cell(), _endpoint(), main(), Write docs/DATA_SOURCES.md: every importer catalog dataset (grouped by…, Where a catalog dataset comes from: URL + layer, Earth Engine asset, CBS table…, render(), _setup()

### Community 130 - "Geo Area Helper"
Cohesion: 0.25
Nodes (8): _climate_weather(), _month(), Month (1-12) of an ISO date/time string, None when it has none., Year of an ISO date/time string, None when it has none (the scenario change is…, The observed baseline weather moved into a KNMI'23 scenario (delta-change of…, _year(), nearest_station(), The key-figure station closest to a WGS84 point (equirectangular distance,…

### Community 131 - "Apple Touch Icon"
Cohesion: 0.25
Nodes (4): LossesChoices, LossesTypes, NonRevenueWater, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 132 - "Favicon 16"
Cohesion: 0.33
Nodes (5): Scroll-driven Three.js City Landing, Landing stages (overview to what-if editing), CrossTwin digital twin platform, DPSIR framework (core/DAG.dot), Gohlke GDAL wheel on Windows

### Community 133 - "Favicon 32"
Cohesion: 0.38
Nodes (5): GEEImporter, prepare(), Import handler for Google Earth Engine datasets. Optional catalog keys on a GEE…, Function Image -> Image selecting (or deriving) the entry's band., Export raster from GEE to local GeoTIFF.

### Community 134 - "Energy App Config"
Cohesion: 0.43
Nodes (5): is_startup_module(), main(), Claude Code PostToolUse hook: project checks after an edit. Wired in…, run(), top_level_heavy_imports()

### Community 135 - "Importer App Config"
Cohesion: 0.29
Nodes (7): get_thermal_indices(), stats(), _raster_stats_sql(), Min/max/mean/stddev of one raster clipped to a geometry, plus its coverage.…, The observed SOLWEIG run whose Tmrt, PET and UTCI the heat card shows. Done…, Statistics over the stored thermal rasters inside the unit (read only).…, select_thermal_run()

### Community 136 - "Nature App Config"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Show the most expensive SQL statements recorded by pg_stat_statements…

### Community 138 - "Urban Heat App Config"
Cohesion: 0.47
Nodes (4): getLayerLegendIcon(), markActiveLens(), renderLayerList(), renderLensRail()

### Community 139 - "Admin Unit Resolver"
Cohesion: 0.40
Nodes (6): _pave(), Street.width when typed in, else the class default of the canyon equations…, DAG edge: Streets -> LandCover. A street drawn, generated or reshaped in the…, street_landcover_saved(), move(), _street_width()

### Community 140 - "City Name JS"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 141 - "Draggable Overlays"
Cohesion: 0.40
Nodes (3): GreenSpacesQuerySet, Green spaces of type 'park' (OSM leisure=park, parks drawn in the map editor)., Public park space: parks plus BGT recreation areas (type 'recreatie…').

### Community 142 - "Model Selector JS"
Cohesion: 0.40
Nodes (4): DSMBuildingPatch, A map-editor change of one building, applied on top of every DSM when it is…, dsm_patch_changed(), Log the area where the DSM overlay changed (DSMEdit), raw saves and Restore's…

### Community 143 - "ASGI Config"
Cohesion: 0.40
Nodes (3): LeakageIndex, DAG edges: Real_Losses -> ILI (CARL), Network -> ILI (UARL from the mains…, Infrastructure Leakage Index of the whole network for one year (IWA): ILI =…

### Community 148 - "Household Size Edges"
Cohesion: 0.50
Nodes (4): Built once per process: creating a GDAL/PROJ transformation is the slow part of…, Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), _wgs84_to_storage()

### Community 151 - "Core Admin"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 152 - "HTTP Method Decorator"
Cohesion: 0.50
Nodes (3): initializeUI(), selectAllLayers(), toggleLayersDrawer()

### Community 155 - "Energy Views"
Cohesion: 0.50
Nodes (4): External data import page, PDOK CBS Sentinel-2 GEE sources, Column mapping step 2, Importer field mapping page

### Community 157 - "Importer Models"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 158 - "Explore Filters"
Cohesion: 0.50
Nodes (3): .venv/Scripts/python.exe, context7, postgres

### Community 159 - "MainMap Admin"
Cohesion: 0.50
Nodes (3): middleware, cache_versioned_tiles(), Tile and info responses whose URL carries `v=` (the COG's mtime, added by…

### Community 161 - "Nature Views"
Cohesion: 0.50
Nodes (4): Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono)

### Community 165 - "Style Suggestion Doc"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 166 - "TiTiler App"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 167 - "Infiltration Edge"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

## Knowledge Gaps
- **179 isolated node(s):** `HILUCSLandUseAdmin`, `LandCoverClassesAdmin`, `SoilTypeAdmin`, `SurfaceMaterialPropertiesAdmin`, `TpwSource` (+174 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1407 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **54 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Building` connect `Indicator Help and Water JS` to `Builtup Signals and Canyons`, `Water Supply Models and Signals`, `Map Layers and Events`, `Landing Scroll Wiring`, `Water Supply Indicators`, `Population Projections`, `Postgres Check Tool`, `Degree of Urbanisation Views`, `Soil Infiltration (SCS)`, `Administrative Units`, `Supply Security Equations`, `KNMI Importer`, `Weather Raster Views`, `Architecture Diagrams Tooling`, `Bulk Writer`, `Population Cascade Signals`, `Landing Plan Layout`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `is_extrapolated()` connect `LST Earth Engine Inputs` to `PhysicalEnv Signals and DSM`, `GET Decorator`, `SOLWEIG Meteorology Inputs`, `LST Pipeline and NDVI`, `Landing Scroll Wiring`, `Green Spaces and Heat Indicators`, `Soil Infiltration (SCS)`, `Land Cover Styles`, `Urbanisation Dashboard and What-if`, `Map Editor JS`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `raster_layer_entry()` connect `Map Settings Models` to `HILUCS Land Use Codes`, `SOLWEIG Meteorology Inputs`, `DSM Patch Overlay`, `Landing City Builder`, `Housing Signals and Property`, `Map Initialisation`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `Building` (e.g. with `_sql()` and `calculate_building_age()`) actually correct?**
  _`Building` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `LandCoverVector` (e.g. with `landcover_shares()` and `_landcover_rows_created()`) actually correct?**
  _`LandCoverVector` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Property` (e.g. with `remove()` and `_tables()`) actually correct?**
  _`Property` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `init()` (e.g. with `close()` and `commit()`) actually correct?**
  _`init()` has 6 INFERRED edges - model-reasoned connections that need verification._