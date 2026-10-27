"""
Map styles set by staff in the map's settings panel (mainMap/settings_views.py),
merged on top of the defaults in this package. The code holds the default;
a mainMap.LayerStyleOverride row holds only what differs from it, so
deleting the row resets the layer, and a changed default still reaches
every property nobody overrode.

Vector layers: `vector_style(key)` is the one place that resolves a layer's
catalog colour, Mapbox style layers and legend (default + override); the
layer catalog and the settings form both use it. An override can set the
catalog colour, any scalar paint property of a style layer (a colour, an
opacity, a width) and the colours of a categorical `match` expression
(land-cover classes, soil units, building types), the legend following.

Rasters: overrides are keyed like the defaults in rasterStyles.py (the
raster's `index`, else its model), and `apply_raster_override` swaps the
colormap and value range before the tile URL and legend are built.
"""
import copy
import re

from .landCoverStyles import build_landcover_style_and_legend
from .layerStyles import FALLBACK_COLORS, LAYER_STYLES
from .soilStyles import build_soil_style_and_legend
from .treeStyles import build_tree_style

HEX_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
# Legend `value` of the colour a `match` falls back to (unknown building type,
# soil units without a legend colour).
OTHER = '__other__'


def base_vector_style(key, fallback_color=FALLBACK_COLORS[0]):
    """(color, style_layers, legend) of a vector layer as the code defines it."""
    entry = LAYER_STYLES.get(key, {})
    style_layers = entry.get('layers')
    legend = entry.get('legend')
    if key == 'physicalEnv.LandCoverVector':
        # Categorical colour per class_name, computed per request since
        # LandCoverClasses rows are get_or_create'd from source data.
        try:
            style_layers, legend = build_landcover_style_and_legend()
        except Exception:
            legend = None
    elif key == 'physicalEnv.SoilArea':
        # Same idea: colours of the BRO soil map legend, for the soil units imported.
        style_layers, legend = build_soil_style_and_legend()
    elif key == 'nature.Tree':
        # 3D tree model, whose URL static() resolves per request.
        style_layers = build_tree_style()
    return entry.get('color', fallback_color), style_layers, legend


def vector_overrides():
    """Registry key -> override data of every restyled vector layer (one query)."""
    from mainMap.models import LayerStyleOverride
    return dict(LayerStyleOverride.objects.filter(kind=LayerStyleOverride.VECTOR).values_list('key', 'data'))


def vector_style(key, fallback_color=FALLBACK_COLORS[0], overrides=None):
    """
    (color, style_layers, legend) with the layer's override applied.
    The catalog passes `overrides` (vector_overrides()) to query once per request.
    """
    if overrides is None:
        overrides = vector_overrides()
    color, style_layers, legend = base_vector_style(key, fallback_color)
    return apply_vector_override(color, style_layers, legend, overrides.get(key))


def apply_vector_override(color, style_layers, legend, data):
    """The default style with `data` (a LayerStyleOverride.data) applied; the inputs are not changed."""
    if not data:
        return color, style_layers, legend
    style_layers = copy.deepcopy(style_layers)
    legend = copy.deepcopy(legend)
    color = data.get('color') or color

    for index, props in (data.get('paint') or {}).items():
        try:
            paint = style_layers[int(index)].setdefault('paint', {})
        except (TypeError, ValueError, IndexError):
            continue   # the default lost that style layer since the override was saved
        for prop, value in props.items():
            if is_scalar(paint.get(prop)):
                paint[prop] = value

    categories = data.get('categories') or {}
    if categories:
        for layer in style_layers or []:
            for prop, value in layer.get('paint', {}).items():
                if is_color_match(value):
                    layer['paint'][prop] = _recolor_match(value, categories)
        for item in legend or []:
            if item.get('value') in categories:
                item['color'] = categories[item['value']]
    return color, style_layers, legend


def is_scalar(value):
    """A paint value the settings form can edit: a hex colour or a number (not an expression)."""
    return (isinstance(value, str) and bool(HEX_COLOR.match(value))) or \
        (isinstance(value, (int, float)) and not isinstance(value, bool))


def is_color_match(value):
    """['match', input, v1, '#c1', v2, '#c2', ..., '#fallback'] with colour outputs."""
    if not (isinstance(value, list) and len(value) >= 3 and value[0] == 'match' and len(value) % 2 == 1):
        return False
    outputs = value[3:-1:2] + [value[-1]]
    return all(isinstance(c, str) and HEX_COLOR.match(c) for c in outputs)


def match_categories(value):
    """[(category, colour)] of a colour `match`, the fallback as OTHER."""
    pairs = [(value[i], value[i + 1]) for i in range(2, len(value) - 1, 2)]
    return pairs + [(OTHER, value[-1])]


def _recolor_match(value, categories):
    out = list(value)
    for i in range(2, len(out) - 1, 2):
        if out[i] in categories:
            out[i + 1] = categories[out[i]]
    if OTHER in categories:
        out[-1] = categories[OTHER]
    return out


def raster_override(style_key):
    """Override data for a raster style key, or None."""
    from mainMap.models import LayerStyleOverride
    return (LayerStyleOverride.objects.filter(kind=LayerStyleOverride.RASTER, key=style_key)
            .values_list('data', flat=True).first())


def apply_raster_override(style, data):
    """(colormap, rescale, label, unit) with an override's colormap / range applied."""
    if not data:
        return style
    colormap, rescale, label, unit = style
    if data.get('colormap'):
        colormap = data['colormap']
    if 'rescale' in data:
        rescale = tuple(data['rescale']) if data['rescale'] else None
    return colormap, rescale, label, unit
