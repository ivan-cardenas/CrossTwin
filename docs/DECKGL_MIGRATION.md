# Mapbox GL JS → deck.gl: assessment and migration plan

Status: plan only, nothing is implemented. The assessment is based on the current map frontend (`mainMap/templates/mainMap.html`, `core/static/js/*.js`, `mainMap/views.py`) and on deck.gl **9.4** (September 2026).

## TL;DR

- **Is it possible?** Yes. But deck.gl is **not a basemap library**. It draws data layers; it has no vector basemap styles, labels, geocoder or map controls. So "switch to deck.gl" really means **deck.gl + a base map engine**. That engine can stay Mapbox GL JS or become MapLibre GL JS.
- **Would it help?** Yes for **large, 3-D and time-dependent data**: tens of thousands of buildings, land-cover polygons, 3D BAG / 3D Tiles, VoxCity voxels, hourly heat rasters, GPU filtering by year. It does **not** fix the slow parts measured in [PERFORMANCE.md](PERFORMANCE.md) §1: whole-table GeoJSON downloads and backend queries. Those need the backend fixes (bbox / MVT tiles) whichever renderer draws the result.
- **Recommendation: don't replace; add.** Keep Mapbox for the basemap, labels, controls, WMS/TiTiler rasters and the small administrative layers. Add deck.gl **inside** the same map with `MapboxOverlay({ interleaved: true })` and move only the heavy or 3-D layers to it. Optionally, as a separate later decision, swap Mapbox for **MapLibre + PDOK basemaps** to drop the Mapbox token and costs.

## 1. What the map uses from Mapbox today

| Mapbox feature | Where | deck.gl equivalent |
|---|---|---|
| `mapboxgl.Map`, camera (`easeTo`, `fitBounds`, `getCenter`, pitch/bearing), `sessionStorage` camera restore | `Map_init.js`, `Events.js`, `CityName.js`, `Panels.js` | Stays with the base map (deck.gl reads the camera from it in overlay mode) |
| Basemap styles `mapbox://styles/mapbox/*` (light/dark/streets/satellite/outdoors) | `Config.js:26` | None: needs a base map engine |
| Geocoder plugin, Navigation/Fullscreen/Geolocate/Scale controls | `Map_init.js:159-177` | None: stays with the base map (or the PDOK Locatieserver for Dutch addresses) |
| Built-in 3-D buildings (`composite` / `building` source-layer) | `Map_init.js:237` | Mapbox-only data; replace with 3D BAG via deck.gl if wanted |
| GeoJSON sources + `fill` / `line` / `circle` / `fill-extrusion` layers, styled by **Mapbox style-spec expressions** served from Django (`LAYER_STYLES` in `mainMap/styles/layerStyles.py`; land cover and soil built per request in `landCoverStyles.py` / `soilStyles.py`) | `Layers.js:90-186` | `GeoJsonLayer` / `MVTLayer` with JS accessors: **needs a style translator** (§4) |
| Raster tiles: WMS (incl. the authenticated proxy and animated time frames) and TiTiler COGs | `Layers.js:190-445`, `Map_init.js:278` | `TileLayer` + `BitmapLayer`, but Mapbox raster sources already work well, so **keep them in Mapbox** |
| Click popups (`mapboxgl.Popup`, `createPopupContent`), hover cursor, admin-unit click → panels | `Layers.js:168-176`, `Map_init.js:32` | deck.gl `onClick` / `onHover` picking; popups can still use `mapboxgl.Popup` |
| Layer visibility via `setLayoutProperty`, zoom-to-layer from the in-memory GeoJSON | `Layers.js:543-595`, `MapUI.js:91` | `layer.props.visible` + `overlay.setProps({layers})`; bounds from `/api/layers/<app>/<model>/bounds/` |

**Conclusion:** about 70% of the map code (camera, controls, basemap, rasters, WMS animation, panels) is not what deck.gl replaces. The part deck.gl improves is the vector-layer rendering in `Layers.js:addLayer`.

## 2. Benefits for CrossTwin specifically

| Benefit | Why it matters here |
|---|---|
| **Scale**: GPU-instanced rendering of 10⁵–10⁶ features, binary data (Arrow/`binary: true` MVT) | `builtup.Building`, `LandCoverVector` and `Street` layers are city- or province-sized; Mapbox `geojson` sources re-tile them on the main thread |
| **3-D**: `Tile3DLayer` (3D Tiles), `SimpleMeshLayer`, `PointCloudLayer`, `ColumnLayer` | 3D BAG buildings, VoxCity voxels / OBJ exports ([VOXCITY.md](VOXCITY.md) §4.5): Mapbox cannot draw these |
| **GPU filtering**: `DataFilterExtension` (`filterRange`, `categorySize`) | The year selector and thresholds (e.g. energy label, heat-stress class) can filter on the GPU with no refetch |
| **Aggregation**: `HexagonLayer`, `H3HexagonLayer`, `ScreenGridLayer`, `HeatmapLayer`, `ContourLayer` | Indicator density maps (water users, facilities, NBS points) without server work |
| **Time animation**: `TripsLayer`, animated attributes via `transitions` | Hourly UTCI/WBGT and scenario transitions (population what-if) can animate smoothly |
| **Picking**: `pickMultipleObjects`, `autoHighlight`, `highlightedObjectIndex` | Hover-highlight and multi-select for admin units / buildings |
| **No vendor lock for rendering**: works with Mapbox *and* MapLibre | Makes the optional move to MapLibre (§6) a base-map-only change |

## 3. Costs and risks

- **Styles live in the backend as Mapbox expressions.** `LAYER_STYLES` carries Mapbox paint dicts (`['match', ['get','energyLabel'], …]`, `['coalesce', ['get','height'], 10]`, `line-dasharray`). deck.gl uses JS accessor functions, and functions cannot come from Django JSON. You need a translator (§4) or `@deck.gl/json`.
- **Labels and text** are better in Mapbox (collision detection, style fonts). Keep labels in the basemap.
- **Dashed lines** need `PathStyleExtension`. Extrusion *with* Mapbox terrain is not aligned in deck.gl (deck data at z=0 renders at sea level when terrain is on).
- **Mapbox globe / non-Mercator projections are not supported** by `@deck.gl/mapbox`. The map uses Mercator today, so this is fine as long as it stays that way.
- **Input events**: in overlay mode deck.gl only receives the clicks and hovers Mapbox delegates (no `onDrag`). That covers what `Layers.js` does today.
- **Two layer registries.** `loadedLayers[key].layerIds` assumes Mapbox layer ids. Adding deck.gl means a `renderer` field and two code paths in `toggleLayerVisibility`, `zoomToLayer`, `changeBasemap` and `MapUI` counts.
- **No build step today.** The JS is plain `<script>` files with globals. deck.gl's UMD bundle (`https://cdn.jsdelivr.net/npm/deck.gl@9.4/dist.min.js`, global `deck`) keeps it that way. It is about 1 MB; load it only on `mainMap.html`.

## 4. Target architecture (hybrid, interleaved)

```
mapboxgl.Map (basemap, labels, controls, geocoder, camera)
 ├─ Mapbox layers: basemap · admin boundaries · WMS (incl. animated) · TiTiler COG rasters · groundwater
 └─ MapboxOverlay({ interleaved: true })          ← one instance, added with map.addControl(overlay)
       └─ deck.gl layers (beforeId: first symbol layer, so labels stay on top)
            GeoJsonLayer / MVTLayer  → Building (3-D), LandCoverVector, Street, Park, …
            Tile3DLayer              → 3D BAG / VoxCity (later)
            H3HexagonLayer / HeatmapLayer → aggregated indicators (later)
```

### New file `core/static/js/DeckLayers.js`

This follows the project rule of no inline `<script>`. It loads after `Layers.js` and before `Map_init.js`.

```js
// DeckLayers.js — deck.gl layers rendered inside the Mapbox map
let deckOverlay = null;
const deckLayers = {};            // key → deck.gl layer instance

function initDeckOverlay() {
  deckOverlay = new deck.MapboxOverlay({ interleaved: true, layers: [] });
  map.addControl(deckOverlay);
}

function renderDeckLayers() {
  deckOverlay.setProps({ layers: Object.values(deckLayers) });
}

function addDeckVectorLayer(layerConfig) {
  const { key, url, display_name, deck_style } = layerConfig;
  deckLayers[key] = new deck.GeoJsonLayer({
    id: key,
    data: url,                              // deck.gl fetches and parses off the main thread
    beforeId: firstSymbolLayerId(),
    pickable: true,
    autoHighlight: true,
    ...deckStyleToProps(deck_style, layerConfig.color),
    onClick: ({ object, coordinate }) => object && new mapboxgl.Popup()
      .setLngLat(coordinate)
      .setHTML(createPopupContent(object.properties, display_name, layerConfig.fields || {}))
      .addTo(map),
  });
  loadedLayers[key] = { renderer: 'deck', layerIds: [key], config: layerConfig };
  renderDeckLayers();
}

function setDeckLayerVisible(key, visible) {
  deckLayers[key] = deckLayers[key].clone({ visible });
  renderDeckLayers();
}
```

### Style translation

Add a `deck` key per entry in `LAYER_STYLES`, a **declarative** spec that the frontend turns into accessors. Keep the existing `layers` key for Mapbox so both renderers work during the migration:

```python
'builtup.Building': {
    'color': '#ffa726',
    'layers': [...],                       # unchanged, used while renderer == 'mapbox'
    'renderer': 'deck',
    'deck': {'extruded': True, 'elevation': {'field': 'height', 'default': 10},
             'fill': '#ffa726', 'opacity': 0.75},
},
'Energy.BuildingEnergyLabel': {
    'renderer': 'deck',
    'deck': {'fill': {'match': 'energyLabel',
                      'cases': {'A+++': '#00441b', 'A': '#1a9850', 'G': '#d73027'},
                      'default': '#9e9e9e'},
             'opacity': 0.65, 'line': '#37474f', 'lineWidth': 0.5},
},
```

```js
// DeckLayers.js
const hexToRgb = (h, a = 255) => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)).concat(a);

function colorAccessor(spec, alpha) {
  if (typeof spec === 'string') return hexToRgb(spec, alpha);
  const cases = Object.fromEntries(Object.entries(spec.cases).map(([k, v]) => [k, hexToRgb(v, alpha)]));
  const fallback = hexToRgb(spec.default, alpha);
  return f => cases[f.properties[spec.match]] || fallback;
}

function deckStyleToProps(s = {}, color) {
  const a = Math.round((s.opacity ?? 0.35) * 255);
  return {
    filled: true,
    stroked: !!s.line,
    extruded: !!s.extruded,
    getFillColor: colorAccessor(s.fill || color, a),
    getLineColor: colorAccessor(s.line || color, 255),
    getLineWidth: s.lineWidth ?? 1,
    lineWidthUnits: 'pixels',
    getElevation: s.elevation ? f => f.properties[s.elevation.field] ?? s.elevation.default : 0,
    getPointRadius: s.radius ?? 5, pointRadiusUnits: 'pixels',
  };
}
```

The alternative is `@deck.gl/json`'s `JSONConverter`, which accepts deck.gl-native JSON with `@@=` expressions. It is more powerful but a second DSL to learn. The small translator above only needs to cover the styles `LAYER_STYLES` uses today (flat colour, `match`, `coalesce` height, dash).

### Data: pair deck.gl with vector tiles

deck.gl renders faster, but `model_geojson` still sends the whole table ([PERFORMANCE.md](PERFORMANCE.md) §1). Add the MVT endpoint from §1.5 (`/api/layers/<app>/<model>/tiles/{z}/{x}/{y}.pbf`, `ST_AsMVT`) and use `deck.MVTLayer({ data: tileUrl, binary: true, … })` for the large layers. Then:
- `zoomToLayer` must use `/api/layers/<app>/<model>/bounds/` (it currently computes bounds from the in-memory GeoJSON, `Layers.js:570`);
- `MapUI.js:91`'s feature total must use the catalog `count` instead of `geojson.features.length`.

## 5. Phased plan

| Phase | Scope | Exit criteria | Effort |
|---|---|---|---|
| **0. Spike** | Add the deck.gl UMD script to `mainMap.html`; `initDeckOverlay()` in `map.on('load')`; render `builtup.Building` as an extruded `GeoJsonLayer` next to the Mapbox version | Measure first-render time, FPS while panning (Chrome performance panel), main-thread blocking, on the largest city. Go/no-go | 1–2 days |
| **1. Plumbing** | `DeckLayers.js`; `renderer` + `deck` keys in `LAYER_STYLES`, returned by `available_layers`; `addLayer` dispatches on `renderer`; `toggleLayerVisibility`, `zoomToLayer`, `changeBasemap` (deck overlay survives `setStyle`, but check `beforeId` still exists), `MapUI` counts handle both renderers; shared popup via `createPopupContent` | Every catalog layer works with `renderer='mapbox'` **or** `'deck'` by flipping one dict key | 3–5 days |
| **2. Move heavy layers** | `Building`, `BuildingEnergyLabel`, `LandCoverVector`, `Street`, `Park`, `nature.*` polygons → deck.gl; add the MVT endpoint and switch the largest to `MVTLayer`; `PathStyleExtension` for dashed pipes/streets; `DataFilterExtension` on `year` wired to the year selector | Same visuals as today (screenshot comparison), map usable with the full city building layer | 1–2 weeks |
| **3. New capabilities** | 3D BAG via `Tile3DLayer`; VoxCity outputs (`PointCloudLayer` / 3D Tiles, [VOXCITY.md](VOXCITY.md)); `H3HexagonLayer` / `HeatmapLayer` indicator views; animated scenario transitions | Driven by research needs; one feature at a time | open |
| **4. Optional: MapLibre** | Replace `mapbox-gl` with `maplibre-gl` v5+ and `@deck.gl/maplibre`; basemap from **PDOK BRT-Achtergrondkaart** vector tiles (or OpenFreeMap / MapTiler); geocoder → **PDOK Locatieserver**; rewrite `add3DBuildings` with 3D BAG | No Mapbox token, same UX. Take this only if Mapbox pricing/licensing becomes a concern | 1 week |

Keep **administrative layers in Mapbox** through phase 2. They are small, and `onAdminLayerLoaded` → `refreshActivePanel` depends on their Mapbox click events. Move them only when everything else is stable, re-implementing the click via deck.gl `onClick`.

## 6. MapLibre instead of Mapbox (the separate decision)

| | Mapbox GL JS v3 | MapLibre GL JS v5+ |
|---|---|---|
| Licence / cost | Proprietary; token; billed per map load above the free tier | BSD; no token |
| Basemaps | Mapbox styles (high quality, global) | Any: **PDOK BRT-Achtergrondkaart** (official Dutch, free), OpenFreeMap, MapTiler |
| deck.gl | `@deck.gl/mapbox` (no Mapbox globe) | `@deck.gl/maplibre` (recommended integration; globe support, experimental) |
| Geocoder | Mapbox Geocoder plugin | PDOK Locatieserver (Dutch addresses, free) or Nominatim (already used by `CityName.js`) |
| API | ≈ same (`Map`, `addSource`, `addLayer`, `Popup`, controls) | ≈ same: most of `Map_init.js` / `Layers.js` ports by renaming `mapboxgl` → `maplibregl` |

For a Dutch-only digital twin, MapLibre + PDOK is a natural fit, but it is independent of deck.gl. Do it before or after, not at the same time.

## 7. Testing

- Add a **Playwright** smoke test for `/` (Chromium is available in the dev container). It should load the page, toggle each catalog layer, click a feature, check the popup text, and switch basemaps. Run it under both renderer settings during phase 1.
- Performance baseline before phase 0 and after each phase: time to first render of the Building layer, FPS during a 5 s pan, JS heap size.
- Pin the deck.gl version in the script URL (`deck.gl@9.4.x`) and upgrade deliberately.

## 8. Open questions

1. How large do the Building / LandCoverVector layers get at province scale? This decides whether phase 2 needs MVT immediately.
2. Is Mapbox's free tier sufficient for the expected users? This decides phase 4.
3. Should the 3-D view (3D BAG, VoxCity) be a mode on the main map or a separate page with a standalone `deck.Deck` and `OrbitView`? Standalone gives full 3-D camera control, which `MapboxOverlay` cannot.

## Sources

- deck.gl `@deck.gl/mapbox` docs: [overview](https://github.com/visgl/deck.gl/blob/master/docs/api-reference/mapbox/overview.md) (interleaved mode on mapbox-gl v3+, no Mapbox non-Mercator projections, terrain alignment caveat, `beforeId`)
- deck.gl `@deck.gl/maplibre` docs: [overview](https://github.com/visgl/deck.gl/blob/master/docs/api-reference/maplibre/overview.md) (MapLibre v4.5.1 / v5 / v6)
- [deck.gl on npm](https://www.npmjs.com/package/deck.gl) (v9.4.0)
