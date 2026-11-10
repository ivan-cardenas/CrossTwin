# Graph Report - CrossTwin  (2026-11-10)

## Corpus Check
- 86 files · ~217,716 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2644 nodes · 5117 edges · 148 communities (117 shown, 19 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 423 edges (avg confidence: 0.92)
- Token cost: 111,136 input · 0 output

## Community Hubs (Navigation)
- Administrative Units & Population
- Land Cover Rings & Albedo
- physicalEnv Signals & Editor Hooks
- Map Editing Backup/Restore
- Housing Models & Signals
- Water Supply Signals
- Map Layers Frontend
- Water Supply Calculations
- Built-up Signals (Canyon, DEGURBA)
- Urban Heat Indicators
- Weather Raster Models
- DEGURBA Population Allocation
- Water Chain & Models
- File Upload Importer
- Map Views & Layer Catalog
- physicalEnv Models & Admin
- Landing City Builder
- Sky View Factor
- Live Weather API
- Layer Style Overrides
- Street Canyon Inputs
- LST Grid & Pipeline
- Built-up Calculations
- Console Feed Backend
- SOLWEIG Views
- SOLWEIG Pipeline & PET
- External Import Dispatch
- Architecture Diagrams
- SOLWEIG Meteorology
- SOLWEIG Tool Frontend
- SCS Infiltration & Recharge
- Urban Heat Raster Models
- Map Settings Views
- GeoJSON Feature Import
- Landing City Plan
- DSM Patches
- KNMI Daily Data
- COG Export
- Model Registry & Raster Styles
- Landing Page Wiring
- Import Console & Catalog
- SMW LST Equations
- Example DB Packaging
- Earth Engine LST Inputs
- Tree Heights from DSM
- Population Forecast Chart
- DEGURBA Classifier
- Spatial Parent Index
- Nature Models
- SVF Views
- LST Views
- Map Init & 3D Buildings
- README Architecture Concepts
- Landing Scene Renderer
- OSM Importer
- Map Editing Models
- Impervious Fractions & SOLWEIG Inputs
- Editing Frontend
- Landing Scroll Stages
- LST Tool Frontend
- Weather Pill
- External Data Import UI
- LST Calculation
- Water Demand & Consumption
- Admin Unit Lookup & Population
- Built-up Chain Equations
- Built-up Model save() Logic
- DEGURBA Rebuild
- Frontend Config
- Map Page Template & Tools
- Map Page Wiring & Tour
- Postgres Check Tool
- Layer Cache Versioning
- Indicator Help Content
- SVF Tool Frontend
- Housing Calculations
- Housing Dashboard & Gaps
- Population Dock Panels
- Housing Chain Equations
- Heat Dashboard Templates
- DEGURBA Tool Frontend
- Bulk Writer
- Housing Views
- Built-up Dashboard Templates
- GEE Auth
- KNMI Importer
- Weather Stations & Meteorology
- Console Feed Frontend
- Heat Dashboard JS
- Map Settings Frontend
- Info Help Template Tag
- Version Info
- Deferred Cascades & CBS
- Map Settings Templates
- HILUCS Codelist
- DSM Edits & Thermal Runs
- Architecture Export
- LST Command & Window
- Housing Dashboard Panel
- GEE Importer
- Non-Revenue Water
- Point-in-Unit Lookup
- DB Stats Command
- Query Stats Middleware
- Info Popover
- Environmental Costs
- Zoning Areas
- Upload Templates
- App Icon 512
- Water Dashboard JS
- Energy Models
- WMS Legend Lookup
- Built-up App Config
- App Icon 192
- Django Settings
- Housing App Config
- Signed Int URL Converter
- manage.py
- physicalEnv App Config
- Style Suggestion Design System
- Water App Config
- Weather App Config
- Apple Touch Icon
- Favicon 16
- Favicon 32
- Energy App Config
- Importer App Config
- Nature App Config
- Request Profiler
- Urban Heat App Config
- ASGI Config
- WSGI Config
- Mortgage Indicators
- require_http_methods
- pyproject Package
- Style Suggestion Doc

## God Nodes (most connected - your core abstractions)
1. `City` - 58 edges
2. `Neighborhood` - 44 edges
3. `Building` - 31 edges
4. `LandCoverVector` - 31 edges
5. `Province` - 30 edges
6. `buildCity()` - 23 edges
7. `District` - 23 edges
8. `import_dataset()` - 21 edges
9. `calculate()` - 20 edges
10. `calculate_lst()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Weather What-if Sliders (ta_c, rh_pct, wind_ms, kdown_wm2)` --semantically_similar_to--> `Rain Event + Groundwater Season What-if`  [INFERRED] [semantically similar]
  urban_heat/templates/urban_heat/partials/whatif_controls.html → watersupply/templates/watersupply/partials/rain_slider.html
- `ElectricityCost` --uses--> `Province`  [INFERRED]
  Energy/models.py → administrative/models.py
- `HouseholdSize` --uses--> `PopulationProjection`  [INFERRED]
  housing/models.py → administrative/models.py
- `NeighborhoodHeat` --uses--> `Neighborhood`  [INFERRED]
  urban_heat/models.py → administrative/models.py
- `Command` --uses--> `City`  [INFERRED]
  urban_heat/management/commands/calculate_lst.py → administrative/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **External import area-of-interest picker flow** — importer_templates_importer_external_data_updateui, importer_templates_importer_external_data_pickerlevelfor, importer_templates_importer_external_data_setpickerlevel, importer_templates_importer_external_data_loadpickerlevel, importer_templates_importer_external_data_togglearea, importer_templates_importer_external_data_unionbbox [EXTRACTED 1.00]
- **Map editing UI (feature form, backup bar, Editing.js, core.editing)** — mainmap_templates_mainmap_partials_feature_form, mainmap_templates_mainmap_partials_backup_bar, core_static_js_editing, core_editing [EXTRACTED 1.00]
- **Map settings panel (editable layers + style overrides)** — mainmap_templates_mainmap_settings_card, mainmap_templates_mainmap_partials_map_settings, mainmap_templates_mainmap_partials_settings_editable_row, mainmap_templates_mainmap_partials_settings_style_form, core_static_js_mapsettings [EXTRACTED 1.00]
- **CrossTwin icon composition: physical city, digital wireframe, orbit ring** — core_static_ico_android_chrome_512x512_isometric_city_block, core_static_ico_android_chrome_512x512_cyan_wireframe_grid, core_static_ico_android_chrome_512x512_orbit_ring [INFERRED 0.85]
- **Landing fallback sketch generation flow** — core_static_js_landing_plan, tools_landing_fallback_svg, core_static_img_landing_city_blueprint, mainmap_templates_mainmap_landing [INFERRED 0.85]
- **Domain indicator side panels sharing grid + JS pattern** — watersupply_templates_watersupply_partials_indicators_panel, housing_templates_housing_partials_indicators_panel, builtup_templates_builtup_partials_indicators_panel, urban_heat_templates_urban_heat_partials_indicators_panel, readme_indicator_dashboard_pattern [INFERRED 0.85]
- **Info help popover flow** — templates_partials_info_btn, core_indicator_help, core_static_js_info_popover, templates_indicators_base [EXTRACTED 1.00]

## Communities (148 total, 19 thin omitted)

### Community 0 - "Administrative Units & Population"
Cohesion: 0.05
Nodes (59): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, cities_within(), city_of(), neighborhoods_within(), province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any… (+51 more)

### Community 1 - "Land Cover Rings & Albedo"
Cohesion: 0.04
Nodes (69): GEOSGeometry, calculate_pipeline_land_take(), Land cover the housing pipeline would build on (dashboard only, writes…, _finalize_landcover(), Batch-import helpers shared by the file-upload and external-data importers. -…, Replays watersupply's soil/land-cover receivers: one extent for the whole batch., _refresh_freshwater_over(), ensure_multipolygon() (+61 more)

### Community 2 - "physicalEnv Signals & Editor Hooks"
Cohesion: 0.05
Nodes (74): Park, is_editor_change(), is_restoring(), True inside a map-editor save or delete. Receivers that must react to a user's…, True while restore_backup() runs. Receivers that undo an edit's side effects on…, building_height(), Record an editor change of one building. before: its footprint before this edit…, Height above ground of a builtup.Building: height_m, else floors x… (+66 more)

### Community 3 - "Map Editing Backup/Restore"
Cohesion: 0.06
Nodes (62): active_backup(), backup(), _backup_bar(), backup_discard(), backup_restore(), _build_form(), _check_constraints(), _editable_model() (+54 more)

### Community 4 - "Housing Models & Signals"
Cohesion: 0.05
Nodes (43): CentralBankPolicy, CreditSupplyConditions, HouseholdSize, HousePriceIndex, HousingAffordability, HousingProject, HousingSupplyDemand, Meta (+35 more)

### Community 5 - "Water Supply Signals"
Cohesion: 0.07
Nodes (59): AvailableFreshWater, TotalWaterProduction, bbox_polygon(), _cities_in_watersheds(), city_population_cascaded(), city_saved(), consumption_saved(), daily_balance_imported() (+51 more)

### Community 6 - "Map Layers Frontend"
Cohesion: 0.07
Nodes (56): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+48 more)

### Community 7 - "Water Supply Calculations"
Cohesion: 0.07
Nodes (50): active_wells_with_watershed(), calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage(), calculate_drought_area(), calculate_energy_consumption(), calculate_infiltration() (+42 more)

### Community 8 - "Built-up Signals (Canyon, DEGURBA)"
Cohesion: 0.07
Nodes (54): Property, building_canyon_deleted(), building_canyon_presave(), building_canyon_saved(), building_urbanisation_deleted(), building_urbanisation_presave(), building_urbanisation_saved(), _connect_landcover_created() (+46 more)

### Community 9 - "Urban Heat Indicators"
Cohesion: 0.07
Nodes (51): calculate_canyon_aspect(), calculate_nbs_coverage(), calculate_urban_morphology(), calculate_vegetation_coverage(), classify_pet(), classify_utci(), classify_wbgt(), get_latest_meteorology() (+43 more)

### Community 10 - "Weather Raster Models"
Cohesion: 0.05
Nodes (31): HumidityRaster, InterpolatedRasterBase, Meta, PrecipitationRaster, Calculate bounds polygon from the raster's extent, Determine bounds for interpolation, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:… (+23 more)

### Community 11 - "DEGURBA Population Allocation"
Cohesion: 0.08
Nodes (48): PopulationAllocation, One neighborhood's share of one grid cell: the bookkeeping of the dasymetric…, allocate(), _bump(), cell_code(), _cells_over(), _class_population_sql(), classify_grid() (+40 more)

### Community 12 - "Water Chain & Models"
Cohesion: 0.06
Nodes (25): WMSLayerAdmin, consumption_m3_yr(), demand_m3_d(), Daily water demand in m3/day: L/person/day / 1000 * persons., Yearly water consumption in m3/year., Production as a percentage of demand (0 when there is no demand)., Hours of supply per day: full service when production covers demand, otherwise…, service_time_hours() (+17 more)

### Community 13 - "File Upload Importer"
Cohesion: 0.06
Nodes (38): atomic, get_area(), Returns the area in square kilometers., GeoUploadForm, get_target_model_choices(), MappingForm, Get choices for target model field., Dynamic form for field mapping. Fields are added dynamically in the view based… (+30 more)

### Community 14 - "Map Views & Layer Catalog"
Cohesion: 0.07
Nodes (43): editable_keys(), Registry keys of the layers switched on in the settings panel (one query)., raster_display_name(), Build a display name matching the legend label plus the acquisition date as MM-…, available_layers(), dashboard_summary(), _display_field(), _extract_unit() (+35 more)

### Community 15 - "physicalEnv Models & Admin"
Cohesion: 0.06
Nodes (28): HILUCSLandUseAdmin, LandCoverClassesAdmin, SoilTypeAdmin, SurfaceMaterialPropertiesAdmin, DigitalElevationModelWMS, DigitalSurfaceModelWMS, DSMVegetationPatch, GroundwaterDepth (+20 more)

### Community 16 - "Landing City Builder"
Cohesion: 0.10
Nodes (35): alongPath(), buildCity(), update(), geometryFrom(), HEAT_STOPS, heatColor(), heatMaterial(), HOUSE_COLORS (+27 more)

### Community 17 - "Sky View Factor"
Cohesion: 0.09
Nodes (39): _area(), calculate_svf(), _db_raster(), dsm_extent(), dsm_for_view(), existing_svf(), horizon_shift_vector(), _intersection() (+31 more)

### Community 18 - "Live Weather API"
Cohesion: 0.08
Nodes (36): RuntimeError, current_weather(), current_weather_or_none(), describe(), enabled(), LiveWeatherError, parse_current(), Live weather at a point from Open-Meteo's forecast API (current conditions, a… (+28 more)

### Community 19 - "Layer Style Overrides"
Cohesion: 0.08
Nodes (33): Form fields of a vector style: default value, current value, input kind., _vector_fields(), build_landcover_style_and_legend(), get_landcover_color(), Color scheme for LandCoverVector.land_cover_type…, Resolve a stable hex color for a LandCoverClasses.class_name value., Build a Mapbox `match` fill-color expression plus a legend for every class_name…, Map styling of the vector layers: Mapbox GL style layers, legend entries and… (+25 more)

### Community 20 - "Street Canyon Inputs"
Cohesion: 0.09
Nodes (26): Inputs of the street canyon, for many streets in one SQL statement. Each street…, {street id: {h_left_m, h_right_m, w_facade_m, n_left, n_right}}; streets…, Ids of the streets whose side buffers can reach any of `geoms` (footprints,…, _sql(), street_inputs(), streets_near(), Building, BuildingEnergyLabel (+18 more)

### Community 21 - "LST Grid & Pipeline"
Cohesion: 0.10
Nodes (24): datetime, LandCoverRaster, Grid, The one raster grid every LST input is put on before the equations run., Smallest grid with corners on multiples of `resolution` that covers the extent., Affine in Earth Engine's order: [xScale, xShear, xOffset, yShear, yScale,…, [west, south, east, north] in EPSG:4326, for filtering image collections., North-up grid: (x0, y0) is the top-left corner, cells are `resolution` m square. (+16 more)

### Community 22 - "Built-up Calculations"
Cohesion: 0.12
Nodes (29): calculate_building_age(), calculate_building_mix(), calculate_building_stock(), calculate_facilities(), calculate_green_space(), calculate_street_network(), _pct(), Distribution of construction years over the Dutch typology periods. DAG edges:… (+21 more)

### Community 23 - "Console Feed Backend"
Cohesion: 0.07
Nodes (21): CoreConfig, AppConfig, add(), clear(), FeedHandler, install(), NotDjango, Console feed: the server's own progress lines, shown under the map loader. The… (+13 more)

### Community 24 - "SOLWEIG Views"
Cohesion: 0.15
Nodes (31): (west, south, east, north) in degrees -> (minx, miny, maxx, maxy) in the…, wgs84_to_storage(), ValueError, SolweigError, centre(), Status of a run for the map tool; a run left 'running' by a dead process reads…, run_state(), BadRequest (+23 more)

### Community 25 - "SOLWEIG Pipeline & PET"
Cohesion: 0.09
Nodes (29): _storage_box(), PET, Physiological Equivalent Temperature (PET) measurements, plan(), What a run over `view` (storage CRS) would read: the DSM, the covered view, the…, The UMEP met file of one run: the hour before and the analysed hour, both with…, write_umep(), calculate() (+21 more)

### Community 26 - "External Import Dispatch"
Cohesion: 0.10
Nodes (20): import_dataset(), ImportResult, load_raster_into_target_model(), PDOKImporter, Import handler for PDOK datasets - imports directly to Django models., Split [min_v, max_v] into evenly-sized segments, each no larger than…, Fetch raster data from PDOK WCS service, tiling the request when the area would…, Register a WMS layer by creating/updating its row in the target WMS model. This… (+12 more)

### Community 27 - "Architecture Diagrams"
Cohesion: 0.11
Nodes (19): apps(), Diagram, editing(), importer(), infiltration(), on_demand(), overview(), raster() (+11 more)

### Community 28 - "SOLWEIG Meteorology"
Cohesion: 0.09
Nodes (24): _era5_day(), era5_day_from_values(), era5_from_values(), era5_hourly(), knmi_day_values(), _knmi_hour(), knmi_hourly(), Met (+16 more)

### Community 29 - "SOLWEIG Tool Frontend"
Cohesion: 0.15
Nodes (25): init(), calculate(), csrfToken(), duration(), fetchMet(), loadInfo(), open(), pause() (+17 more)

### Community 30 - "SCS Infiltration & Recharge"
Cohesion: 0.09
Nodes (24): curve_number(), group_rate_mm_h(), infiltration_coefficient(), TR-55 curve number for a land-cover class name and soil group, or None if…, SCS direct runoff Q (mm) of a rain depth P (mm): S = 25400 / CN - 254 potential…, Share of the rain that does not run off, (P - Q) / P, by the SCS method., Area-weighted final infiltration rate (mm/h) of a set of soil-group x land-…, Area-weighted SCS result for a set of soil-group x land-cover pieces.… (+16 more)

### Community 31 - "Urban Heat Raster Models"
Cohesion: 0.07
Nodes (17): MeanRadiantTemperature, Meta, NatureBasedSolutionPoint, NatureBasedSolutionPolygon, NeighborhoodHeat, Surface Urban Heat Island Intensity (SUHII)) measurements, Nature-Based Solutions (NBS) for urban heat mitigation, Nature-Based Solutions (NBS) for urban heat mitigation (+9 more)

### Community 32 - "Map Settings Views"
Cohesion: 0.13
Nodes (25): enable_blocker(), Why the layer `key` may not be switched on, or None when it may. A model whose…, _colormaps(), _editable_row(), _forbidden(), _layer_name(), map_settings(), _parse_target() (+17 more)

### Community 33 - "GeoJSON Feature Import"
Cohesion: 0.11
Nodes (22): Exception, _enrich_rows(), get_model_class(), _import_feature_rows(), _import_geojson_features(), _ImportBlocked, _keep_existing(), _prepare_features() (+14 more)

### Community 34 - "Landing City Plan"
Cohesion: 0.17
Nodes (22): city_blueprint.svg (landing no-WebGL city sketch), blueprintSegments(), boundaries(), buildPlan(), canalX(), circleLine(), crossing(), inDisc() (+14 more)

### Community 35 - "DSM Patches"
Cohesion: 0.14
Nodes (22): apply_patches(), _apply_vegetation(), _box(), _building_mask(), burn(), crown_heights(), _difference(), estimate_ground() (+14 more)

### Community 36 - "KNMI Daily Data"
Cohesion: 0.12
Nodes (24): daily_values(), distance_km(), fetch_daily(), KNMIError, parse_knmi(), ValueError, radiation_w_m2(), rain_mm() (+16 more)

### Community 37 - "COG Export"
Cohesion: 0.11
Nodes (20): Command, BaseCommand, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), get_raster_field_name(), interpolate_raster() (+12 more)

### Community 38 - "Model Registry & Raster Styles"
Cohesion: 0.09
Nodes (20): build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., get_raster_info(), get_raster_tiles(), Return raster metadata including bounds., Return TiTiler tile URL for a given raster layer., _cog_statistics(), colormap_legend_stops() (+12 more)

### Community 39 - "Landing Page Wiring"
Cohesion: 0.14
Nodes (21): effects, fallBack(), followScrollPlainly(), followScrollWithGsap(), gl, hudFigure, hudHeading, loadScript() (+13 more)

### Community 40 - "Import Console & Catalog"
Cohesion: 0.12
Nodes (17): Console progress lines for the importers (upload wizard, external import), so…, One console line. Forced to ASCII: a character the Windows cp1252 console can't…, say(), get_catalog_grouped(), _kea_building(), _kea_neighborhood(), Mapping for a per-buurt KEA layer: one row per stored neighborhood, keyed on…, Return the catalog grouped by category. Structure: { category: [datasets] }… (+9 more)

### Community 41 - "SMW LST Equations"
Cohesion: 0.13
Nodes (21): Constants of the Statistical Mono-Window (SMW) LST algorithm for Landsat 8/9.…, apply_qa_emissivity(), bare_ground_emissivity(), _bit_set(), cloud_mask(), fractional_vegetation_cover(), land_surface_temperature(), Statistical Mono-Window (SMW) land surface temperature: the equations. Pure… (+13 more)

### Community 42 - "Example DB Packaging"
Cohesion: 0.19
Nodes (21): _check_target_db(), _connection_args(), _crosstwin_version(), _db_settings(), _django(), dump(), load(), main() (+13 more)

### Community 43 - "Earth Engine LST Inputs"
Cohesion: 0.17
Nodes (17): check_download_size(), _collections(), download_bytes(), fetch_scene_inputs(), find_scenes(), GEEError, get_scene(), RuntimeError (+9 more)

### Community 44 - "Tree Heights from DSM"
Cohesion: 0.13
Nodes (15): BaseCommand, _fill_tree_heights(), Measures the height of bulk-written trees that have none from the DSM (it…, Command, Measure the height of stored trees that have none from the DSM…, DigitalSurfaceModel, _covering(), _dsm_extents() (+7 more)

### Community 45 - "Population Forecast Chart"
Cohesion: 0.16
Nodes (19): band_d(), build_population_chart(), pts(), x_of(), y_of(), _fmt(), monotone_segments(), nice_step() (+11 more)

### Community 46 - "DEGURBA Classifier"
Cohesion: 0.19
Nodes (18): _border(), classify(), _component_sums(), _components(), density(), _fill_holes(), _keep(), Degree of Urbanisation (DEGURBA) grid classification: pure numpy/scipy, no ORM.… (+10 more)

### Community 47 - "Spatial Parent Index"
Cohesion: 0.12
Nodes (9): Point-in-polygon lookup against a fixed set of parent rows. Each parent's…, Load only what the lookup needs: pk, geom and any attributes read off the…, The parent containing `geom`'s representative point, or None., SpatialParentIndex, _gml_multipolygon(), _import_atom_gml_features(), WGS84 MultiPolygon of every gml:Polygon below `elem` (None if there are none,…, Stream an INSPIRE Planned Land Use GML file over HTTP and import the… (+1 more)

### Community 48 - "Nature Models"
Cohesion: 0.14
Nodes (9): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, Tree, WaterBodies, WaterWaysLN (+1 more)

### Community 49 - "SVF Views"
Cohesion: 0.19
Nodes (17): BadRequest, _bbox(), _dsm_json(), _error(), _existing_json(), _number(), _params(), require_GET (+9 more)

### Community 50 - "LST Views"
Cohesion: 0.22
Nodes (18): BadRequest, _bbox(), _date(), _error(), _grid_json(), lst_calculate(), view(), lst_scenes() (+10 more)

### Community 51 - "Map Init & 3D Buildings"
Cohesion: 0.20
Nodes (16): add3DBuildingEdges(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, BUILDING_EDGE_LAYER_IDS, buildingColorForTool(), changeBasemap(), getSavedCameraState() (+8 more)

### Community 52 - "README Architecture Concepts"
Cohesion: 0.14
Nodes (18): CrossTwin README, EPSG:28992 RD New Default CRS, Example Data Package (crosstwin_example_data.zip), External Data Sources (PDOK, CBS, KNMI, BIS, OSM, Sentinel-2, GEE, Klimaateffectatlas), GeoJSON Layer Cache (2-minute TTL), Viewport Loading of Large Layers (>=5000 features), Importer System (file upload + external catalog), Model Registry (MODEL/VECTOR/RASTER/WMS) (+10 more)

### Community 53 - "Landing Scene Renderer"
Cohesion: 0.21
Nodes (15): createLanding(), applyTier(), crossfadeTo(), dispose(), draw(), frame(), invalidate(), resize() (+7 more)

### Community 54 - "OSM Importer"
Cohesion: 0.17
Nodes (9): OSMImporter, Import handler for OpenStreetMap through the Overpass API. The Overpass JSON is…, Overpass QL for `dataset` inside bbox [west, south, east, north] (WGS84)., Leading number of an OSM tag value: '12 m' -> 12.0, '7,5' -> 7.5, '40 ft' ->…, (Multi)polygon of a multipolygon relation from its member ways. A ring may be…, GeoJSON geometry of one Overpass element (out center or out geom)., Overpass elements -> GeoJSON features whose properties are the OSM tags plus…, OSM tags are strings ('12 m'); give numeric model fields a number, or drop the… (+1 more)

### Community 55 - "Map Editing Models"
Cohesion: 0.15
Nodes (11): EditableLayer, EditBackup, EditBackupRow, LayerStyleOverride, Meta, The state of one object when the backup was made. `original` holds the row as…, A vector layer staff may edit on the map, switched on in the map's settings…, Restore point for what-if edits made with the map editor (core/editing.py,… (+3 more)

### Community 56 - "Impervious Fractions & SOLWEIG Inputs"
Cohesion: 0.17
Nodes (14): impervious_fraction(), _matches(), Sealed share (0-1) of a land-cover class; 0 for classes not in…, Any keyword at a word start of `name`: "road" must not match "broad-leaved…, build(), _footprints(), Inputs, landcover_grid() (+6 more)

### Community 57 - "Editing Frontend"
Cohesion: 0.28
Nodes (13): _attachEditor(), _bindDrawEvents(), _cancelEdit(), _drawModeFor(), _featureUrl(), _hideOriginal(), _openEditorPanel(), _removeDrawControl() (+5 more)

### Community 58 - "Landing Scroll Stages"
Cohesion: 0.26
Nodes (14): renderDom(), activeStage(), cameraAt(), CAMERAS, fitFactor(), HOLD_END, layersAt(), locate() (+6 more)

### Community 59 - "LST Tool Frontend"
Cohesion: 0.33
Nodes (14): init(), calculate(), commonParams(), csrfToken(), findScenes(), open(), pct(), readJson() (+6 more)

### Community 60 - "Weather Pill"
Cohesion: 0.32
Nodes (13): applyPrecipEffect(), fmt(), init(), load(), openHeatPanel(), precipKind(), radarLayer(), radarVisible() (+5 more)

### Community 61 - "External Data Import UI"
Cohesion: 0.15
Nodes (12): Catalog bbox_from (area-of-interest picker level), external_data.html (Import Public Data), clearBbox(), Import Selected click handler (POST start_external_import), initBboxMap(), loadPickerLevel(), pickerLevelFor(), setPickerLevel() (+4 more)

### Community 62 - "LST Calculation"
Cohesion: 0.14
Nodes (14): calculate_lst(), ndvi_mosaic(), Band 1 of a GDALRaster averaged onto `grid` (NaN outside it / at nodata)., NDVI on the grid; where layers overlap, the first (newest) one wins., Delete the other LST rows of the same scene that lie inside `grid` (a…, Compute one LST raster and (unless save=False) store it. bbox_wgs84 [west,…, replace_covered(), resample_to_grid() (+6 more)

### Community 63 - "Water Demand & Consumption"
Cohesion: 0.16
Nodes (11): calculate_total_demand(), _get_consumption_capita(), _get_consumption_record_years(), Per city of the unit, the ConsumptionCapita record used for `year`…, Per-capita consumption (L/person/day) for an admin unit and year. Mean over the…, Total water demand in m³/day across all cities in an admin unit., baseline_population(), Population the stored chain uses for `city` in `year`: the CBS median forecast… (+3 more)

### Community 64 - "Admin Unit Lookup & Population"
Cohesion: 0.14
Nodes (14): Look up a Province/City/District/Neighborhood instance by level + name., resolve_admin_unit(), get_population(), Projected population of `unit` in `year` (its current population if `year` is…, calculate_dwellings(), calculate_household_size(), calculate_new_units_for_unit(), calculate_property_indicators() (+6 more)

### Community 65 - "Built-up Chain Equations"
Cohesion: 0.18
Nodes (13): aspect_ratio(), canyon(), canyon_height(), canyon_width(), classify_unit(), Pure equations of the street canyon (no ORM queries). H = (H_left + H_right) /…, Mean of the two side heights in metres; a side without buildings is 0., (W in metres, source): 'street' (typed width), 'facade' (measured) or 'default'. (+5 more)

### Community 66 - "Built-up Model save() Logic"
Cohesion: 0.18
Nodes (7): bag_usage_labels(), DAG edges: Buildings -> Canyon_Aspect, Streets -> Canyon_Aspect. Re-reads the…, BAG gebruiksdoel as a list of labels (Building.BAG_USAGE_FUNCTIONS). WFS…, Degree of Urbanisation of an admin unit (DAG node Degree_Urbanisation): its…, DAG edges: Total_Population -> Degree_Urbanisation, Buildings ->…, Set every derived field from the population per class and the urban area (m²)., Urbanisation

### Community 67 - "DEGURBA Rebuild"
Cohesion: 0.20
Nodes (12): current_year(), The population year: latest Neighborhood.populationDate, else the latest…, Full build from the UI: every neighborhood, every land-cover share., What the map's Degree of Urbanisation card shows: year, grid sizes, class…, rebuild(), status(), degurba_calculate(), degurba_info() (+4 more)

### Community 68 - "Frontend Config"
Cohesion: 0.15
Nodes (13): availableLayers, BASEMAPS, BUILDING_COLOR_BY_TOOL, CONFIG, HIDES_3D_BUILDINGS_APPS, HIDES_3D_BUILDINGS_KEYS, layerVisibility, loadedLayers (+5 more)

### Community 69 - "Map Page Template & Tools"
Cohesion: 0.18
Nodes (11): Calculate-for-this-view Tools (LST, SVF, SOLWEIG, DEGURBA), Legend stack (#legend-stack), LST tool card, dashboard_summary.html (population KPI card), population_panel.html (Curves-style forecast graph + stats), Population dock, Side panel (#panel-body HTMX target), SVF tool card (+3 more)

### Community 70 - "Map Page Wiring & Tour"
Cohesion: 0.20
Nodes (11): actionsMenu, actionsMenuBtn, ADMIN_PANEL_TOOLS, clearTourHighlight(), endTour(), findActiveAdminTool(), positionActionsMenu(), refreshActivePanel() (+3 more)

### Community 71 - "Postgres Check Tool"
Cohesion: 0.32
Nodes (13): _connect(), _create_extensions_help(), _diagnose_connection_error(), _install_postgis_help(), _install_postgres_help(), main(), _postgres_binaries(), Check that PostgreSQL is reachable with the .env settings and has PostGIS. Run… (+5 more)

### Community 72 - "Layer Cache Versioning"
Cohesion: 0.24
Nodes (11): bump_layer_version(), get_cache(), _label(), layer_version(), Versioned cache keys for data that only changes when rows are written. Every…, caches[alias], falling back to the default cache when the alias isn't…, Current cache version of a model's data. A missing version is seeded with the…, Invalidate every cached response built from these models' rows. (+3 more)

### Community 73 - "Indicator Help Content"
Cohesion: 0.21
Nodes (8): Help texts behind the "?" buttons of the indicator dashboards and side panels.…, Info Help (?) Button with inert template, Infiltration card (SCS Curve Number), Non-Revenue Water card (apparent/real losses, ILI), Supply Security gauge / Service Time, Consumption per Capita what-if slider, Groundwater season switch (GHG wet / GLG dry), water_indicators.html (standalone water dashboard)

### Community 74 - "SVF Tool Frontend"
Cohesion: 0.33
Nodes (12): init(), calculate(), csrfToken(), loadInfo(), open(), params(), readJson(), refreshButton() (+4 more)

### Community 75 - "Housing Calculations"
Cohesion: 0.15
Nodes (12): calculate_affordability(), calculate_house_price_index(), calculate_new_units(), calculate_rent_indicators(), calculate_supply_demand(), calculate_supply_demand_for_unit(), New housing units in the pipeline. DAG edges: Zoning_Status -> New_Units…, Housing supply vs demand for a city and year. DAG edges: Total_Population ->… (+4 more)

### Community 76 - "Housing Dashboard & Gaps"
Cohesion: 0.19
Nodes (12): Pipeline land take (greenfield vs infill), Housing Supply Coverage gauge (supply / demand units), Zoning & Land Value card (HILUCS shares), Average Persons per Home what-if slider, TODO: Unimplemented DAG Edges, Missing Accessibility model, Rent/Mortgage/Water_Tariff -> Affordability_Stress Gap, Indicator threshold alerting system (backlog) (+4 more)

### Community 77 - "Population Dock Panels"
Cohesion: 0.32
Nodes (10): applyPopulationControls(), initPopulationHover(), loadDashboardPopulation(), loadPopulationPanel(), populationRequestParams(), refreshPopulationViews(), resetPopulationControls(), showDashboardSummary() (+2 more)

### Community 78 - "Housing Chain Equations"
Cohesion: 0.18
Nodes (11): average_household_size(), baseline_population(), demand_units(), housed_residents(), The population -> household size -> housing demand / residents chain of the…, (population, partial) the stored housing chain uses for `city` in `year`.…, Persons per private household, or None without both inputs., Homes needed to house `population` at `average_size` persons each (None without… (+3 more)

### Community 79 - "Heat Dashboard Templates"
Cohesion: 0.22
Nodes (7): initGauges() (global), Canyon_Aspect -> Meteorology Gap, Groundwater Recharge Simplifications (crop factor 1, no soil store), Weather What-if Sliders (ta_c, rh_pct, wind_ms, kdown_wm2), Vegetation Coverage what-if slider, Urban Morphology aspect ratio (H/W), Rain Event + Groundwater Season What-if

### Community 80 - "DEGURBA Tool Frontend"
Cohesion: 0.42
Nodes (9): init(), calculate(), csrfToken(), loadInfo(), open(), readJson(), render(), setStatus() (+1 more)

### Community 81 - "Bulk Writer"
Cohesion: 0.27
Nodes (4): BulkWriter, Collects rows and writes them `batch_size` at a time. With a unique field, rows…, A writer when `Model` can safely be bulk-written, otherwise None (use the row…, Write what is left, replay the skipped signals and invalidate the layer cache.

### Community 82 - "Housing Views"
Cohesion: 0.36
Nodes (7): population_params(), (scenario, growth_adjust_pct) from a request's query parameters `pop_scenario`…, _build_indicators(), housing_indicators(), housing_indicators_json(), JSON endpoint for programmatic access to housing indicators., recalculate_indicators()

### Community 83 - "Built-up Dashboard Templates"
Cohesion: 0.25
Nodes (5): builtup_indicators.html (standalone dashboard), Built-up Coverage / FAR card, Park Area per Inhabitant card (WHO 9/50 m2), Additional Park Area slider (green_added_ha), Degree of Urbanisation Threshold Calibration

### Community 84 - "GEE Auth"
Cohesion: 0.28
Nodes (5): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE for the given Cloud project. `ee.Authenticate()` is a one-time-…, initialize(), Authenticate once per process, like the importer's GEE sources.

### Community 85 - "KNMI Importer"
Cohesion: 0.31
Nodes (5): KNMIImporter, KNMI Data Platform (Open Data API v1). Flow: list the newest file of a dataset…, UTC datetime encoded in a KNMI file name, or None if it has none., Convert a downloaded KNMI grid to a single-band float32 GeoTIFF in…, Import the newest file of the dataset described by a catalog entry.

### Community 86 - "Weather Stations & Meteorology"
Cohesion: 0.28
Nodes (6): Meteorology, Time-series weather measurements from stations. `period` says what a row's…, WeatherStation, A year of daily precipitation and reference evapotranspiration at the station…, {'station': WeatherStation, 'year', 'daily_rain_mm': [...], 'et_ref_mm': float}…, yearly_water_balance()

### Community 87 - "Console Feed Frontend"
Cohesion: 0.50
Nodes (7): begin(), busy(), end(), poll(), render(), schedule(), settle()

### Community 88 - "Heat Dashboard JS"
Cohesion: 0.46
Nodes (7): anyTouched(), applyZone(), resetWeather(), showValue(), syncResetButton(), weatherInputs(), zoneStyle()

### Community 89 - "Map Settings Frontend"
Cohesion: 0.46
Nodes (6): applyEditable(), applyStyle(), catalogEntry(), init(), preview(), readdLayer()

### Community 90 - "Info Help Template Tag"
Cohesion: 0.25
Nodes (7): friendly_equation(), info_help(), ``{% info_help "<key>" %}`` renders a card's "?" button with its help entry…, Escape an equation and render its fractions and superscripts as HTML., The "?" button of card `key`; an unknown key renders the button with only its…, filter, inclusion_tag

### Community 91 - "Version Info"
Cohesion: 0.32
Nodes (6): _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. Counts half the commits:…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 92 - "Deferred Cascades & CBS"
Cohesion: 0.25
Nodes (6): deferred_cascades(), Run the administrative population cascade, the land-cover urban-area recompute,…, CBSImporter, Import handler for CBS StatLine OData datasets., Fetch tabular data from CBS OData API and import to Django model. Args:…, Fetch column definitions and units for a CBS table. Useful for building field…

### Community 93 - "Map Settings Templates"
Cohesion: 0.25
Nodes (8): map_settings.html (Editable layers / Styles tabs), settings_editable_row.html (editable layer toggle), settings_style_form.html (vector/raster style override form), Map settings card (staff), base.html (site shell), LoadingManager (fetch/XHR interceptor overlay), syncHeaderHeight (--header-height CSS var), login.html (staff login form)

### Community 94 - "HILUCS Codelist"
Cohesion: 0.29
Nodes (7): hilucs_lookup(), hilucs_q(), parse_hilucs_href(), INSPIRE HILUCS (Hierarchical INSPIRE Land Use Classification System) helpers. A…, (code, label) of a HILUCS URI, or None if it is not one. The label is spelled…, __fk_lookup__ parser for HILUCS URIs (importer/external_data.py): returns…, Q matching rows whose HILUCS FK `field` is one of `codes` or below it in the…

### Community 95 - "DSM Edits & Thermal Runs"
Cohesion: 0.25
Nodes (6): DSMEdit, Append-only log of the areas where the DSM overlay changed (a patch saved,…, One SOLWEIG thermal-comfort calculation for a map view and hour…, ThermalComfortRun, Results that the editor's building changes made stale inside `view` (storage…, stale_results()

### Community 96 - "Architecture Export"
Cohesion: 0.43
Nodes (7): browser(), main(), page(), Export docs/architecture/latest/*.svg to PNG and PDF with headless Chrome/Edge.…, One page per SVG, each page sized to its diagram (named @page rules)., run(), size()

### Community 97 - "LST Command & Window"
Cohesion: 0.29
Nodes (5): default_window(), [from, to) around the NDVI acquisition; summer of its year when it has no date., search_window(), Command, BaseCommand

### Community 98 - "Housing Dashboard Panel"
Cohesion: 0.38
Nodes (4): applyZone(), zoneStyle(), housing_indicators.html (Province Housing Dashboard), Indicator Dashboard Three-Layer Pattern

### Community 99 - "GEE Importer"
Cohesion: 0.38
Nodes (5): GEEImporter, prepare(), Import handler for Google Earth Engine datasets. Optional catalog keys on a GEE…, Function Image -> Image selecting (or deriving) the entry's band., Export raster from GEE to local GeoTIFF.

### Community 100 - "Non-Revenue Water"
Cohesion: 0.29
Nodes (4): LossesChoices, LossesTypes, NonRevenueWater, Create a random NonRevenueWater loss event. Picks a random LossesChoices,…

### Community 101 - "Point-in-Unit Lookup"
Cohesion: 0.33
Nodes (6): Built once per process: creating a GDAL/PROJ transformation is the slow part of…, Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), _wgs84_to_storage(), admin_unit_at_point(), Point-in-polygon lookup for the map center: resolve the smallest administrative…

### Community 102 - "DB Stats Command"
Cohesion: 0.33
Nodes (3): Command, BaseCommand, Show the most expensive SQL statements recorded by pg_stat_statements…

### Community 104 - "Info Popover"
Cohesion: 0.53
Nodes (4): fill(), place(), popover(), show()

### Community 105 - "Environmental Costs"
Cohesion: 0.33
Nodes (3): EnvironmentalCosts, The most recent cost record (the model has no province/year), or None., DAG edges: Available_FW -> Total_Extraction Total_Extraction ->…

### Community 106 - "Zoning Areas"
Cohesion: 0.40
Nodes (3): ZoningArea, calculate_zoning(), Zoning area breakdown. DAG edges: Housing_Demand -> Zoning_Status Zoning_Status…

### Community 107 - "Upload Templates"
Cohesion: 0.50
Nodes (5): model_selector.js initModelSelector, FieldMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 108 - "App Icon 512"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 109 - "Water Dashboard JS"
Cohesion: 0.60
Nodes (4): applyRain(), applyZone(), rainStyle(), zoneStyle()

### Community 110 - "Energy Models"
Cohesion: 0.40
Nodes (3): ElectricityCost, EnergyEfficiencyLabels, Meta

### Community 111 - "WMS Legend Lookup"
Cohesion: 0.40
Nodes (4): default_wms_legend_url(), _legend_url_from_capabilities(), Look up a layer's <LegendURL><OnlineResource xlink:href="..."/> from the WMS…, Resolve a legend image URL for a WMS layer, used as a fallback when a catalog…

### Community 113 - "App Icon 192"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 117 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 119 - "Style Suggestion Design System"
Cohesion: 0.50
Nodes (4): Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono)

### Community 122 - "Apple Touch Icon"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 123 - "Favicon 16"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 124 - "Favicon 32"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

## Knowledge Gaps
- **99 isolated node(s):** `WMSLayerAdmin`, `TpwSource`, `HILUCSLandUseAdmin`, `LandCoverClassesAdmin`, `SoilTypeAdmin` (+94 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1097 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `feature_form.html (map feature editor)` connect `Map Editing Backup/Restore` to `Editing Frontend`, `Map Page Template & Tools`?**
  _High betweenness centrality (0.196) - this node is a cross-community bridge._
- **Why does `Side panel (#panel-body HTMX target)` connect `Map Page Template & Tools` to `Indicator Help Content`, `Housing Dashboard Panel`, `Map Editing Backup/Restore`?**
  _High betweenness centrality (0.151) - this node is a cross-community bridge._
- **Why does `City` connect `Administrative Units & Population` to `GeoJSON Feature Import`, `Land Cover Rings & Albedo`, `physicalEnv Signals & Editor Hooks`, `Housing Models & Signals`, `LST Command & Window`, `Water Supply Signals`, `Water Supply Calculations`, `DEGURBA Population Allocation`, `Water Chain & Models`, `File Upload Importer`, `Nature Models`, `Street Canyon Inputs`, `LST Grid & Pipeline`, `Built-up Calculations`, `External Import Dispatch`, `Deferred Cascades & CBS`, `Water Demand & Consumption`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Are the 35 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Building` (e.g. with `calculate_building_age()` and `calculate_building_mix()`) actually correct?**
  _`Building` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `LandCoverVector` (e.g. with `_landcover_rows_created()` and `landcover_shares()`) actually correct?**
  _`LandCoverVector` has 17 INFERRED edges - model-reasoned connections that need verification._