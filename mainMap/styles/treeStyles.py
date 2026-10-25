"""
Map style of nature.Tree: green dots when zoomed out, a 3D glTF tree per point
from TREE_MODEL_MIN_ZOOM on (a Mapbox GL JS v3 `model` layer, which instances
one model over every feature of the GeoJSON source). Built per request in
available_layers (mainMap/views.py) because the model URL comes from
static(), which needs the storage backend.
"""
from django.templatetags.static import static

TREE_COLOR = '#2e7d32'
TREE_MODEL_PATH = 'models/3D/Test_Tree.glb'

# Size of Test_Tree.glb in metres (glTF units), measured from its mesh bounds
# plus the node translation: trunk base to crown top. A tree of height h is
# drawn at scale h / TREE_MODEL_HEIGHT_M.
TREE_MODEL_HEIGHT_M = 20.27
# Height used when Tree.height_m is missing (most OSM trees have none).
TREE_DEFAULT_HEIGHT_M = 10
# Scale stops end here; interpolate clamps beyond the last stop, so taller
# (mis-tagged) trees are capped at this height.
TREE_MAX_HEIGHT_M = 50

# Below this zoom a tree is a few pixels tall; the dots stay instead.
TREE_MODEL_MIN_ZOOM = 15


def _uniform(value):
    return ['literal', [value, value, value]]


def build_tree_style():
    """style_layers for nature.Tree. The circle layer comes first: it is the
    click target for popups (Layers.js binds them to the first layer) and
    stays queryable after it fades out under the models."""
    # coalesce before to-number: to-number turns null into 0, not into a
    # failure, so ['coalesce', ['to-number', ...], default] would draw every
    # tree without a height at scale 0 (invisible).
    height = ['to-number', ['coalesce', ['get', 'height_m'], TREE_DEFAULT_HEIGHT_M]]
    # Model scale proportional to the stored height: linear from 0 so that
    # scale = h / TREE_MODEL_HEIGHT_M exactly, clamped at TREE_MAX_HEIGHT_M.
    scale = [
        'interpolate', ['linear'], height,
        0, _uniform(0),
        TREE_MAX_HEIGHT_M, _uniform(round(TREE_MAX_HEIGHT_M / TREE_MODEL_HEIGHT_M, 4)),
    ]
    # Spin each tree by a pseudo-random angle derived from its id so that a
    # row of identical models does not look stamped.
    heading = ['%', ['*', ['to-number', ['get', 'id'], 0], 137.5], 360]
    rotation = ['interpolate', ['linear'], heading,
                0, ['literal', [0, 0, 0]], 360, ['literal', [0, 0, 360]]]
    fade_out = ['interpolate', ['linear'], ['zoom'],
                TREE_MODEL_MIN_ZOOM, 1, TREE_MODEL_MIN_ZOOM + 1, 0]

    return [
        {'type': 'circle', 'paint': {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 1, TREE_MODEL_MIN_ZOOM, 5],
            'circle-color': TREE_COLOR,
            'circle-opacity': fade_out,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#ffffff',
            'circle-stroke-opacity': fade_out,
        }},
        {'type': 'model', 'minzoom': TREE_MODEL_MIN_ZOOM,
         # The URL is also the model id: Layers.js registers it with
         # map.addModel() before adding the layer (a runtime layer never
         # fetches a URL given directly as model-id).
         'layout': {'model-id': static(TREE_MODEL_PATH)},
         'paint': {
            'model-scale': scale,
            'model-rotation': rotation,
            'model-cast-shadows': True,
            'model-receive-shadows': True,
            'model-opacity': 1,
        }},
    ]
