# Map Layer System — Implementation Notes

This document covers the changes made to the map layer catalog, styling, and popup system.

---

## 1. Per-Model Color & Style Assignment

### Problem
Colors were assigned by cycling through a 15-color palette in the order `VECTOR_REGISTRY` iterated — unpredictable and impossible to control per layer without changing registration order.

### Solution
Replaced the cycling palette with `LAYER_STYLES` in `mainMap/styles/layerStyles.py` — a static dict keyed by `"app_label.ModelName"` (matching the `VECTOR_REGISTRY` key format).

```python
LAYER_STYLES = {
    'common.Province': {
        'color': '#37474f',          # used in the legend swatch
        'layers': [...]              # optional — Mapbox layer definitions
    },
    ...
}
```

- `color` is always required — used for the legend chip in the sidebar.
- `layers` is optional. If absent, the JS falls back to a default style based on `geometry_type`.
- A `FALLBACK_COLORS` list handles any model not listed in `LAYER_STYLES`.

**To add a new model's color**, add one entry to `LAYER_STYLES`. No migration, no DB change.

---

## 2. Full Mapbox Style Per Layer

### Problem
The frontend hardcoded paint objects based only on geometry type (point/line/polygon), making it impossible to use advanced Mapbox features like `fill-extrusion`, dashed lines, or data-driven expressions per layer.

### Solution
Each entry in `LAYER_STYLES` can include a `layers` list — an array of Mapbox layer definition objects (without `id` or `source`, which are added dynamically by JS):

```python
'builtup.Building': {
    'color': '#ffa726',
    'layers': [
        {'type': 'fill-extrusion', 'paint': {
            'fill-extrusion-color': '#ffa726',
            'fill-extrusion-height': ['coalesce', ['get', 'height'], 10],
            'fill-extrusion-opacity': 0.75,
        }},
    ],
},
'watersupply.PipeNetwork': {
    'color': '#00acc1',
    'layers': [
        {'type': 'line', 'paint': {'line-color': '#00acc1', 'line-width': 2.5, 'line-dasharray': [4, 1]}},
    ],
},
```

The `/api/layers/` endpoint returns these as `style_layers` on each layer object.

### Frontend (`Layers.js` — `addLayer`)
```js
if (style_layers && style_layers.length > 0) {
    style_layers.forEach((def, i) => {
        map.addLayer({
            id: `${key}-custom-${i}`,
            type: def.type,
            source: key,
            paint: def.paint || {},
            layout: def.layout || {},
        });
    });
} else {
    // falls back to geometry_type switch (point/line/polygon defaults)
}
```

Any valid [Mapbox GL JS paint/layout property](https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/) — including expressions — works inside those dicts.

---

## 3. URL Routing Fixes

### Problems found
1. `mainMap/urls.py` had a leading slash on the layers route: `'/api/layers/'`. Django strips the leading slash before matching, so this pattern **never matched**.
2. `Config.js` had `layersApiUrl: '../api/layers/'` — a relative URL that resolved to `/map/api/layers/` instead of `/api/layers/`.
3. `mainMap/templates/mainMap.html` had a hardcoded `window.CONFIG` block that **completely overrode** `Config.js` defaults (including the wrong `layersApiUrl: "/map/api/layers/"`).

### Fixes
- `mainMap/urls.py`: removed leading slash → `'api/layers/'`
- `Config.js`: `layersApiUrl: '/api/layers/'` (absolute path, unambiguous)
- `mainMap.html`: removed `window.CONFIG = {...}` entirely; now only passes the Mapbox token to `initializeUrbanTwinMap`:

```html
<script>
  document.addEventListener("DOMContentLoaded", () => {
    initializeUrbanTwinMap({ mapboxToken: "{{ mapbox_access_token }}" });
  });
</script>
```

`initializeUrbanTwinMap` (in `Map_init.js`) merges the passed object into the existing `CONFIG` via `{ ...CONFIG, ...config }`, so only server-side secrets need to come from the template. All defaults live in `Config.js`.

> **Insight:** Django URL patterns must never start with `/`. The router strips the leading slash before matching, so a pattern beginning with `/` will silently never match and fall through to a 404.

> **Insight:** `{% url 'namespace:name' %}` is the safe way to reference Django URLs from templates — it stays in sync with `urls.py` automatically if routes change.

---

## 4. Popup Formatting with Field Metadata

### Problem
Popups showed raw property values: unformatted numbers (no thousands separator), raw snake_case keys as labels, no units, and raw FK `_id` columns.

### Solution: Backend metadata extraction

`mainMap/views.py` now exports `fields` metadata per layer in the `/api/layers/` response:

```json
{
  "key": "common.Province",
  "fields": {
    "currentPopulation": {
      "label": "Current Population",
      "help_text": "Total current population in the Province",
      "unit": null
    },
    "populationDensity": {
      "label": "Population Density",
      "help_text": "Population density in people per square kilometer",
      "unit": "ppl/km²"
    },
    "area_km2": {
      "label": "Area Km2",
      "help_text": "Area in square kilometers",
      "unit": "km²"
    }
  }
}
```

Units are extracted automatically from `help_text` by `_extract_unit()` — a regex parser covering the units used in this codebase:

| Pattern matched in help_text | Displayed unit |
|---|---|
| "in square kilometers" / `km²` | `km²` |
| "in cubic meters per year" / `m³/yr` | `m³/yr` |
| "in liters per person per day" | `L/person/day` |
| "in EUR per cubic meter" | `€/m³` |
| "in percent" / `%` | `%` |
| "% per year" | `%/yr` |
| "in EUR" | `€` |
| "in hours per day" | `h/day` |
| "in centimeters per hour" | `cm/h` |
| "kg CO2/h" | `kg CO₂/h` |
| "in square meters" | `m²` |
| "in kilometers" | `km` |

To add a unit for a field, update its `help_text` in the model — the extractor picks it up without any code change.

### Solution: Frontend rendering (`Layers.js`)

`createPopupContent(properties, layerName, fields)` now:

- Uses `fields[key].label` (from `verbose_name`) instead of raw `key.replace(/_/g, ' ')`
- Formats numbers with `Intl.NumberFormat` (locale-aware thousands separator)
- Appends unit as a dimmed `<span class="popup-unit">` suffix
- Skips raw FK columns (`*_id`) where the relation's name is also present
- Skips `pk` and `id` fields
- Renders booleans as "Yes" / "No"
- Renders null/empty as `—`
- Shows `help_text` as a native tooltip (`title` attribute) on the label cell

### CSS additions (`mainMap.css`)
```css
.popup-value    { text-align: right; font-variant-numeric: tabular-nums; }
.popup-unit     { color: var(--text-tertiary); font-size: 9px; margin-left: 2px; }
.popup-label    { cursor: default; }   /* shows tooltip cursor on hover */
```

---

## 5. Styles Package, Data-Driven Legends and Related Popup Fields

### Styles package (`mainMap/styles/`)
All map styling lives in one package:

| Module | Contents |
|---|---|
| `layerStyles.py` | `LAYER_STYLES` (static style per registry key), `FALLBACK_COLORS`, building type colours/labels and extrusion heights |
| `landCoverStyles.py` | `build_landcover_style_and_legend()`: a `match` on `land_cover_type` for every class present on `LandCoverVector` |
| `soilStyles.py` | `SOIL_UNIT_COLORS` (the 305 soil units of the BRO Bodemkaart 1:50 000 legend, in legend order) and `build_soil_style_and_legend()` |
| `rasterStyles.py` | Raster colormaps, value ranges and legend stops (used by `core/views.py` for TiTiler tiles) |

`available_layers` reads `LAYER_STYLES` for every vector layer and, for land cover and the soil map, replaces `layers`/`legend` with the per-request result, so the legend lists only the classes actually imported.

### Soil map colours
The BRO legend colours each **main soil unit** (`first_soilcode` of the WFS, e.g. `Hn21`), not the full map code (`Hn21/Hd21`, `kHn21`). The importer stores it as `SoilType.unitCode`/`unitName` (the soil lookup's `defaults_from`, which also fills soil types imported earlier). The colours were sampled from the PDOK legend image (`legend/soilarea/soilslope.png`); three names occur twice in that legend, the first row is the marine (M) code, the second the river (R) code. Units not in `SOIL_UNIT_COLORS` and soil types without a `unitCode` (re-import the soil map) are drawn grey.

### Related fields in popups and styles
`POPUP_RELATED_FIELDS` in `mainMap/views.py` lists, per layer, columns of an FK's target to send along: `{'physicalEnv.SoilArea': {'soil_type': [('name', None), ('unitCode', 'Soil unit'), ...]}}`. `_geojson_sql` adds them to the existing `LEFT JOIN` as `<fk>__<field>` (still one query per layer), and `_field_metadata` gives them a label, unit and help text. A `…__name` property becomes the popup title (`_featureTitleKey`), and a style can `match` on them (`['get', 'soil_type__unitCode']`).

---

## File Map

| File | What changed |
|---|---|
| `mainMap/views.py` | Added `LAYER_STYLES`, `_FALLBACK_COLORS`, `_extract_unit()`, `_field_metadata()`; updated `available_layers` to return `color`, `style_layers`, `fields` (styles since moved to `mainMap/styles/`, see §5) |
| `mainMap/styles/` | §5: `layerStyles.py`, `soilStyles.py`, `landCoverStyles.py` and `rasterStyles.py` (the last two moved from `core/`) |
| `mainMap/views.py` | §5: `POPUP_RELATED_FIELDS`, `_popup_related_fields()`, `_field_meta_entry()`; `mm/h` unit |
| `physicalEnv/models.py`, `importer/` | §5: `SoilType.unitCode`/`unitName`, `defaults_from` on `__fk_lookup__` |
| `mainMap/urls.py` | Removed leading `/` from `api/layers/` route |
| `mainMap/templates/mainMap.html` | Removed hardcoded `window.CONFIG`; template now only passes `mapboxToken` |
| `common/static/js/Config.js` | `layersApiUrl` set to `'/api/layers/'` (absolute); is now the single source of truth for all map config defaults |
| `common/static/js/Layers.js` | `addLayer` uses `style_layers` when present; `createPopupContent` updated with formatting, labels, units |
| `common/static/css/mainMap.css` | Added `.popup-header`, `.popup-table`, `.popup-label`, `.popup-value`, `.popup-unit` |
