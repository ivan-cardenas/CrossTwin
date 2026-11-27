"""
Geometry of the small SVG line charts of the housing indicators (pure: no ORM, no
HTML). The template draws what this returns, so the chart looks the same in the
side panel and on the standalone dashboard and needs no JavaScript.

A series is {"key", "label", "points": [(x, y), ...]} with numeric x (a year) and y.
"""
import math

WIDTH, HEIGHT = 320, 150
PAD_LEFT, PAD_RIGHT, PAD_TOP, PAD_BOTTOM = 40, 10, 10, 22
Y_TICKS = 4   # intended number of gridlines; the step is rounded to 1, 2 or 5 x 10^n


def nice_step(span, ticks=Y_TICKS):
    """A round gridline step (1, 2 or 5 x 10^n) giving about `ticks` lines over `span`."""
    raw = span / max(ticks, 1)
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


def _label(value):
    return f"{value:,.0f}"


def line_chart(series, width=WIDTH, height=HEIGHT):
    """
    Chart geometry for the series that have points, or None when none has.

    Returns {"width", "height", "left", "right", "top", "bottom", "series":
    [{"key", "label", "path", "dots": [{"cx", "cy", "x", "y"}]}], "x_ticks":
    [{"x", "label"}], "y_ticks": [{"y", "label"}]}. The x axis is the years
    present (a single year is centred); the y axis starts at a round value below
    the lowest point and ends at a round value above the highest.
    """
    series = [s for s in series if s.get("points")]
    if not series:
        return None
    xs = sorted({x for s in series for x, _ in s["points"]})
    ys = [y for s in series for _, y in s["points"]]
    step = nice_step((max(ys) - min(ys)) or max(abs(max(ys)), 1.0) * 0.2)
    y_min, y_max = math.floor(min(ys) / step) * step, math.ceil(max(ys) / step) * step
    if y_max == y_min:
        y_max = y_min + step

    left, right, top, bottom = PAD_LEFT, width - PAD_RIGHT, PAD_TOP, height - PAD_BOTTOM

    def px(x):
        return round((left + right) / 2 if len(xs) == 1 else left + (x - xs[0]) / (xs[-1] - xs[0]) * (right - left), 1)

    def py(y):
        return round(bottom - (y - y_min) / (y_max - y_min) * (bottom - top), 1)

    drawn = []
    for s in series:
        points = sorted(s["points"])
        coords = [(px(x), py(y)) for x, y in points]
        drawn.append({
            "key": s["key"], "label": s["label"],
            "path": " ".join(f"{'M' if i == 0 else 'L'}{cx},{cy}" for i, (cx, cy) in enumerate(coords)) if len(coords) > 1 else "",
            # "dots": False draws the line only (a long extrapolation)
            "dots": [] if s.get("dots") is False else
                    [{"cx": cx, "cy": cy, "x": x, "y": _label(y)} for (cx, cy), (x, y) in zip(coords, points)],
        })
    y_ticks, value = [], y_min
    while value <= y_max + step / 2:
        y_ticks.append({"y": py(value), "label": _label(value)})
        value += step
    every = max(1, math.ceil(len(xs) / 6))   # at most about six year labels
    return {
        "width": width, "height": height, "left": left, "right": right, "top": top, "bottom": bottom,
        "series": drawn,
        "x_ticks": [{"x": px(x), "label": str(x)} for i, x in enumerate(xs) if i % every == 0],
        "y_ticks": y_ticks,
    }
