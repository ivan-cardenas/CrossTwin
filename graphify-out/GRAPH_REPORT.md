# Graph Report - CrossTwin  (2026-10-15)

## Corpus Check
- 166 files · ~133,699 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1612 nodes · 2944 edges · 120 communities (85 shown, 24 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 263 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Administrative Units & Population
- Map Layers & Events JS
- SVF Calculation
- Water Supply Models
- Land-Cover Release & Batching
- Water Supply Calculations
- LST/SVF Tool Frontend
- Model Registry & Forms
- Map Editing & Backup
- Water Supply Models (2)
- Housing & Built-up Models
- Built-up Indicators
- LST Pipeline & NDVI
- External Importer Core
- Earth Engine Auth & Inputs
- SMW Equations
- CBS & Enrichment Import
- Heat Indicators
- Urban Heat Models
- Housing & Built-up Models (2)
- Housing & Built-up Models (3)
- WMS Tile Proxy
- Map Views & Panels
- Population Chart
- Urban Fabric Buffer & Arch Diagrams
- LST Tool Views
- Spatial Parent Index
- Housing & Built-up Models (4)
- COG Export
- OSM Overpass Importer
- Nature Models
- External Catalog Views
- LST Grid
- Layer Cache Versioning
- LST/SVF Tool Frontend (2)
- Raster Tile API
- External Data Import UI
- Weather Raster Models
- Map Init & City Name
- Housing Dashboard Cards
- Housing & Built-up Models (5)
- Postgres Check Tool
- Weather Raster Models (2)
- Administrative Units & Population (2)
- LST/SVF Tool Frontend (3)
- External Importer Core (2)
- Heat Calculations
- Heat Dashboard JS
- KNMI Importer
- Water Dashboard Cards
- Design System & Base Template
- Weather Raster Signals
- Map Views & Panels (2)
- README Architecture Concepts
- Dependencies
- Frontend Config
- BulkWriter
- Land-Cover & Soil Styles
- Housing Panel JS
- Housing & Built-up Models (6)
- Built-up Dashboard Cards
- Version Info
- Diagram Export
- Precipitation Rasters
- Land-Cover & Soil Styles (2)
- Tree Styles
- Map Views & Panels (3)
- DB Stats Command
- Query Stats Middleware
- External Importer Core (3)
- Earth Engine Auth & Inputs (2)
- App Icon 512
- Water Dashboard JS
- Administrative Units & Population (3)
- PhysicalEnv Admin
- LST Grid (2)
- Nature-Based Solutions
- Precipitation Rasters (2)
- Precipitation Rasters (3)
- Admin Unit Lookup
- Administrative AppConfig
- Core AppConfig
- App Icon 192
- Django Settings
- CBS & Enrichment Import (2)
- Importer Upload Templates
- manage.py
- PhysicalEnv AppConfig
- NDVI Mosaic
- Urban Heat Models (2)
- Weather AppConfig
- Builtup AppConfig
- Geo Functions
- Apple Touch Icon
- Favicon 16
- Favicon 32
- Energy AppConfig
- Housing AppConfig
- Importer AppConfig
- Nature AppConfig
- Request Profiler
- Urban Heat AppConfig
- Meteorology
- Bbox Rounding Tests
- ASGI
- WSGI
- AppConfig Base
- require_POST
- Style Suggestion Doc

## God Nodes (most connected - your core abstractions)
1. `City` - 48 edges
2. `Neighborhood` - 35 edges
3. `Province` - 28 edges
4. `Building` - 20 edges
5. `import_dataset()` - 20 edges
6. `District` - 19 edges
7. `calculate_lst()` - 19 edges
8. `LandCoverVector` - 18 edges
9. `Diagram` - 18 edges
10. `ImportResult` - 18 edges

## Surprising Connections (you probably didn't know these)
- `watersupply indicators_panel.html (HTMX side panel)` --semantically_similar_to--> `builtup indicators_panel.html (HTMX side panel)`  [INFERRED] [semantically similar]
  watersupply/templates/watersupply/partials/indicators_panel.html → builtup/templates/builtup/partials/indicators_panel.html
- `housing indicators_grid.html` --conceptually_related_to--> `No inline <script> blocks convention`  [AMBIGUOUS]
  housing/templates/housing/partials/indicators_grid.html → README.md
- `Building` --uses--> `Neighborhood`  [INFERRED]
  builtup/models.py → administrative/models.py
- `Building` --uses--> `SurfaceMaterialProperties`  [INFERRED]
  builtup/models.py → physicalEnv/models.py
- `Building` --uses--> `WallMaterialProperties`  [INFERRED]
  builtup/models.py → physicalEnv/models.py

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

## Communities (120 total, 24 thin omitted)

### Community 0 - "Administrative Units & Population"
Cohesion: 0.06
Nodes (48): CityAdmin, NeighborhoodAdmin, ProvinceAdmin, cities_within(), city_of(), neighborhoods_within(), province_of(), Shared helpers for resolving and aggregating by administrative unit. Lets any… (+40 more)

### Community 1 - "Map Layers & Events JS"
Cohesion: 0.06
Nodes (64): initializeUI(), activateToolLayers(), addAnimatedWmsLayer(), addCategoricalLegend(), addCoordinatesToBounds(), addLayer(), addRasterLayer(), addRasterLayerFromConfig() (+56 more)

### Community 2 - "SVF Calculation"
Cohesion: 0.06
Nodes (55): DigitalSurfaceModel, _area(), calculate_svf(), dsm_extent(), dsm_for_view(), existing_svf(), horizon_shift_vector(), _intersection() (+47 more)

### Community 3 - "Water Supply Models"
Cohesion: 0.06
Nodes (42): The most recent cost record (the model has no province/year), or None., AppConfig, WatersupplyConfig, LossesChoices, LossesTypes, MeteredResidential, NonRevenueWater, OPEX (+34 more)

### Community 4 - "Land-Cover Release & Batching"
Cohesion: 0.07
Nodes (47): is_restoring(), True while restore_backup() runs. Receivers that undo an edit's side effects on…, calculate_pipeline_land_take(), Land cover the housing pipeline would build on (dashboard only, writes…, _buffer_sql(), Land-cover overlay edits driven by other layers. urbanize_around() turns a…, Undo urbanize_around() for an editor building that moved or was deleted: every…, The 'urban fabric' class, matched case-insensitively like the PDOK BRT import's… (+39 more)

### Community 5 - "Water Supply Calculations"
Cohesion: 0.07
Nodes (48): calculate_available_freshwater(), calculate_co2_emission(), calculate_collection_ratio(), calculate_coverage(), calculate_drought_area(), calculate_energy_consumption(), calculate_infiltration(), calculate_nrw() (+40 more)

### Community 6 - "LST/SVF Tool Frontend"
Cohesion: 0.07
Nodes (43): _attachEditor(), _bindDrawEvents(), _cancelEdit(), _drawModeFor(), _featureUrl(), _hideOriginal(), _openEditorPanel(), _removeDrawControl() (+35 more)

### Community 7 - "Model Registry & Forms"
Cohesion: 0.06
Nodes (39): atomic, build_model_registry(), Build MODEL_REGISTRY dynamically from specified apps., deferred_cascades(), _finalize_landcover(), Batch-import helpers shared by the file-upload and external-data importers. -…, Run the administrative population cascade, the land-cover urban-area recompute…, GeoUploadForm (+31 more)

### Community 8 - "Map Editing & Backup"
Cohesion: 0.10
Nodes (37): AppConfig, active_backup(), backup(), _backup_bar(), backup_discard(), backup_restore(), _build_form(), _check_constraints() (+29 more)

### Community 9 - "Water Supply Models (2)"
Cohesion: 0.07
Nodes (26): EnvironmentalCosts, WMSLayerAdmin, baseline_population(), consumption_m3_yr(), demand_m3_d(), The population -> consumption -> demand -> supply security -> service time…, Population the stored chain uses for `city` in `year`: the CBS median forecast…, Daily water demand in m3/day: L/person/day / 1000 * persons. (+18 more)

### Community 10 - "Housing & Built-up Models"
Cohesion: 0.10
Nodes (19): calculate_mortgage_indicators(), calculate_new_units(), calculate_supply_demand(), calculate_supply_demand_for_unit(), Housing supply vs demand for a city and year. DAG edges: Urbanization ->…, Mortgage indicators from central bank policy and credit conditions. DAG edges:…, Aggregate supply/demand across all cities within an admin unit., New housing units in the pipeline. DAG edges: Zoning_Status -> New_Units… (+11 more)

### Community 11 - "Built-up Indicators"
Cohesion: 0.15
Nodes (22): calculate_building_age(), calculate_building_mix(), calculate_building_stock(), calculate_facilities(), calculate_green_space(), calculate_street_network(), _pct(), Distribution of construction years over the Dutch typology periods. DAG edges:… (+14 more)

### Community 12 - "LST Pipeline & NDVI"
Cohesion: 0.15
Nodes (20): LandCoverRaster, calculate_lst(), default_window(), grid_for(), LSTError, ndvi_layer(), ndvi_layers_in(), _ndvi_queryset() (+12 more)

### Community 13 - "External Importer Core"
Cohesion: 0.12
Nodes (15): import_dataset(), ImportResult, Register a WMS layer by creating/updating its row in the target WMS model. This…, Fetch tabular data from CBS OData API and import to Django model. Args:…, Import handler for Sentinel-2 datasets., Look up the real acquisition timestamp of the most recent Sentinel-2 L2A scene…, Fetch raster from Sentinel-2 WCS (e.g., WorldCover)., Fetch processed Sentinel-2 imagery via the Copernicus Data Space Ecosystem's… (+7 more)

### Community 14 - "Earth Engine Auth & Inputs"
Cohesion: 0.13
Nodes (20): GEEAuthManager, Manages Google Earth Engine authentication., Initialize GEE for the given Cloud project. `ee.Authenticate()` is a one-time-…, check_download_size(), _collections(), download_bytes(), fetch_scene_inputs(), find_scenes() (+12 more)

### Community 15 - "SMW Equations"
Cohesion: 0.12
Nodes (23): Constants of the Statistical Mono-Window (SMW) LST algorithm for Landsat 8/9.…, apply_qa_emissivity(), bare_ground_emissivity(), _bit_set(), cloud_mask(), fractional_vegetation_cover(), interpolate_tpw(), land_surface_temperature() (+15 more)

### Community 16 - "CBS & Enrichment Import"
Cohesion: 0.10
Nodes (22): Exception, GEOSGeometry, default_wms_legend_url(), ensure_multipolygon(), GEEImporter, _import_feature_rows(), _ImportBlocked, _legend_url_from_capabilities() (+14 more)

### Community 17 - "Heat Indicators"
Cohesion: 0.13
Nodes (22): Look up a Province/City/District/Neighborhood instance by level + name., resolve_admin_unit(), calculate_nbs_coverage(), calculate_urban_morphology(), classify_pet(), classify_utci(), get_latest_meteorology(), get_thermal_indices() (+14 more)

### Community 18 - "Urban Heat Models"
Cohesion: 0.11
Nodes (14): MeanRadiantTemperature, Meta, NeighborhoodHeat, PET, Physiological Equivalent Temperature (PET) measurements, Surface Urban Heat Island Intensity (SUHII)) measurements, Heat and shade indicators per neighborhood, from the Klimaateffectatlas WFS…, Mean Radiant Temperature (MRT) measurements (+6 more)

### Community 19 - "Housing & Built-up Models (2)"
Cohesion: 0.14
Nodes (20): Pure function: takes DB data dict, returns flat indicators dict.…, calculate_affordability(), calculate_house_price_index(), calculate_new_units_for_unit(), calculate_property_indicators(), calculate_rent_indicators(), calculate_zoning(), Aggregate new units across all cities within an admin unit. (+12 more)

### Community 20 - "Housing & Built-up Models (3)"
Cohesion: 0.13
Nodes (19): GroundwaterDepth, Groundwater depth statistic (GHG/GLG/GVG) of the BIS Nederland groundwater…, A polygon of the Dutch soil map, typed by SoilType., SoilArea, curve_number(), infiltration_coefficient(), is_drained(), _matches() (+11 more)

### Community 21 - "WMS Tile Proxy"
Cohesion: 0.15
Nodes (19): WMSLayer, _fetch_with_retry(), _find_dimension_values(), _last_n_time_steps(), _local_tag(), _parse_iso8601(), _parse_iso8601_duration(), Return the raw text of the <Dimension name="time"> for a given layer. (+11 more)

### Community 22 - "Map Views & Panels"
Cohesion: 0.14
Nodes (20): _display_field(), _extract_unit(), _field_label(), _field_meta_entry(), _field_metadata(), _geojson_sql(), _humanize_field_name(), model_geojson() (+12 more)

### Community 23 - "Population Chart"
Cohesion: 0.16
Nodes (19): band_d(), build_population_chart(), pts(), x_of(), y_of(), _fmt(), monotone_segments(), nice_step() (+11 more)

### Community 24 - "Urban Fabric Buffer & Arch Diagrams"
Cohesion: 0.14
Nodes (10): apps(), Diagram, editing(), importer(), infiltration(), on_demand(), overview(), Generate the CrossTwin architecture diagram suite (SVG) into… (+2 more)

### Community 25 - "LST Tool Views"
Cohesion: 0.20
Nodes (18): BadRequest, _bbox(), _date(), _error(), _grid_json(), lst_calculate(), view(), lst_scenes() (+10 more)

### Community 26 - "Spatial Parent Index"
Cohesion: 0.12
Nodes (9): Point-in-polygon lookup against a fixed set of parent rows. Each parent's…, Load only what the lookup needs: pk, geom and any attributes read off the…, The parent containing `geom`'s representative point, or None., SpatialParentIndex, _gml_multipolygon(), _import_atom_gml_features(), WGS84 MultiPolygon of every gml:Polygon below `elem` (None if there are none,…, Stream an INSPIRE Planned Land Use GML file over HTTP and import the… (+1 more)

### Community 27 - "Housing & Built-up Models (4)"
Cohesion: 0.14
Nodes (9): Building, BuildingEnergyLabel, Meta, NeighborhoodClimateRisk, Park, Property, Proxy onto Building, filed under the Energy app so the energy-label fields…, Climate risks to the building stock of a neighborhood, from the… (+1 more)

### Community 28 - "COG Export"
Cohesion: 0.17
Nodes (13): Command, _cog_filename(), export_all_rasters(), export_geotiff_to_cog(), export_raster_to_cog(), get_raster_field_name(), Build a COG filename from whatever satellite/process metadata the raster model…, Reproject a local GeoTIFF to EPSG:4326 and convert it to a COG on disk, saving… (+5 more)

### Community 29 - "OSM Overpass Importer"
Cohesion: 0.17
Nodes (9): OSMImporter, Import handler for OpenStreetMap through the Overpass API. The Overpass JSON is…, Overpass QL for `dataset` inside bbox [west, south, east, north] (WGS84)., Leading number of an OSM tag value: '12 m' -> 12.0, '7,5' -> 7.5, '40 ft' ->…, (Multi)polygon of a multipolygon relation from its member ways. A ring may be…, GeoJSON geometry of one Overpass element (out center or out geom)., Overpass elements -> GeoJSON features whose properties are the OSM tags plus…, OSM tags are strings ('12 m'); give numeric model fields a number, or drop the… (+1 more)

### Community 30 - "Nature Models"
Cohesion: 0.12
Nodes (9): Forests, GreenSpaces, Meta, ProtectedArea, ProtectionType, Tree, WaterBodies, WaterWaysLN (+1 more)

### Community 31 - "External Catalog Views"
Cohesion: 0.14
Nodes (12): get_catalog_grouped(), _kea_building(), _kea_neighborhood(), Mapping for a per-buurt KEA layer: one row per stored neighborhood, keyed on…, Return the catalog grouped by category. Structure: { category: [datasets] }…, Mapping for a per-pand KEA layer: attributes written onto existing BAG…, get_external_data(), require_POST (+4 more)

### Community 32 - "LST Grid"
Cohesion: 0.13
Nodes (10): Grid, The one raster grid every LST input is put on before the equations run., Smallest grid with corners on multiples of `resolution` that covers the extent., Affine in Earth Engine's order: [xScale, xShear, xOffset, yShear, yScale,…, [west, south, east, north] in EPSG:4326, for filtering image collections., North-up grid: (x0, y0) is the top-left corner, cells are `resolution` m square., Grid over the part of the view the NDVI layers cover (LST is empty elsewhere)., The [west, south, east, north] WGS84 box as a polygon in the storage CRS. (+2 more)

### Community 33 - "Layer Cache Versioning"
Cohesion: 0.20
Nodes (13): bump_layer_version(), get_cache(), _label(), layer_version(), Versioned cache keys for data that only changes when rows are written. Every…, caches[alias], falling back to the default cache when the alias isn't…, Current cache version of a model's data. A missing version is seeded with the…, Invalidate every cached response built from these models' rows. (+5 more)

### Community 34 - "LST/SVF Tool Frontend (2)"
Cohesion: 0.18
Nodes (12): actionsMenu, actionsMenuBtn, ADMIN_PANEL_TOOLS, clearTourHighlight(), endTour(), findActiveAdminTool(), positionActionsMenu(), refreshActivePanel() (+4 more)

### Community 35 - "Raster Tile API"
Cohesion: 0.21
Nodes (12): get_raster_info(), get_raster_tiles(), Return raster metadata including bounds., Return TiTiler tile URL for a given raster layer., _cog_statistics(), colormap_legend_stops(), _lookup_style(), raster_display_name() (+4 more)

### Community 36 - "External Data Import UI"
Cohesion: 0.15
Nodes (12): Catalog bbox_from (area-of-interest picker level), external_data.html (Import Public Data), clearBbox(), Import Selected click handler (POST start_external_import), initBboxMap(), loadPickerLevel(), pickerLevelFor(), setPickerLevel() (+4 more)

### Community 37 - "Weather Raster Models"
Cohesion: 0.15
Nodes (8): interpolate_raster(), Interpolates raster data using Radial Basis Function (RBF) interpolation.…, HumidityRaster, Determine bounds for interpolation, Extract point data from measurements Args: measurements: QuerySet of…, Generate raster by interpolating measurements Must be implemented by child…, Generic interpolation method - works for all child classes, Interpolated relative humidity raster layer

### Community 38 - "Map Init & City Name"
Cohesion: 0.24
Nodes (11): updateCityName(), add3DBuildings(), addExternalLayers(), ADMIN_LEVELS, changeBasemap(), getSavedCameraState(), initializeUrbanTwinMap(), onAdminLayerLoaded() (+3 more)

### Community 39 - "Housing Dashboard Cards"
Cohesion: 0.18
Nodes (14): housing indicators_grid.html, Average Fixed Mortgage Rate card (annuity, 30y), Pipeline land take (greenfield vs infill) display, Zoning & Land Value card (HILUCS shares), Population dock, Three-Layer Indicator Dashboard Pattern, MOCK_DATA fallback, TODO - Unimplemented DAG Edges (+6 more)

### Community 40 - "Housing & Built-up Models (5)"
Cohesion: 0.14
Nodes (8): DigitalElevationModelWMS, DigitalSurfaceModelWMS, HILUCSLandUse, LandCoverWMS, Meta, INSPIRE HILUCS land-use classification…, SurfaceMaterialProperties, WallMaterialProperties

### Community 41 - "Postgres Check Tool"
Cohesion: 0.32
Nodes (13): _connect(), _create_extensions_help(), _diagnose_connection_error(), _install_postgis_help(), _install_postgres_help(), main(), _postgres_binaries(), Check that PostgreSQL is reachable with the .env settings and has PostGIS. Run… (+5 more)

### Community 42 - "Weather Raster Models (2)"
Cohesion: 0.15
Nodes (7): InterpolatedRasterBase, Calculate bounds polygon from the raster's extent, Convert extent tuple to Polygon, Get measurements within time window for a specific field Args:…, Convenience method to generate raster for a Province Args: Province: Province…, Override in child classes to specify which measurement field to use, Override in child classes to specify metadata keys Returns tuple: (min_key,…

### Community 43 - "Administrative Units & Population (2)"
Cohesion: 0.28
Nodes (12): city_changed(), _defer(), deferred_population_cascade(), district_changed(), _flush_population_cascade(), neighborhood_changed(), receiver, Postpone the District -> City -> Province cascade until the block ends, then… (+4 more)

### Community 44 - "LST/SVF Tool Frontend (3)"
Cohesion: 0.33
Nodes (12): init(), calculate(), csrfToken(), loadInfo(), open(), params(), readJson(), refreshButton() (+4 more)

### Community 45 - "External Importer Core (2)"
Cohesion: 0.19
Nodes (10): _enrich_rows(), get_model_class(), _import_geojson_features(), _keep_existing(), Fetch vector data from PDOK WFS service and import directly to Django model.…, Fetch vector data from an OGC API Features service (PDOK's newer REST/JSON…, __require_existing__ {"property", "model", "field" (default pk)}: drop the…, __enrich__: write the mapped attributes onto existing rows of Model, matched by… (+2 more)

### Community 46 - "Heat Calculations"
Cohesion: 0.19
Nodes (12): calculate_green_area(), calculate_vegetation_coverage(), classify_wbgt(), _raster_stats_sql(), Get min/max/mean/stddev from a raster clipped to a geometry., Total green area (parks + green land cover) in km². DAG edges: LandCover →…, Classify a WBGT value (°C) into a heat-stress category., Gauge colour matching classify_wbgt (None when there is no value). (+4 more)

### Community 47 - "Heat Dashboard JS"
Cohesion: 0.23
Nodes (9): applyZone(), zoneStyle(), initGauges() (global), partials/_info_btn.html, partials/_info_popover.html, Thermal comfort indices (LST, PET, UTCI, WBGT, SVF, SUHII), heat_indicators.html (Urban Heat Dashboard), Vegetation Coverage what-if slider (+1 more)

### Community 48 - "KNMI Importer"
Cohesion: 0.24
Nodes (8): datetime, KNMIImporter, load_raster_into_target_model(), KNMI Data Platform (Open Data API v1). Flow: list the newest file of a dataset…, UTC datetime encoded in a KNMI file name, or None if it has none., Convert a downloaded KNMI grid to a single-band float32 GeoTIFF in…, Import the newest file of the dataset described by a catalog entry., Load a downloaded raster file into its catalog entry's target_model. The…

### Community 49 - "Water Dashboard Cards"
Cohesion: 0.26
Nodes (12): No inline <script> blocks convention, Watersupply gaps (collection ratio, WT_Efficiency, Apparent_Losses -> ILI), Consumption per Capita what-if slider, watersupply indicators_grid.html, Infiltration card (SCS Curve Number), Non-Revenue Water card (ILI), Supply Security / Service Time cards, watersupply indicators_panel.html (HTMX side panel) (+4 more)

### Community 50 - "Design System & Base Template"
Cohesion: 0.18
Nodes (12): Design anti-patterns (glow, hover-lift, shimmer gradients), Civic Cartography Dashboard design system, Palette (ink neutrals, cyanotype accent, traffic-light status), Typography (Archivo, Inter, IBM Plex Mono), base.html (site shell template), Template blocks (extra_css, extra_js, content), Header height CSS variable sync, HTMX 1.9.10 library (+4 more)

### Community 51 - "Weather Raster Signals"
Cohesion: 0.24
Nodes (11): create_latest_view(), create_raster_view(), delete_raster_view(), on_raster_deleted(), on_raster_saved(), receiver, Create a view that always shows the latest raster, Create a database view for a single raster (+3 more)

### Community 52 - "Map Views & Panels (2)"
Cohesion: 0.18
Nodes (8): Like <int:>, but also matches negative ids (user-created Buildings, see…, SignedIntConverter, admin_unit_at_point(), layer_bounds(), map_view(), Display the map page., Point-in-polygon lookup for the map center: resolve the smallest administrative…, Returns the bounding box of a layer in WGS84, as [[west, south], [east, north]]…

### Community 53 - "README Architecture Concepts"
Cohesion: 0.29
Nodes (11): CrossTwin README, DAG edge coverage (31 of 103 edges implemented), deferred_cascades() bulk-write batching, DPSIR Causal Framework (core/DAG.dot), Cached GeoJSON API with viewport loading, Importer System (file upload + external catalog), Model Registry (MODEL/VECTOR/RASTER/WMS_REGISTRY), Raster to COG Pipeline (+3 more)

### Community 54 - "Dependencies"
Cohesion: 0.18
Nodes (10): django-crispy-forms + crispy-tailwind, Django 5.2.12, earthengine-api 1.7.18, GDAL 3.11.4 (Windows wheel), geopandas 1.1.2, openeo 0.51.0, owslib 0.35.0, rasterio 1.4.4 (+2 more)

### Community 55 - "Frontend Config"
Cohesion: 0.22
Nodes (9): availableLayers, BASEMAPS, CONFIG, layerVisibility, loadedLayers, roundBboxInUrl(), roundCoord(), TOOL_CATEGORIES (+1 more)

### Community 56 - "BulkWriter"
Cohesion: 0.27
Nodes (4): BulkWriter, Collects rows and writes them `batch_size` at a time. With a unique field, rows…, A writer when `Model` can safely be bulk-written, otherwise None (use the row…, Write what is left, replay the skipped signals and invalidate the layer cache.

### Community 57 - "Land-Cover & Soil Styles"
Cohesion: 0.22
Nodes (7): build_soil_style_and_legend(), Colours of the soil map (physicalEnv.SoilArea), taken from the legend of the…, (style_layers, legend) for physicalEnv.SoilArea: a `match` on the…, A soil unit of the Dutch soil map (Bodemkaart 1:50 000, BIS Nederland), stored…, SoilType, classify_soil_group(), Hydrologic soil group 'A'-'D' of a Dutch soil map name, or None if it names no…

### Community 58 - "Housing Panel JS"
Cohesion: 0.25
Nodes (7): applyZone(), zoneStyle(), housing_indicators.html (Province Housing Dashboard), Mortgage Interest Rate what-if slider, pop_scenario / pop_growth population what-if params, indicators_base.html (standalone dashboard shell), #indicators-grid HTMX swap target

### Community 59 - "Housing & Built-up Models (6)"
Cohesion: 0.25
Nodes (8): _hilucs_lookup(), hilucs_lookup(), hilucs_q(), parse_hilucs_href(), INSPIRE HILUCS (Hierarchical INSPIRE Land Use Classification System) helpers. A…, (code, label) of a HILUCS URI, or None if it is not one. The label is spelled…, __fk_lookup__ parser for HILUCS URIs (importer/external_data.py): returns…, Q matching rows whose HILUCS FK `field` is one of `codes` or below it in the…

### Community 60 - "Built-up Dashboard Cards"
Cohesion: 0.29
Nodes (6): builtup_indicators.html (standalone dashboard), builtup indicators_grid.html, Built-up Coverage / FAR card, Park Area per Inhabitant card (WHO 9/50 m2), builtup indicators_panel.html (HTMX side panel), Additional Park Area slider (green_added_ha)

### Community 61 - "Version Info"
Cohesion: 0.32
Nodes (6): _derive_version(), _get_git_info(), Derive a semver-ish label from the raw commit count. 0–99 → v0.1, 100–199 →…, Inject git info into every template rendered by Django., Run git commands once and cache the result for the process lifetime. In…, version_context()

### Community 62 - "Diagram Export"
Cohesion: 0.43
Nodes (7): browser(), main(), page(), Export docs/architecture/latest/*.svg to PNG and PDF with headless Chrome/Edge.…, One page per SVG, each page sized to its diagram (named @page rules)., run(), size()

### Community 63 - "Precipitation Rasters"
Cohesion: 0.25
Nodes (4): Meta, Interpolated wind speed raster layer, WeatherStation, WindSpeedRaster

### Community 64 - "Land-Cover & Soil Styles (2)"
Cohesion: 0.33
Nodes (6): build_landcover_style_and_legend(), get_landcover_color(), available_layers(), raster_layer_entry(), Returns a list of all available layers (models with geometry fields). URL:…, The layer-catalog entry of one raster row (also returned by the map's LST tool).

### Community 65 - "Tree Styles"
Cohesion: 0.33
Nodes (5): Map styling of the vector layers: Mapbox GL style layers, legend entries and…, build_tree_style(), Map style of nature.Tree: green dots when zoomed out, a 3D glTF tree per point…, style_layers for nature.Tree. The circle layer comes first: it is the click…, _uniform()

### Community 66 - "Map Views & Panels (3)"
Cohesion: 0.33
Nodes (7): dashboard_summary(), population_panel(), The administrative unit the population views talk about, as (level, unit,…, HTMX partial for the Dashboard panel: total population of the selected…, HTML for the bottom dock opened from the Population pill: today's population,…, _resolve_summary_unit(), _unit_context()

### Community 67 - "DB Stats Command"
Cohesion: 0.33
Nodes (3): BaseCommand, Command, Show the most expensive SQL statements recorded by pg_stat_statements…

### Community 69 - "External Importer Core (3)"
Cohesion: 0.40
Nodes (4): PDOKImporter, Import handler for PDOK datasets - imports directly to Django models., Split [min_v, max_v] into evenly-sized segments, each no larger than…, Fetch raster data from PDOK WCS service, tiling the request when the area would…

### Community 70 - "Earth Engine Auth & Inputs (2)"
Cohesion: 0.33
Nodes (3): Share of the area with a clear pixel, None if not computed., Scene, LSTResult

### Community 71 - "App Icon 512"
Cohesion: 0.50
Nodes (5): CrossTwin App Icon (android-chrome-512x512), Cyan wireframe/grid half representing geospatial digital model, Digital twin concept: real city (left) mirrored by wireframe model (right), Isometric city block with buildings, trees, park and river, Green-to-cyan orbit ring linking physical and digital halves

### Community 72 - "Water Dashboard JS"
Cohesion: 0.60
Nodes (4): applyRain(), applyZone(), rainStyle(), zoneStyle()

### Community 73 - "Administrative Units & Population (3)"
Cohesion: 0.40
Nodes (3): ElectricityCost, EnergyEfficiencyLabels, Meta

### Community 74 - "PhysicalEnv Admin"
Cohesion: 0.40
Nodes (4): HILUCSLandUseAdmin, LandCoverClassesAdmin, SoilTypeAdmin, SurfaceMaterialPropertiesAdmin

### Community 75 - "LST Grid (2)"
Cohesion: 0.40
Nodes (4): Delete the other LST rows of the same scene that lie inside `grid` (a…, replace_covered(), LandSurfaceTemperature, Land Surface Temperature (LST) measurements

### Community 76 - "Nature-Based Solutions"
Cohesion: 0.40
Nodes (3): NatureBasedSolutionPoint, NatureBasedSolutionPolygon, Nature-Based Solutions (NBS) for urban heat mitigation

### Community 79 - "Admin Unit Lookup"
Cohesion: 0.50
Nodes (4): Built once per process: creating a GDAL/PROJ transformation is the slow part of…, Point-in-polygon lookup: find the smallest administrative unit (Neighborhood >…, resolve_admin_unit_at_point(), _wgs84_to_storage()

### Community 82 - "App Icon 192"
Cohesion: 0.67
Nodes (4): CrossTwin App Icon (192x192), Isometric digital twin city motif (solid buildings blending into wireframe buildings), Green park/land base with trees and blue water/street edge, Teal orbit rings and clouds on navy rounded-square background

### Community 84 - "CBS & Enrichment Import (2)"
Cohesion: 0.50
Nodes (3): CBSImporter, Import handler for CBS StatLine OData datasets., Fetch column definitions and units for a CBS table. Useful for building field…

### Community 85 - "Importer Upload Templates"
Cohesion: 0.67
Nodes (4): FieldMapping.html Template, upload.html Template, upload_result.html Template, importer:upload_geodata view

### Community 86 - "manage.py"
Cohesion: 0.50
Nodes (3): main(), Run administrative tasks., Django's command-line utility for administrative tasks.

### Community 88 - "NDVI Mosaic"
Cohesion: 0.50
Nodes (4): ndvi_mosaic(), Band 1 of a GDALRaster averaged onto `grid` (NaN outside it / at nodata)., NDVI on the grid; where layers overlap, the first (newest) one wins., resample_to_grid()

### Community 93 - "Apple Touch Icon"
Cohesion: 1.00
Nodes (3): CrossTwin App Icon (apple-touch-icon), Isometric digital twin city block (solid buildings beside wireframe buildings), Urban environment elements: green park, water/canal, street grid, clouds, orbit rings

### Community 94 - "Favicon 16"
Cohesion: 0.67
Nodes (3): CrossTwin favicon 16x16, Browser tab icon (branding), Teal/blue cube-like glyph on light background

### Community 95 - "Favicon 32"
Cohesion: 0.67
Nodes (3): CrossTwin favicon (32x32), Blue rounded-square app icon with city skyline motif, CrossTwin brand identity (digital twin platform)

## Ambiguous Edges - Review These
- `housing indicators_grid.html` → `No inline <script> blocks convention`  [AMBIGUOUS]
  housing/templates/housing/partials/indicators_grid.html · relation: conceptually_related_to
- `watersupply indicators_grid.html` → `No inline <script> blocks convention`  [AMBIGUOUS]
  watersupply/templates/watersupply/partials/indicators_grid.html · relation: conceptually_related_to
- `DAG edge coverage (31 of 103 edges implemented)` → `Per-app DAG edge gap analysis`  [AMBIGUOUS]
  TODO.md · relation: conceptually_related_to

## Knowledge Gaps
- **70 isolated node(s):** `Scenario`, `TpwSource`, `WMSLayerAdmin`, `LossesChoices`, `LossesTypes` (+65 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 673 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `housing indicators_grid.html` and `No inline <script> blocks convention`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `watersupply indicators_grid.html` and `No inline <script> blocks convention`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `DAG edge coverage (31 of 103 edges implemented)` and `Per-app DAG edge gap analysis`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `City` connect `Administrative Units & Population` to `Water Supply Models`, `Land-Cover Release & Batching`, `Water Supply Calculations`, `Model Registry & Forms`, `Water Supply Models (2)`, `Administrative Units & Population (2)`, `LST Pipeline & NDVI`, `CBS & Enrichment Import`, `KNMI Importer`, `Urban Heat Models`, `CBS & Enrichment Import (2)`, `Nature Models`?**
  _High betweenness centrality (0.210) - this node is a cross-community bridge._
- **Why does `feature_form.html (map feature editor)` connect `LST/SVF Tool Frontend` to `Map Editing & Backup`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Are the 27 inferred relationships involving `City` (e.g. with `CityAdmin` and `cities_within()`) actually correct?**
  _`City` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `Neighborhood` (e.g. with `NeighborhoodAdmin` and `cities_within()`) actually correct?**
  _`Neighborhood` has 19 INFERRED edges - model-reasoned connections that need verification._