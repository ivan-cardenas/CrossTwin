# Indicator style guide

How an indicator card, gauge, slider and "On map" button must look and be marked up, so every domain (`watersupply`, `urban_heat`, `housing`, `builtup`, new ones) renders the same. Style source: `core/static/css/indicators.css` (section "Metrics style" and below). Tokens: `core/static/css/theme.css`. Frontend rules (HTMX partial, no inline `<script>`, JS in `core/static/js/indicators/<domain>.js`) stay as in `.claude/CLAUDE.md`.

## Rules

1. **Tokens only.** No hex or `rgba(255,255,255,…)` in indicator CSS or markup. Use `var(--text-primary)`, `--text-tertiary`, `--border`, `--accent`, `--accent-rgb`, `--surface-*`. Both themes (`data-theme="dark|light"`) must work.
2. **Data colours are the exception.** Status colours (`--success/--warning/--error`), series colours (`--series-supply`, `--series-demand`) and the card identity colours `--accent2` (brick), `--accent3` (ochre) carry meaning. Do not use them for decoration.
3. **Fonts.** Names (indicator names, administrative unit name): `--font-display` (Saira Extra Condensed), uppercase, kept narrow to cut clutter. Figures: `--font-display`. Captions, units, kickers, numbers in tables: `--font-mono`, uppercase, `letter-spacing: var(--tracking-label)`.
4. **Hairlines, not shadows.** 1px borders, `border-radius` 0 inside the grid, no box-shadow.
5. **Motion.** Cards rise in on render (CSS only, so HTMX swaps re-animate). Arcs and bars animate with `var(--ease-out)`. Everything is disabled under `prefers-reduced-motion`.

## Card anatomy

```html
<div class="grid">
  <div class="card [c2|c3] [wide] [gauge]">          <!-- c2 = brick, c3 = ochre identity colour -->
    <div class="gauge-header">                        <!-- plain cards: icon + label row -->
      <div class="card-icon">💧</div>                 <!-- optional, rendered as a quiet grey glyph -->
      <div class="card-label">Indicator name</div>    <!-- the NAME: brightest text on the card -->
      {% info_help "<domain>.<card>" %}               <!-- "?" help -->
      {% include "partials/_show_on_map.html" with layers="app.Model" label="indicator name" %}
    </div>
    <div class="card-value">42<span class="card-unit">…</span></div>   <!-- big condensed figure -->
    <div class="card-unit">m³ per day</div>                            <!-- mono caption under a hairline -->
  </div>
</div>
```

- The grid numbers cards automatically (`01 —` in accent colour before the name via a CSS counter). Do not hand-write numbers.
- **Name** = `.card-label`: `--font-display` 1.05rem, uppercase, `--text-primary`. Keep it short and noun-like ("Green Space per Inhabitant"). No trailing units.
- **Figure** = `.card-value`: `--font-display`, tabular numerals. One figure per card; secondary values go in the caption or a bar.
- **Caption** = `.card-unit`: mono, uppercase, tertiary, hairline above it.
- Never add a coloured left stripe; identity colour appears only in the number prefix and the hover hairline.

## Panel header (side-panel partial)

```html
<div class="ind-kicker">Housing Indicators</div>          <!-- mono kicker -->
<div class="ind-unit">{{ location }} <span class="ind-year">· {{ year }}</span></div>   <!-- administrative unit, condensed -->
```

No inline styles in the header.

## "On map" button

Always `{% include "partials/_show_on_map.html" … %}` (never hand-rolled markup). It renders a pill: pin icon + `On map`, accent outline; pressed (`aria-pressed="true"`) it fills with `--accent`. Place it last in the header row, after the `?` help. Hidden automatically on standalone dashboards (no map). Behaviour is documented in the partial and `Layers.js::focusCardLayers`.

## Gauges

Markup stays as in the grid partials (SVG arc, `data-gauge-id`, `data-gauge-val`, `data-gauge-display`; JS in `core/static/js/indicators/<domain>.js` animates `stroke-dashoffset`). Style is applied by CSS, so do not restyle in markup:

| Part | Look |
|---|---|
| Arc / ring | 3px stroke, butt caps, track `--surface-hover` (CSS maps `rgba(255,255,255,…)` strokes), progress `--accent` or a status colour set by JS |
| Number (`<text font-weight="700">`) | `--font-display` 22px, `--text-primary` |
| Sub-caption (`<text font-family="var(--font-mono)">`) | 6px mono uppercase, `--text-tertiary` |

Rules for new gauges: use `stroke-linecap="round"` on the progress path (CSS turns it into the hairline style), keep the track stroke as `rgba(255,255,255,0.06)` or use `var(--surface-hover)`, give the number `font-weight="700"` and the caption `font-family="var(--font-mono)"` so the selectors match. Colour by status only through JS thresholds that are named and cited constants (see Reproducibility in `.claude/CLAUDE.md`).

## Sliders (what-if)

```html
<div class="slider-container whatif-only">
  <div class="slider-header">
    <div class="slider-header-left"><div class="card-label">What-if name</div> {% info_help "…" %}</div>
    <div class="slider-value-display"><span id="…-display">0</span><span class="slider-unit">ha</span></div>
  </div>
  <div class="slider-zones-container">
    <div class="slider-zones"><div class="sz-ok"></div><div class="sz-warn"></div><div class="sz-bad"></div></div>
    <div class="slider-zone-wrap"><input class="zone-slider" type="range" …></div>
    <div class="slider-threshold-labels"><span>…</span></div>
  </div>
</div>
```

- 2px rail split into zones (`sz-ok/warn/bad` use the status tokens), hollow ring thumb in `--thumb-col` (defaults to brick), condensed value on the right, mono unit and threshold labels.
- Sliders never write data: they call `recalculate_indicators` with overrides (DAG contract rule 8).
- Plain weather-style `<input type="range">` rows use `accent-color: var(--accent)`; no custom colours.

## Checklist for a new indicator

- [ ] Card uses the anatomy above; name, figure and caption classes only.
- [ ] No hex colours in the new CSS/markup except data colours; checked in light and dark.
- [ ] `{% info_help %}` entry added in `core/indicator_help.py`; equation/DAG docs updated per the DAG contract.
- [ ] "On map" via the shared partial, with the layers behind the number.
- [ ] Standalone page and side-panel partial share the same markup and JS file.
- [ ] Works after an HTMX swap and with `prefers-reduced-motion`.
