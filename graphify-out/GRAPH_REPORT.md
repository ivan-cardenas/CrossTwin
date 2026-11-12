# Graph Report - CrossTwin  (2026-11-12)

## Corpus Check
- 70 files · ~222,274 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2578 nodes · 5059 edges · 169 communities (125 shown, 31 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 444 edges (avg confidence: 0.92)
- Token cost: 150,714 input · 0 output

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
- ASGI Config
- WSGI Config
- Import Templates
- Setup and Example Data
- Housing Affordability Gaps
- Household Size Edges
- Water Loss Edges
- Province Raster Generation
- HTTP Method Decorator
- Feature Form Template
- Project Package
- PostGIS Test Runner
- GET Decorator
- Style Suggestion Doc
- Infiltration Edge
- PET to NBS Gap

## God Nodes (most connected - your core abstractions)
1. `City` - 58 edges
2. `Neighborhood` - 43 edges
3. `Building` - 35 edges
4. `LandCoverVector` - 31 edges
5. `Province` - 30 edges
6. `buildCity()` - 23 edges
7. `District` - 23 edges
8. `import_dataset()` - 21 edges
9. `ImportResult` - 20 edges
10. `calculate_lst()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Weather What-if Sliders (ta_c, rh_pct, wind_ms, kdown_wm2)` --semantically_similar_to--> `Rain Event + Groundwater Season What-if`  [INFERRED] [semantically similar]
  urban_heat/templates/urban_heat/partials/whatif_controls.html → watersupply/templates/watersupply/partials/rain_slider.html
- `New_Green_Area -> LandCover (editor green spaces)` --semantically_similar_to--> `Urban-fabric buffer around editor buildings (urbanize_around / release_ring)`  [INFERRED] [semantically similar]
  TODO.md → README.md
- `InterpolatedRasterBase` --uses--> `Province`  [INFERRED]
  weather/models.py → administrative/models.py
- `ElectricityCost` --uses--> `Province`  [INFERRED]
  Energy/models.py → administrative/models.py
- `NeighborhoodHeat` --uses--> `Neighborhood`  [INFERRED]
  urban_heat/models.py → administrative/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **External import area-of-interest picker flow** — importer_templates_importer_external_data_togglearea, importer_templates_importer_external_data_unionbbox [EXTRACTED 1.00]
- **Info help popover flow** — templates_partials_info_btn, core_indicator_help, core_static_js_info_popover, templates_indicators_base [EXTRACTED 1.00]
- **Map editing UI (feature form, backup bar, Editing.js, core.editing)** — mainmap_templates_mainmap_partials_feature_form, mainmap_templates_mainmap_partials_backup_bar, core_static_js_editing, core_editing [EXTRACTED 1.00]
- **Map settings panel (editable layers + style overrides)** — mainmap_templates_mainmap_settings_card, mainmap_templates_mainmap_partials_map_settings, mainmap_templates_mainmap_partials_settings_editable_row, mainmap_templates_mainmap_partials_settings_style_form, core_static_js_mapsettings [EXTRACTED 1.00]
- **CrossTwin icon composition: physical city, digital wireframe, orbit ring** — core_static_ico_android_chrome_512x512_isometric_city_block, core_static_ico_android_chrome_512x512_cyan_wireframe_grid, core_static_ico_android_chrome_512x512_orbit_ring [INFERRED 0.85]
- **Domain indicator side panels sharing grid + JS pattern** — watersupply_templates_watersupply_partials_indicators_panel, housing_templates_housing_partials_indicators_panel, builtup_templates_builtup_partials_indicators_panel, urban_heat_templates_urban_heat_partials_indicators_panel, readme_indicator_dashboard_pattern [INFERRED 0.85]
- **Landing fallback sketch generation flow** — core_static_js_landing_plan, tools_landing_fallback_svg, core_static_img_landing_city_blueprint, mainmap_templates_mainmap_landing [INFERRED 0.85]
- **Calculate-for-this-view map tools (shared lst-card UI)** — mainmap_templates_mainmap_actions_menu, mainmap_templates_mainmap_lst_card, mainmap_templates_mainmap_svf_card, mainmap_templates_mainmap_solweig_card, mainmap_templates_mainmap_degurba_card [EXTRACTED 1.00]
- **Map-editor geometry edits rewriting land cover / DSM** — readme_urbanize_around, todo_new_green_area_landcover, todo_vegetation_dsm, mainmap_templates_mainmap_partials_feature_form_feature_editor [INFERRED 0.75]
- **Degree of Urbanisation across DAG, dashboard and map card** — todo_degree_of_urbanisation, todo_urbanization_node_removed, builtup_templates_builtup_partials_indicators_grid_degree_of_urbanisation_card, mainmap_templates_mainmap_degurba_card [INFERRED 0.85]

## Communities (169 total, 31 thin omitted)

### Community 0 - "Builtup Signals and Canyons"
Cohesion: 0.05
Nodes (63): BuiltupConfig, AppConfig, _sql(), street_inputs(), streets_near(), neighborhoods_at(), DAG edges: Buildings -> Canyon_Aspect, Streets -> Canyon_Aspect. Re-reads the…, The urban canyon of one street: height-to-width ratio H/W. H = mean of the… (+55 more)

### Community 1 - "Water Supply Models and Signals"
Cohesion: 0.07
Nodes (60): AvailableFreshWater, SupplySecurity, TotalWaterProduction, bbox_polygon(), _cities_in_watersheds(), city_population_cascaded(), city_saved(), consumption_saved() (+52 more)

### Community 2 - "Map Layers and Events"
Cohesion: 0.07
Nodes (59): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+51 more)

### Community 3 - "PhysicalEnv Signals and DSM"
Cohesion: 0.06
Nodes (59): PhysicalEnvConfig, AppConfig, building_height(), record_change(), record_vegetation_change(), tree_crown(), tree_height(), release_ring() (+51 more)

### Community 4 - "Map Views and Charts"
Cohesion: 0.05
Nodes (54): build_population_chart(), pts(), x_of(), y_of(), nice_step(), Vertical grid years: multiples of 5 inside the range (or the ends for a short…, Chart data for `unit`, or None when no projection is imported for it. scenario:…, 164800 -> '164.8k', 2_100_000 -> '2.1M' (axis labels). (+46 more)

### Community 5 - "SOLWEIG Meteorology Inputs"
Cohesion: 0.05
Nodes (50): _era5_day(), era5_day_from_values(), era5_from_values(), era5_hourly(), knmi_day_values(), _knmi_hour(), knmi_hourly(), Met (+42 more)

### Community 6 - "Map Editing Backup"
Cohesion: 0.07
Nodes (48): active_backup(), backup(), _backup_bar(), backup_discard(), backup_restore(), _build_form(), _check_constraints(), _editable_model() (+40 more)

### Community 7 - "Green Spaces and Heat Indicators"
Cohesion: 0.09
Nodes (39): GreenSpaces, Every green space polygon, parks included: a park is a green space with type =…, absorbed_radiation_w_m2(), apparent_temperature_c(), clamp_weather(), vapour_pressure_hpa(), wbgt_estimate_c(), weather_heat_stress() (+31 more)

### Community 8 - "Water Supply Indicators"
Cohesion: 0.11
Nodes (36): get_population(), active_wells_with_watershed(), calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage(), calculate_drought_area(), calculate_energy_consumption() (+28 more)

### Community 9 - "Water Supply Chain Equations"
Cohesion: 0.07
Nodes (21): WMSLayerAdmin, baseline_population(), consumption_m3_yr(), demand_m3_d(), AreaAffectedDrought, ConsumptionCapita, CoverageWaterSupply, ImportedWater (+13 more)

### Community 10 - "Landing City Builder"
Cohesion: 0.10
Nodes (35): alongPath(), buildCity(), update(), geometryFrom(), HEAT_STOPS, heatColor(), heatMaterial(), HOUSE_COLORS (+27 more)

### Community 11 - "Live Weather Service"
Cohesion: 0.08
Nodes (36): RuntimeError, current_weather(), current_weather_or_none(), describe(), enabled(), LiveWeatherError, parse_current(), Live weather at a point from Open-Meteo's forecast API (current conditions, a… (+28 more)

### Community 12 - "Core Console and Views"
Cohesion: 0.06
Nodes (27): CoreConfig, AppConfig, add(), clear(), FeedHandler, install(), NotDjango, Console feed: the server's own progress lines, shown under the map loader. The… (+19 more)

### Community 13 - "Urban Heat Raster Models"
Cohesion: 0.06
Nodes (23): MeanRadiantTemperature, Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, NeighborhoodHeat, PET, Sky View Factor (SVF) measurements, Physiological Equivalent Temperature (PET) measurements (+15 more)

### Community 14 - "Soil Infiltration (SCS)"
Cohesion: 0.10
Nodes (25): curve_number(), group_rate_mm_h(), impervious_fraction(), infiltration_coefficient(), is_drained(), _matches(), scs_runoff_mm(), soil_landcover_composition() (+17 more)

### Community 15 - "Administrative Units"
Cohesion: 0.15
Nodes (21): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, cities_within(), city_of(), neighborhoods_within(), province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any… (+13 more)

### Community 16 - "Land Cover and Albedo"
Cohesion: 0.11
Nodes (22): NamedTuple, default_material_for(), material(), material_code_for(), measure(), ring_albedo(), set_default_materials(), _buffer_sql() (+14 more)

### Community 17 - "Urbanisation Grid Refresh"
Cohesion: 0.16
Nodes (29): allocate(), _background(), _background_job(), _bump(), _cells_over(), _class_population_sql(), classify_grid(), _collect() (+21 more)

### Community 18 - "Building Heights and SVF Inputs"
Cohesion: 0.15
Nodes (29): _fill(), fill_from_dsm(), fill_under_dsm(), footprint_heights(), _label(), Building heights from the DSM, for buildings whose source gives none. BAG…, fill_from_dsm's work; returns the buildings that got a height., Height above ground of each footprint on one grid, or None. surface, ground:… (+21 more)

### Community 19 - "SOLWEIG Views"
Cohesion: 0.15
Nodes (30): wgs84_to_storage(), Map the tool's expected failures to 400 and anything else to 502., centre(), Status of a run for the map tool; a run left 'running' by a dead process reads…, Results that the editor's building changes made stale inside `view` (storage…, run_state(), stale_results(), BadRequest (+22 more)

### Community 20 - "Housing Signals and Property"
Cohesion: 0.11
Nodes (27): Property, Proxy onto builtup.Property limited to dwellings (BAG woonfunctie), its own map…, ResidentialProperty, city_population_cascaded(), city_saved(), deferred_housing_refresh(), _dwellings_of_city(), _flush_housing_refresh() (+19 more)

### Community 21 - "PhysicalEnv Admin and Models"
Cohesion: 0.09
Nodes (20): HILUCSLandUseAdmin, LandCoverClassesAdmin, SoilTypeAdmin, SurfaceMaterialPropertiesAdmin, classify_soil_group(), DigitalElevationModelWMS, DigitalSurfaceModelWMS, HILUCSLandUse (+12 more)

### Community 22 - "Edited DSM COG"
Cohesion: 0.10
Nodes (26): _background(), cog_window(), edited_cog_name(), enqueue(), _job(), _patch_extents(), patch_window(), Buildings -> DSM, Vegetation_Coverage -> DSM: the editor's patches written into… (+18 more)

### Community 23 - "Architecture Diagrams Tooling"
Cohesion: 0.11
Nodes (19): apps(), Diagram, editing(), importer(), infiltration(), on_demand(), overview(), raster() (+11 more)

### Community 24 - "LST Grid"
Cohesion: 0.10
Nodes (21): Grid, Smallest grid with corners on multiples of `resolution` that covers the extent., Affine in Earth Engine's order: [xScale, xShear, xOffset, yShear, yScale,…, [west, south, east, north] in EPSG:4326, for filtering image collections., North-up grid: (x0, y0) is the top-left corner, cells are `resolution` m square., grid_for(), LSTError, ndvi_layer() (+13 more)

### Community 25 - "Urbanisation Dashboard and What-if"
Cohesion: 0.10
Nodes (21): city_factors(), dashboard(), whatif_unit(), BuildingEnergyLabel, _CurrentCells, Facility, _LocalCells, Meta (+13 more)

### Community 26 - "External Data Import Core"
Cohesion: 0.12
Nodes (17): get_model_class(), import_dataset(), ImportResult, PDOKImporter, Import handler for PDOK datasets - imports directly to Django models., Fetch vector data from PDOK WFS service and import directly to Django model.…, Split [min_v, max_v] into evenly-sized segments, each no larger than…, Fetch vector data from an OGC API Features service (PDOK's newer REST/JSON… (+9 more)

### Community 27 - "SOLWEIG Pipeline"
Cohesion: 0.11
Nodes (26): plan(), ValueError, What a run over `view` (storage CRS) would read: the DSM, the covered view, the…, SolweigError, calculate(), device(), execute(), local_timezone() (+18 more)

### Community 28 - "Editable Layer Settings"
Cohesion: 0.13
Nodes (26): editable_keys(), enable_blocker(), Why the layer `key` may not be switched on, or None when it may. A model whose…, Registry keys of the layers switched on in the settings panel (one query)., _colormaps(), _editable_row(), _forbidden(), _layer_name() (+18 more)

### Community 29 - "External Catalog and Console"
Cohesion: 0.09
Nodes (21): Console progress lines for the importers (upload wizard, external import), so…, One console line. Forced to ASCII: a character the Windows cp1252 console can't…, say(), get_catalog_grouped(), _kea_building(), _kea_neighborhood(), Mapping for a per-buurt KEA layer: one row per stored neighborhood, keyed on…, Return the catalog grouped by category. Structure: { category: [datasets] }… (+13 more)

### Community 30 - "Housing Indicators"
Cohesion: 0.16
Nodes (22): ZoningArea, calculate_affordability(), calculate_dwellings(), calculate_house_price_index(), calculate_household_size(), calculate_new_units(), calculate_new_units_for_unit(), calculate_pipeline_land_take() (+14 more)

### Community 31 - "Landing Plan Layout"
Cohesion: 0.17
Nodes (22): city_blueprint.svg (landing no-WebGL city sketch), blueprintSegments(), boundaries(), buildPlan(), canalX(), circleLine(), crossing(), inDisc() (+14 more)

### Community 32 - "Spatial Parent Index"
Cohesion: 0.09
Nodes (17): GEOSGeometry, Point-in-polygon lookup against a fixed set of parent rows. Each parent's…, Load only what the lookup needs: pk, geom and any attributes read off the…, The parent containing `geom`'s representative point, or None., SpatialParentIndex, ensure_multipolygon(), _gml_multipolygon(), _import_atom_gml_features() (+9 more)

### Community 33 - "Housing Models and Admin"
Cohesion: 0.11
Nodes (13): calculate_mortgage_indicators(), CentralBankPolicy, CreditSupplyConditions, HousePriceIndex, HousingAffordability, HousingProject, HousingSupplyDemand, Meta (+5 more)

### Community 34 - "Map Style Overrides"
Cohesion: 0.12
Nodes (23): Form fields of a vector style: default value, current value, input kind., _vector_fields(), apply_raster_override(), apply_vector_override(), base_vector_style(), is_color_match(), is_scalar(), match_categories() (+15 more)

### Community 35 - "LST SMW Equations"
Cohesion: 0.12
Nodes (23): Constants of the Statistical Mono-Window (SMW) LST algorithm for Landsat 8/9.…, apply_qa_emissivity(), bare_ground_emissivity(), _bit_set(), cloud_mask(), fractional_vegetation_cover(), interpolate_tpw(), land_surface_temperature() (+15 more)

### Community 36 - "Builtup Indicators"
Cohesion: 0.19
Nodes (21): population_params(), calculate_building_age(), calculate_building_mix(), calculate_building_stock(), calculate_facilities(), calculate_green_space(), calculate_street_network(), _pct() (+13 more)

### Community 37 - "External Data Enrichment"
Cohesion: 0.11
Nodes (20): Exception, default_wms_legend_url(), _enrich_rows(), _fill_building_heights(), _import_geojson_features(), _ImportBlocked, _keep_existing(), _legend_url_from_capabilities() (+12 more)

### Community 38 - "LST Pipeline and NDVI"
Cohesion: 0.12
Nodes (19): LandCoverRaster, The one raster grid every LST input is put on before the equations run., calculate_lst(), default_window(), LSTResult, ndvi_mosaic(), LST from Landsat 9 + CrossTwin's NDVI layer, stored as a LandSurfaceTemperature…, Band 1 of a GDALRaster averaged onto `grid` (NaN outside it / at nodata). (+11 more)

### Community 39 - "Landing Scroll Wiring"
Cohesion: 0.16
Nodes (21): effects, fallBack(), followScrollPlainly(), followScrollWithGsap(), gl, hudFigure, hudHeading, loadScript() (+13 more)

### Community 40 - "Import Page UI"
Cohesion: 0.09
Nodes (22): BBOX_FROM_LEVEL picker level (coarsest wins), Area of Interest bbox map panel, Date Range panel, Import button handler (start_external_import), Import first notice and confirm, initBboxMap(), Import Public Data page, Copernicus openEO credentials panel (+14 more)

### Community 41 - "Map Page Templates"
Cohesion: 0.09
Nodes (23): Legend stack, Map loader + console feed, mainMap.html map page, dashboard_summary.html (population KPI card), map_settings.html (Editable layers / Styles tabs), population_panel.html (Curves-style forecast graph + stats), settings_editable_row.html (editable layer toggle), settings_style_form.html (vector/raster style override form) (+15 more)

### Community 42 - "Population Projections"
Cohesion: 0.18
Nodes (20): _adjust(), annual_growth_rate(), _city_growth_factor(), _city_value(), extrapolate(), normalize_scenario(), population_by_year(), population_curve() (+12 more)

### Community 43 - "File Upload Importer"
Cohesion: 0.15
Nodes (21): atomic, _build_mapping_form(), _cast_value(), _generic_import(), _get_expected_geom_type(), _get_model_spec(), _raster_import(), Read a raster file and optionally reproject it. Returns a dict with raster… (+13 more)

### Community 44 - "PhysicalEnv Views"
Cohesion: 0.16
Nodes (20): busy(), True while edits are queued or being written into an edited COG (this process)., BadRequest, _bbox(), dsm_edited_status(), _dsm_json(), _error(), _existing_json() (+12 more)

### Community 45 - "Example DB Packaging"
Cohesion: 0.19
Nodes (21): _check_target_db(), _connection_args(), _crosstwin_version(), _db_settings(), _django(), dump(), load(), main() (+13 more)

### Community 46 - "OSM Importer"
Cohesion: 0.14
Nodes (11): OSMImporter, Import handler for OpenStreetMap through the Overpass API. The Overpass JSON is…, Overpass QL for `dataset` inside bbox [west, south, east, north] (WGS84)., Leading number of an OSM tag value: '12 m' -> 12.0, '7,5' -> 7.5, '40 ft' ->…, (Multi)polygon of a multipolygon relation from its member ways. A ring may be…, GeoJSON geometry of one Overpass element (out center or out geom)., Overpass elements -> GeoJSON features whose properties are the OSM tags plus…, OSM tags are strings ('12 m'); give numeric model fields a number, or drop the… (+3 more)

### Community 47 - "LST Earth Engine Inputs"
Cohesion: 0.17
Nodes (17): check_download_size(), _collections(), download_bytes(), fetch_scene_inputs(), find_scenes(), GEEError, get_scene(), RuntimeError (+9 more)

### Community 48 - "Indicator Help and Water JS"
Cohesion: 0.14
Nodes (13): Help texts behind the "?" buttons of the indicator dashboards and side panels.…, applyRain(), applyZone(), rainStyle(), zoneStyle(), Info Help (?) Button with inert template, Degree of Urbanisation Threshold Calibration, Infiltration card (SCS Curve Number) (+5 more)

### Community 49 - "Raster COG Export"
Cohesion: 0.14
Nodes (16): Command, BaseCommand, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), get_raster_field_name(), interpolate_raster() (+8 more)

### Community 50 - "KNMI Importer"
Cohesion: 0.14
Nodes (13): datetime, KNMIImporter, load_raster_into_target_model(), Import handler for Sentinel-2 datasets., Look up the real acquisition timestamp of the most recent Sentinel-2 L2A scene…, Fetch raster from Sentinel-2 WCS (e.g., WorldCover)., Fetch processed Sentinel-2 imagery via the Copernicus Data Space Ecosystem's…, KNMI Data Platform (Open Data API v1). Flow: list the newest file of a dataset… (+5 more)

### Community 51 - "Map Edit Journal Signals"
Cohesion: 0.16
Nodes (17): MainmapConfig, AppConfig, journal_created_canyon(), journal_created_dsm_patch(), journal_created_landcover(), journal_rewritten_canyon(), journal_rewritten_dsm_patch(), journal_rewritten_landcover() (+9 more)

### Community 52 - "LST Views"
Cohesion: 0.20
Nodes (18): BadRequest, _bbox(), _date(), _error(), _grid_json(), lst_calculate(), view(), lst_scenes() (+10 more)

### Community 53 - "Thermal Comfort Tool JS"
Cohesion: 0.27
Nodes (17): init(), calculate(), csrfToken(), duration(), fetchMet(), loadInfo(), open(), pause() (+9 more)

### Community 54 - "Raster Styles"
Cohesion: 0.13
Nodes (17): _cog_statistics(), colormap_legend_stops(), discrete_colormap_param(), _lookup_style(), raster_display_name(), _raster_statistics(), raster_style_key(), Colormap + value-range resolution for raster tile rendering. Previously every… (+9 more)

### Community 55 - "Nature Models"
Cohesion: 0.13
Nodes (10): Forests, GreenSpacesQuerySet, Meta, ProtectedArea, ProtectionType, Green spaces of type 'park' (OSM leisure=park, parks drawn in the map editor)., Public park space: parks plus BGT recreation areas (type 'recreatie…')., WaterBodies (+2 more)

### Community 56 - "Interpolated Weather Rasters"
Cohesion: 0.14
Nodes (10): InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:…, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child…, Override in child classes to specify which measurement field to use (+2 more)

### Community 57 - "Map Initialisation"
Cohesion: 0.20
Nodes (16): add3DBuildingEdges(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, BUILDING_EDGE_LAYER_IDS, buildingColorForTool(), changeBasemap(), getSavedCameraState() (+8 more)

### Community 58 - "Housing Chain Equations"
Cohesion: 0.14
Nodes (9): baseline_population(), demand_units(), housed_residents(), what_if_demand(), HouseholdSize, Average number of persons per private household (= per occupied home) of a City…, (population, average_size) from the stored forecast; the current values where…, Record of `year`, else the closest earlier one, else the earliest later one… (+1 more)

### Community 59 - "Population Cascade Signals"
Cohesion: 0.19
Nodes (14): AdministrativeConfig, AppConfig, city_changed(), _defer(), deferred_population_cascade(), district_changed(), _flush_population_cascade(), neighborhood_changed() (+6 more)

### Community 60 - "Layer Cache Versioning"
Cohesion: 0.18
Nodes (15): bump_layer_version(), get_cache(), _label(), layer_version(), Versioned cache keys for data that only changes when rows are written. Every…, caches[alias], falling back to the default cache when the alias isn't…, Current cache version of a model's data. A missing version is seeded with the…, Invalidate every cached response built from these models' rows. (+7 more)

### Community 61 - "Landing Scene Renderer"
Cohesion: 0.21
Nodes (15): createLanding(), applyTier(), crossfadeTo(), dispose(), draw(), frame(), invalidate(), resize() (+7 more)

### Community 62 - "Map Calculation Cards"
Cohesion: 0.14
Nodes (16): Degree of Urbanisation card, Actions menu (import, calculate for this view, year selector), Bottom bar (indicator pills, camera buttons), Degree of Urbanisation card, LST tool card, Thermal Comfort (SOLWEIG) card, SVF tool card, Buildings/Streets -> Canyon_Aspect (StreetCanyon H/W) (+8 more)

### Community 63 - "Map Editor JS"
Cohesion: 0.25
Nodes (13): _attachEditor(), _bindDrawEvents(), _cancelEdit(), _drawModeFor(), _featureUrl(), _hideOriginal(), _openEditorPanel(), _removeDrawControl() (+5 more)

### Community 64 - "Housing Panel JS"
Cohesion: 0.14
Nodes (13): applyZone(), zoneStyle(), housing_indicators.html (Province Housing Dashboard), Pipeline land take (greenfield vs infill), Housing Supply Coverage gauge (supply / demand units), Zoning & Land Value card (HILUCS shares), Average Persons per Home what-if slider, TODO: Unimplemented DAG Edges (+5 more)

### Community 65 - "LST Tool JS"
Cohesion: 0.30
Nodes (14): init(), calculate(), commonParams(), csrfToken(), findScenes(), open(), pct(), readJson() (+6 more)

### Community 66 - "Bulk Import Finalizers"
Cohesion: 0.18
Nodes (14): _fill_tree_heights(), _finalize_landcover(), Batch-import helpers shared by the file-upload and external-data importers. -…, Replays watersupply's soil/land-cover receivers: one extent for the whole batch., Measures the height of bulk-written trees that have none from the DSM (it…, _refresh_freshwater_over(), Tree, measure_missing() (+6 more)

### Community 67 - "Map Settings Models"
Cohesion: 0.15
Nodes (11): EditableLayer, EditBackup, EditBackupRow, LayerStyleOverride, Meta, The state of one object when the backup was made. `original` holds the row as…, A vector layer staff may edit on the map, switched on in the map's settings…, Restore point for what-if edits made with the map editor (core/editing.py,… (+3 more)

### Community 68 - "DSM Patch Overlay"
Cohesion: 0.24
Nodes (13): apply_patches(), _apply_vegetation(), _box(), _building_mask(), burn(), crown_heights(), _difference(), estimate_ground() (+5 more)

### Community 69 - "Heat Panel JS"
Cohesion: 0.22
Nodes (10): anyTouched(), applyZone(), resetWeather(), showValue(), syncResetButton(), weatherInputs(), zoneStyle(), initGauges() (global) (+2 more)

### Community 70 - "Landing Camera Stages"
Cohesion: 0.24
Nodes (14): cameraAt(), CAMERAS, fitFactor(), HOLD_END, LAST_STAGE, layersAt(), locate(), mix() (+6 more)

### Community 71 - "Weather Pill"
Cohesion: 0.32
Nodes (13): applyPrecipEffect(), fmt(), init(), load(), openHeatPanel(), precipKind(), radarLayer(), radarVisible() (+5 more)

### Community 72 - "Model Registry and Upload Form"
Cohesion: 0.14
Nodes (10): build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., GeoUploadForm, get_target_model_choices(), MappingForm, Get choices for target model field., Dynamic form for field mapping. Fields are added dynamically in the view based…, Form for uploading geodata files (GeoJSON or Shapefile). (+2 more)

### Community 73 - "Map Frontend Config"
Cohesion: 0.15
Nodes (13): availableLayers, BASEMAPS, BUILDING_COLOR_BY_TOOL, CONFIG, HIDES_3D_BUILDINGS_APPS, HIDES_3D_BUILDINGS_KEYS, layerVisibility, loadedLayers (+5 more)

### Community 74 - "Map Page Wiring"
Cohesion: 0.20
Nodes (11): actionsMenu, actionsMenuBtn, ADMIN_PANEL_TOOLS, clearTourHighlight(), endTour(), findActiveAdminTool(), positionActionsMenu(), refreshActivePanel() (+3 more)

### Community 75 - "SVF Tool JS"
Cohesion: 0.30
Nodes (12): init(), calculate(), csrfToken(), loadInfo(), open(), params(), readJson(), refreshButton() (+4 more)

### Community 76 - "Postgres Check Tool"
Cohesion: 0.32
Nodes (13): _connect(), _create_extensions_help(), _diagnose_connection_error(), _install_postgis_help(), _install_postgres_help(), main(), _postgres_binaries(), Check that PostgreSQL is reachable with the .env settings and has PostGIS. Run… (+5 more)

### Community 77 - "Degree of Urbanisation Views"
Cohesion: 0.24
Nodes (10): True while a background refresh is queued or running (this process)., rebuild(), refreshing(), status(), degurba_calculate(), degurba_info(), _json(), require_GET (+2 more)

### Community 78 - "Builtup Models"
Cohesion: 0.20
Nodes (6): bag_usage_labels(), BAG gebruiksdoel as a list of labels (Building.BAG_USAGE_FUNCTIONS). WFS…, Degree of Urbanisation of an admin unit (DAG node Degree_Urbanisation): its…, DAG edges: Total_Population -> Degree_Urbanisation, Buildings ->…, Set every derived field from the population per class and the urban area (m²)., Urbanisation

### Community 79 - "Landing Page Docs"
Cohesion: 0.21
Nodes (10): Scroll-driven Three.js City Landing, Landing stages (overview to what-if editing), tools/check_postgres.py PostGIS check, CrossTwin digital twin platform, README DAG coverage count (31 of 103, outdated), DPSIR framework (core/DAG.dot), Gohlke GDAL wheel on Windows, Two-server setup (Django + TiTiler) (+2 more)

### Community 80 - "Info Popover"
Cohesion: 0.23
Nodes (8): fill(), place(), popover(), show(), Calculate-for-this-view Tools (LST, SVF, SOLWEIG, DEGURBA), CrossTwin README, External Data Sources (PDOK, CBS, KNMI, BIS, OSM, Sentinel-2, GEE, Klimaateffectatlas), GeoJSON Layer Cache (2-minute TTL)

### Community 81 - "Population Dock Panels"
Cohesion: 0.32
Nodes (10): applyPopulationControls(), initPopulationHover(), loadDashboardPopulation(), loadPopulationPanel(), populationRequestParams(), refreshPopulationViews(), resetPopulationControls(), showDashboardSummary() (+2 more)

### Community 82 - "SOLWEIG Raster Inputs"
Cohesion: 0.23
Nodes (10): build(), _footprints(), Inputs, landcover_grid(), CrossTwin layers -> the SOLWEIG input rasters of one view, on one grid. window…, SOLWEIG land-cover classes on the grid, or None without land-cover polygons., The input arrays of plan `p` (see the module docstring). Returns Inputs with…, Write the arrays as SOLWEIG's single tile 0_0 (<dir>/<Name>/<Name>_0_0.tif).… (+2 more)

### Community 83 - "Weather Raster Views"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 84 - "DEGURBA Classifier"
Cohesion: 0.44
Nodes (10): _border(), classify(), _component_sums(), _components(), density(), _fill_holes(), _keep(), _smooth() (+2 more)

### Community 85 - "Builtup Indicator Cards"
Cohesion: 0.18
Nodes (11): Building Stock card, Building Type Mix card, Built-up Coverage gauge (FAR), Construction Period card, Built-up indicators grid partial, info_help template tag usage, Park Area per Inhabitant gauge (WHO thresholds), Street Network density card (+3 more)

### Community 86 - "Degree of Urbanisation Tool JS"
Cohesion: 0.42
Nodes (10): init(), afterEdit(), calculate(), csrfToken(), loadInfo(), open(), readJson(), render() (+2 more)

### Community 87 - "Sky View Factor"
Cohesion: 0.36
Nodes (10): calculate_svf(), existing_svf(), horizon_shift_vector(), replace_covered(), save_svf(), sky_view_factor(), _storage_box(), _svf_block() (+2 more)

### Community 88 - "Meteorology Model"
Cohesion: 0.18
Nodes (6): Meta, Meteorology, Interpolated wind speed raster layer, Time-series weather measurements from stations. `period` says what a row's…, WeatherStation, WindSpeedRaster

### Community 89 - "Bulk Writer"
Cohesion: 0.27
Nodes (4): BulkWriter, Collects rows and writes them `batch_size` at a time. With a unique field, rows…, A writer when `Model` can safely be bulk-written, otherwise None (use the row…, Write what is left, replay the skipped signals and invalidate the layer cache.

### Community 90 - "Feature Editor Form"
Cohesion: 0.22
Nodes (10): Layers panel, No-backup warning (permanent changes), Delete confirmation, Feature editor side-panel form, deferred_cascades bulk import batching, Key conventions (SRID, save(), DO_NOTHING, update(), no inline scripts), Signal-driven computation, Urban-fabric buffer around editor buildings (urbanize_around / release_ring) (+2 more)

### Community 91 - "Green Area Land Cover"
Cohesion: 0.22
Nodes (10): Undo green_area() for an editor green space that moved or was deleted…, release_green_area(), _city_of(), _green(), green_space_deleted(), green_space_saved(), move(), City of a building: through its neighborhood (Building.save() sets it), else… (+2 more)

### Community 92 - "Population Projection Model"
Cohesion: 0.22
Nodes (3): PopulationProjection, Projected total population of a City for one year and forecast variant. Loaded…, Scenario

### Community 93 - "Background Worker"
Cohesion: 0.22
Nodes (4): BackgroundWorker, Coalescing background workers for derived data that a map edit must not wait…, Queue `item`; start the thread when it is idle., True while items are queued or a batch is running (this process).

### Community 94 - "Earth Engine Auth"
Cohesion: 0.28
Nodes (5): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE for the given Cloud project. `ee.Authenticate()` is a one-time-…, initialize(), Authenticate once per process, like the importer's GEE sources.

### Community 95 - "Builtup Dashboard JS"
Cohesion: 0.25
Nodes (5): builtup_indicators.html (standalone dashboard), Additional Park Area slider (green_added_ha), Three-layer indicator dashboard pattern, MOCK_DATA fallback, Dashboard backlog (Energy, nature dashboards)

### Community 96 - "Console Feed JS"
Cohesion: 0.50
Nodes (7): begin(), busy(), end(), poll(), render(), schedule(), settle()

### Community 97 - "Map Settings JS"
Cohesion: 0.46
Nodes (6): applyEditable(), applyStyle(), catalogEntry(), init(), preview(), readdLayer()

### Community 98 - "Indicator Help Tag"
Cohesion: 0.25
Nodes (7): friendly_equation(), info_help(), ``{% info_help "<key>" %}`` renders a card's "?" button with its help entry…, Escape an equation and render its fractions and superscripts as HTML., The "?" button of card `key`; an unknown key renders the button with only its…, filter, inclusion_tag

### Community 99 - "Version Labels"
Cohesion: 0.32
Nodes (6): _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. Counts half the commits:…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 100 - "HILUCS Land Use Codes"
Cohesion: 0.29
Nodes (7): hilucs_lookup(), hilucs_q(), parse_hilucs_href(), INSPIRE HILUCS (Hierarchical INSPIRE Land Use Classification System) helpers. A…, (code, label) of a HILUCS URI, or None if it is not one. The label is spelled…, __fk_lookup__ parser for HILUCS URIs (importer/external_data.py): returns…, Q matching rows whose HILUCS FK `field` is one of `codes` or below it in the…

### Community 101 - "Architecture Export"
Cohesion: 0.43
Nodes (7): browser(), main(), page(), Export docs/architecture/latest/*.svg to PNG and PDF with headless Chrome/Edge.…, One page per SVG, each page sized to its diagram (named @page rules)., run(), size()

### Community 102 - "Non-Revenue Water"
Cohesion: 0.25
Nodes (4): LossesChoices, LossesTypes, NonRevenueWater, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 103 - "Street Canyon Equations"
Cohesion: 0.43
Nodes (5): aspect_ratio(), canyon(), canyon_height(), canyon_width(), classify_unit()

### Community 104 - "GEE Importer"
Cohesion: 0.38
Nodes (5): GEEImporter, prepare(), Import handler for Google Earth Engine datasets. Optional catalog keys on a GEE…, Function Image -> Image selecting (or deriving) the entry's band., Export raster from GEE to local GeoTIFF.

### Community 105 - "Layer and Tree Styles"
Cohesion: 0.33
Nodes (5): Map styling of the vector layers: Mapbox GL style layers, legend entries and…, build_tree_style(), Map style of nature.Tree: green dots when zoomed out, a 3D glTF tree per point…, style_layers for nature.Tree. The circle layer comes first: it is the click…, _uniform()

### Community 106 - "Fill Tree Heights Command"
Cohesion: 0.33
Nodes (3): BaseCommand, Command, Measure the height of stored trees that have none from the DSM…

### Community 107 - "DB Stats Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Show the most expensive SQL statements recorded by pg_stat_statements…

### Community 109 - "Deferred Cascades"
Cohesion: 0.33
Nodes (5): deferred_cascades(), Run the administrative population cascade, the land-cover urban-area recompute,…, _heights_after_dsm(), Daily precipitation (RH), Makkink reference ET (EV24), mean wind (FG),…, After a DSM import: measure the stored buildings under it that have no height…

### Community 110 - "Land Cover Styles"
Cohesion: 0.40
Nodes (5): build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…

### Community 111 - "Environmental Costs"
Cohesion: 0.33
Nodes (3): EnvironmentalCosts, The most recent cost record (the model has no province/year), or None., DAG edges: Available_FW -> Total_Extraction Total_Extraction ->…

### Community 112 - "Supply Security Equations"
Cohesion: 0.40
Nodes (5): service_time_hours(), supply_security_pct(), DAG edges: Total_Water_Demand -> Supply_Security Total_Water_Prod ->…, _build_indicators(), Pure function: takes DB data dict, returns indicators dict.

### Community 113 - "Upload Templates"
Cohesion: 0.50
Nodes (5): model_selector.js initModelSelector, FieldMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 114 - "App Icon 512"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 115 - "Energy Models"
Cohesion: 0.40
Nodes (3): ElectricityCost, EnergyEfficiencyLabels, Meta

### Community 116 - "Importer Geometry Utils"
Cohesion: 0.40
Nodes (4): gpd_read_any(), Return `geom` expressed in settings.COORDINATE_SYSTEM, the only CRS geometries…, Read an uploaded file (GeoJSON, Shapefile zip, etc.) into a GeoDataFrame.…, to_storage_srid()

### Community 120 - "Admin Unit Point Lookup"
Cohesion: 0.50
Nodes (4): Built once per process: creating a GDAL/PROJ transformation is the slow part of…, Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), _wgs84_to_storage()

### Community 121 - "App Icon 192"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 124 - "CBS Importer"
Cohesion: 0.50
Nodes (3): CBSImporter, Import handler for CBS StatLine OData datasets., Fetch column definitions and units for a CBS table. Useful for building field…

### Community 125 - "FK Lookup Resolution"
Cohesion: 0.50
Nodes (3): Resolve FK by name (case-insensitive) or id. Works for City-like foreign keys.…, _resolve_fk(), The material an imported value names: its code, its name (case-insensitive;…

### Community 126 - "Manage Entry Point"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 127 - "Style Suggestions"
Cohesion: 0.50
Nodes (4): Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono)

### Community 131 - "Apple Touch Icon"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 132 - "Favicon 16"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 133 - "Favicon 32"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

## Knowledge Gaps
- **130 isolated node(s):** `WMSLayerAdmin`, `HILUCSLandUseAdmin`, `LandCoverClassesAdmin`, `SoilTypeAdmin`, `SurfaceMaterialPropertiesAdmin` (+125 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 982 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **31 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `City` connect `Administrative Units` to `Water Supply Models and Signals`, `PhysicalEnv Signals and DSM`, `Green Spaces and Heat Indicators`, `Water Supply Indicators`, `Water Supply Chain Equations`, `Urban Heat Raster Models`, `Land Cover and Albedo`, `Urbanisation Grid Refresh`, `Housing Signals and Property`, `LST Grid`, `Urbanisation Dashboard and What-if`, `External Data Enrichment`, `Population Projections`, `File Upload Importer`, `KNMI Importer`, `Nature Models`, `Population Cascade Signals`, `Bulk Import Finalizers`, `Green Area Land Cover`, `Population Projection Model`, `CBS Importer`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `Building` connect `Builtup Indicators` to `Builtup Signals and Canyons`, `Housing Models and Admin`, `PhysicalEnv Signals and DSM`, `DSM Patch Overlay`, `External Data Enrichment`, `Green Spaces and Heat Indicators`, `Builtup Models`, `Administrative Units`, `Urbanisation Grid Refresh`, `Building Heights and SVF Inputs`, `SOLWEIG Raster Inputs`, `PhysicalEnv Admin and Models`, `Urbanisation Dashboard and What-if`, `Housing Indicators`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `deferred_cascades()` connect `Deferred Cascades` to `Builtup Signals and Canyons`, `Water Supply Models and Signals`, `Bulk Import Finalizers`, `External Data Enrichment`, `Map Editing Backup`, `File Upload Importer`, `Urbanisation Grid Refresh`, `Housing Signals and Property`, `External Data Import Core`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Are the 35 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Building` (e.g. with `_sql()` and `calculate_building_age()`) actually correct?**
  _`Building` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `LandCoverVector` (e.g. with `landcover_shares()` and `_landcover_rows_created()`) actually correct?**
  _`LandCoverVector` has 17 INFERRED edges - model-reasoned connections that need verification._