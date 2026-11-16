"""
Geometry for the population "curves" graph of the map's bottom dock.

The look follows Photoshop's Curves dialog: a dark plot with a regular grid,
one smooth curve, small square handles on it, and (added here) a shaded band for
the 67% forecast interval. Everything is computed server-side as SVG path data so
the template only has to draw it; the hover read-out in panels.js works from the
per-year `points` list.
"""
import json
import math

from administrative.calculations.population import (
    EXTRAPOLATION_LABEL, REFERENCE_YEAR, is_extrapolated, population_by_year, population_curve, projection_years,
)

WIDTH, HEIGHT = 760, 230
MARGIN = {'left': 54, 'right': 16, 'top': 12, 'bottom': 26}
# CBS 85173NED forecasts out to 2050; the axis always spans at least this
# horizon even when only part of it has been imported yet, so the empty
# years on the right read as "not imported" rather than making the graph
# look like it stops early.
FORECAST_END_YEAR = 2050
VARIANTS = ('low', 'prognose', 'high')
VARIANT_LABELS = {'low': 'Lower bound', 'prognose': 'Median forecast', 'high': 'Upper bound'}
HANDLE_SIZE = 5.5  # px side of a handle square
HANDLE_EVERY = 5   # a square handle every N years (plus first, last and the selected year)
# A selected year beyond the imported CBS years (e.g. 2100) is drawn as a
# dashed trend (population.extrapolate) sampled every TREND_STEP years.
TREND_STEP = 5


def short_number(value):
    """164800 -> '164.8k', 2_100_000 -> '2.1M' (axis labels)."""
    value = float(value)
    if abs(value) >= 1_000_000:
        text, suffix = f"{value / 1_000_000:.2f}", 'M'
    elif abs(value) >= 1_000:
        text, suffix = f"{value / 1_000:.1f}", 'k'
    else:
        return f"{value:.0f}"
    return text.rstrip('0').rstrip('.') + suffix


def nice_step(raw):
    """Round a raw step up to 1, 2, 2.5 or 5 x 10^n so the grid labels are round numbers."""
    if raw <= 0:
        return 1
    exponent = math.floor(math.log10(raw))
    fraction = raw / 10 ** exponent
    for nice in (1, 2, 2.5, 5, 10):
        if fraction <= nice:
            return nice * 10 ** exponent


def monotone_segments(points):
    """
    Cubic Bezier segments ((p0), (c1), (c2), (p3)) through `points` [(x, y)...]
    using Fritsch-Carlson monotone interpolation: smooth like a Photoshop curve
    but never overshooting the data (so a low/median/high trio never crosses).
    """
    n = len(points)
    if n < 2:
        return []
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    dx = [xs[i + 1] - xs[i] for i in range(n - 1)]
    slope = [(ys[i + 1] - ys[i]) / dx[i] if dx[i] else 0.0 for i in range(n - 1)]

    tangent = [slope[0]]
    for i in range(1, n - 1):
        tangent.append(0.0 if slope[i - 1] * slope[i] <= 0 else (slope[i - 1] + slope[i]) / 2)
    tangent.append(slope[-1])

    for i in range(n - 1):
        if slope[i] == 0:
            tangent[i] = tangent[i + 1] = 0.0
            continue
        a, b = tangent[i] / slope[i], tangent[i + 1] / slope[i]
        h = a * a + b * b
        if h > 9:
            t = 3 / math.sqrt(h)
            tangent[i], tangent[i + 1] = t * a * slope[i], t * b * slope[i]

    segments = []
    for i in range(n - 1):
        third = dx[i] / 3
        segments.append((
            (xs[i], ys[i]),
            (xs[i] + third, ys[i] + tangent[i] * third),
            (xs[i + 1] - third, ys[i + 1] - tangent[i + 1] * third),
            (xs[i + 1], ys[i + 1]),
        ))
    return segments


def _fmt(p):
    return f"{p[0]:.1f},{p[1]:.1f}"


def path_d(points):
    """SVG path data of the smooth curve through `points`."""
    segments = monotone_segments(points)
    if not segments:
        return f"M{_fmt(points[0])}" if points else ""
    d = f"M{_fmt(segments[0][0])}"
    for _p0, c1, c2, p3 in segments:
        d += f" C{_fmt(c1)} {_fmt(c2)} {_fmt(p3)}"
    return d


def band_d(upper, lower):
    """Closed SVG path of the area between two curves (upper left->right, lower right->left)."""
    up, low = monotone_segments(upper), monotone_segments(lower)
    if not up or not low:
        return ""
    d = f"M{_fmt(up[0][0])}"
    for _p0, c1, c2, p3 in up:
        d += f" C{_fmt(c1)} {_fmt(c2)} {_fmt(p3)}"
    d += f" L{_fmt(low[-1][3])}"
    for p0, c1, c2, _p3 in reversed(low):     # a reversed cubic swaps its control points
        d += f" C{_fmt(c2)} {_fmt(c1)} {_fmt(p0)}"
    return d + " Z"


def _year_ticks(first, last):
    """
    Vertical grid years: multiples of 5 inside the range, 10 for a span over
    30 years and 25 over 60 (2023-2100: 2025, 2050, 2075, 2100); the ends for
    a short range.
    """
    span = last - first
    every = 5 if span <= 30 else 10 if span <= 60 else 25
    ticks = [y for y in range(first, last + 1) if y % every == 0]
    return ticks if len(ticks) >= 2 else sorted({first, last})


def build_population_chart(unit, scenario, growth, year, current):
    """
    Chart data for `unit`, or None when no projection is imported for it.

    scenario: the highlighted variant; growth: extra %/yr, applied only to the
    highlighted variant so the 67% band always reflects the original CBS
    prediction and only the tested curve moves; year: the selected year
    (marker, may be None); current: the unit's current population (dashed
    reference line).
    """
    scenario = scenario if scenario in VARIANTS else 'prognose'
    # The band (low/high) and the dashed median reference always reflect the
    # original CBS prediction, unaffected by the what-if slider; only the
    # highlighted 'selected' curve is computed with `growth` applied, so
    # dragging the slider moves that curve without moving the band under it.
    by_year = {s: {p['year']: p['population'] for p in population_curve(unit, s, 0)} for s in VARIANTS}
    selected = {p['year']: p['population'] for p in population_curve(unit, scenario, growth)}
    main = selected or by_year['prognose']
    if not main:
        return None

    years = sorted(by_year['prognose'].keys() | by_year['low'].keys() | by_year['high'].keys() | selected.keys())
    data_first, data_last = years[0], years[-1]

    # A selected year past the imported years: the CBS trend extrapolated
    # (the same values the indicator panels use), from the last imported year.
    trend_years = []
    trend = trend_by = {}
    if year is not None and year > data_last and is_extrapolated(unit, year):
        trend_years = sorted({*range(data_last, year, TREND_STEP), year})
        trend = population_by_year(unit, trend_years, scenario, growth)
        trend_by = {s: population_by_year(unit, trend_years, s, 0) for s in ('low', 'high')}

    # The axis always spans at least REFERENCE_YEAR..FORECAST_END_YEAR (2025-2050),
    # widening around whatever has actually been imported and the trend.
    first = min(data_first, REFERENCE_YEAR)
    last = max(data_last, FORECAST_END_YEAR, trend_years[-1] if trend_years else 0)

    all_values = ([v for s in VARIANTS for v in by_year[s].values()] + list(selected.values())
                  + list(trend.values()) + [v for t in trend_by.values() for v in t.values()]
                  + [current or 0])
    lo, hi = min(all_values), max(all_values)
    step = nice_step((hi - lo) / 4 or max(hi, 1) / 4)
    y_min = math.floor(lo / step) * step
    y_max = math.ceil(hi / step) * step
    if y_max == y_min:
        y_max = y_min + step

    m = MARGIN
    x0, x1 = m['left'], WIDTH - m['right']
    y0, y1 = m['top'], HEIGHT - m['bottom']          # y0 = top, y1 = bottom of the plot

    def x_of(y):
        return (x0 + x1) / 2 if last == first else x0 + (y - first) / (last - first) * (x1 - x0)

    def y_of(v):
        return y1 - (v - y_min) / (y_max - y_min) * (y1 - y0)

    def pts(series, over=years):
        return [(x_of(y), y_of(series[y])) for y in over if y in series]

    grid_h, value = [], y_min
    while value <= y_max + step / 100:
        y = y_of(value)
        grid_h.append({'y': round(y, 1), 'text_y': round(y + 3, 1), 'label': short_number(value)})
        value += step
    grid_v = [{'x': round(x_of(y), 1), 'label': str(y)} for y in _year_ticks(first, last)]

    handle_years = {y for y in years if (y - data_first) % HANDLE_EVERY == 0} | {data_first, data_last}
    if year in selected:
        handle_years.add(year)
    handles = [{
        'x': round(x_of(y), 1), 'y': round(y_of(selected[y]), 1), 'year': y, 'active': y == year,
        'rx': round(x_of(y) - HANDLE_SIZE / 2, 1), 'ry': round(y_of(selected[y]) - HANDLE_SIZE / 2, 1),
    } for y in sorted(handle_years)]

    points = [{
        'year': y, 'x': round(x_of(y), 1),
        'low': by_year['low'].get(y), 'median': by_year['prognose'].get(y), 'high': by_year['high'].get(y),
        'y_low': round(y_of(by_year['low'][y]), 1) if y in by_year['low'] else None,
        'y_median': round(y_of(by_year['prognose'][y]), 1) if y in by_year['prognose'] else None,
        'y_high': round(y_of(by_year['high'][y]), 1) if y in by_year['high'] else None,
    } for y in years]
    for y in trend_years[1:]:
        points.append({
            'year': y, 'x': round(x_of(y), 1), 'trend': True,
            'low': trend_by['low'][y], 'median': trend[y], 'high': trend_by['high'][y],
            'y_low': round(y_of(trend_by['low'][y]), 1),
            'y_median': round(y_of(trend[y]), 1),
            'y_high': round(y_of(trend_by['high'][y]), 1),
        })

    marker = None
    if year in selected:
        marker = {'x': round(x_of(year), 1), 'year': year, 'y': round(y_of(selected[year]), 1)}
    elif year in trend:
        marker = {'x': round(x_of(year), 1), 'year': year, 'y': round(y_of(trend[year]), 1), 'trend': True}
        handles.append({
            'x': marker['x'], 'y': marker['y'], 'year': year, 'active': True,
            'rx': round(marker['x'] - HANDLE_SIZE / 2, 1), 'ry': round(marker['y'] - HANDLE_SIZE / 2, 1),
        })

    return {
        'width': WIDTH, 'height': HEIGHT,
        'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'plot_w': x1 - x0, 'plot_h': y1 - y0,
        'label_y': y1 + 15,
        'grid_h': grid_h, 'grid_v': grid_v,
        'band_path': band_d(pts(by_year['high']), pts(by_year['low'])),
        'low_path': path_d(pts(by_year['low'])), 'high_path': path_d(pts(by_year['high'])),
        'median_path': path_d(pts(by_year['prognose'])),
        'selected_path': path_d(pts(selected)),
        'has_trend': bool(trend_years),
        'trend_path': path_d(pts(trend, trend_years)) if trend_years else '',
        'trend_low_path': path_d(pts(trend_by['low'], trend_years)) if trend_years else '',
        'trend_high_path': path_d(pts(trend_by['high'], trend_years)) if trend_years else '',
        'trend_label': EXTRAPOLATION_LABEL,
        'scenario': scenario, 'variant_label': VARIANT_LABELS[scenario],
        'baseline': {
            'y': round(y_of(current), 1), 'text_y': round(y_of(current) - 4, 1),
            'label': short_number(current),
        } if current else None,
        'tick_x': x0 - 7, 'baseline_x': x1 - 4, 'handle_size': HANDLE_SIZE,
        'handles': handles, 'marker': marker,
        'first_year': first, 'last_year': last,
        'points_json': json.dumps(points, separators=(',', ':')),
    }


def build_population_stats(unit, scenario, growth, year, current):
    """
    Numbers shown next to the graph: today, the selected year, the change and the
    interval. `has_projection` is False when there is no projection for the
    year (the value would just be today's population, which must not be
    presented as a forecast). A year beyond the imported CBS years (2100)
    is the CBS trend extrapolated: `extrapolated` is then True and the
    panel labels it.
    """
    scenario = scenario if scenario in VARIANTS else 'prognose'
    stats = {'current': current or 0, 'year': year, 'has_projection': False}
    extrapolated = is_extrapolated(unit, year)
    if year is None or (year not in projection_years(unit) and not extrapolated):
        return stats
    # The interval is the original CBS prediction (growth=0); only the
    # highlighted scenario's projected value moves with the what-if slider.
    band = {s: population_by_year(unit, [year], s, 0)[year] for s in VARIANTS}
    projected = population_by_year(unit, [year], scenario, growth)[year]
    stats.update({
        'has_projection': True,
        'extrapolated': extrapolated,
        'variant_label': VARIANT_LABELS[scenario],
        'projected': projected,
        'low': band['low'], 'high': band['high'],
        'delta': projected - (current or 0),
        'delta_pct': round((projected - current) / current * 100, 1) if current else None,
    })
    return stats
