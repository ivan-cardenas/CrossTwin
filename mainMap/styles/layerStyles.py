"""
Map styling of the vector layers: Mapbox GL style layers, legend entries and
the catalog colour per registry key ('<app_label>.<Model>'). available_layers
(mainMap/views.py) attaches them to the layer catalog; layers without an entry
get a FALLBACK_COLORS colour and the default style in Layers.js. Land-cover
styles are built from the database instead (mainMap/styles/landCoverStyles.py).
"""
from .treeStyles import TREE_COLOR

# Building colour by Building.buildingType (derived from the BAG usage function
# in Building.save()). Listed in legend order; 'unknown' is the match fallback
# for buildings without a type and must stay last.
BUILDING_TYPE_COLORS = {
    'residential':   '#43a047',   # green
    'commercial':    '#1e88e5',   # blue
    'industrial':    '#b8860b',   # dark yellow
    'mixed':         '#00897b',   # blue-green
    'institutional': '#8e6cc0',   # purple
    'unknown':       '#9e9e9e',   # grey
}
BUILDING_TYPE_LABELS = [
    ('residential', 'Residential'),
    ('commercial', 'Commercial'),
    ('industrial', 'Industrial'),
    ('mixed', 'Mixed use'),
    ('institutional', 'Institutional'),
    ('unknown', 'Unknown type'),
]
# Extrusion height when Building.height_m is missing: floors x this, else the default.
BUILDING_FLOOR_HEIGHT_M = 3
BUILDING_DEFAULT_HEIGHT_M = 10


LAYER_STYLES = {
    # ── administrative hierarchy ────────────────────────────────────────────
    'administrative.Province': {
        'color': '#37474f',
        'layers': [
            {'type': 'fill',   'paint': {'fill-color': '#37474f', 'fill-opacity': 0.08}},
            {'type': 'line',   'paint': {'line-color': '#37474f', 'line-width': 2.5}},
        ],
    },
    'administrative.City': {
        'color': '#1565c0',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#1565c0', 'fill-opacity': 0.1}},
            {'type': 'line', 'paint': {'line-color': '#1565c0', 'line-width': 2}},
        ],
    },
    'administrative.District': {
        'color': '#1976d2',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#1976d2', 'fill-opacity': 0.12}},
            {'type': 'line', 'paint': {'line-color': '#1976d2', 'line-width': 1.5, 'line-dasharray': [4, 2]}},
        ],
    },
    'administrative.Neighborhood': {
        'color': '#42a5f5',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#42a5f5', 'fill-opacity': 0.15}},
            {'type': 'line', 'paint': {'line-color': '#42a5f5', 'line-width': 1, 'line-dasharray': [3, 2]}},
        ],
    },
    'physicalEnv.LandCoverVector': {
        'color': '#558b2f',
    },
    # layers + legend per request from the units present (mainMap/styles/soilStyles.py)
    'physicalEnv.SoilArea': {
        'color': '#a1887f',
    },

    # ── watersupply ────────────────────────────────────────────────────────
    'watersupply.UsersLocation': {
        'color': '#0277bd',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 5, 'circle-color': '#0277bd', 'circle-stroke-width': 1, 'circle-stroke-color': '#ffffff'}},
        ],
    },
    'watersupply.Watershed': {
        'color': '#0097a7',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#0097a7', 'fill-opacity': 0.15}},
            {'type': 'line', 'paint': {'line-color': '#0097a7', 'line-width': 1.5}},
        ],
    },
    'watersupply.PipeNetwork': {
        'color': '#00acc1',
        'layers': [
            {'type': 'line', 'paint': {'line-color': '#00acc1', 'line-width': 2.5, 'line-dasharray': [4, 1]}},
        ],
    },
    'watersupply.CoverageWaterSupply': {
        'color': '#26c6da',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#26c6da', 'fill-opacity': 0.2}},
            {'type': 'line', 'paint': {'line-color': '#26c6da', 'line-width': 1}},
        ],
    },
    'watersupply.AreaAffectedDrought': {
        'color': '#f57f17',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#f57f17', 'fill-opacity': 0.3}},
            {'type': 'line', 'paint': {'line-color': '#e65100', 'line-width': 1.5}},
        ],
    },

    # ── builtup ────────────────────────────────────────────────────────────
    'builtup.ZoningArea': {
        'color': '#f57c00',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#f57c00', 'fill-opacity': 0.2}},
            {'type': 'line', 'paint': {'line-color': '#f57c00', 'line-width': 1}},
        ],
    },
    'builtup.Street': {
        'color': '#8d6e63',
        'layers': [
            {'type': 'line', 'paint': {'line-color': '#8d6e63', 'line-width': 2}},
        ],
    },
    'builtup.Park': {
        'color': '#66bb6a',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#66bb6a', 'fill-opacity': 0.4}},
            {'type': 'line', 'paint': {'line-color': '#388e3c', 'line-width': 1}},
        ],
    },
    'builtup.Facility': {
        'color': '#ab47bc',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 7, 'circle-color': '#ab47bc', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff'}},
        ],
    },
    'builtup.Building': {
        'color': BUILDING_TYPE_COLORS['residential'],
        'legend': [{'label': label, 'color': BUILDING_TYPE_COLORS[key]} for key, label in BUILDING_TYPE_LABELS],
        'layers': [
            {'type': 'fill-extrusion', 'paint': {
                'fill-extrusion-color': [
                    'match', ['get', 'buildingType'],
                    *[v for key, _ in BUILDING_TYPE_LABELS[:-1] for v in (key, BUILDING_TYPE_COLORS[key])],
                    BUILDING_TYPE_COLORS['unknown'],
                ],
                # Stored height (height_m) when known, else floors x BUILDING_FLOOR_HEIGHT_M,
                # else BUILDING_DEFAULT_HEIGHT_M. The property is 'height_m', the model field name.
                'fill-extrusion-height': [
                    'case',
                    ['!=', ['get', 'height_m'], None], ['to-number', ['get', 'height_m']],
                    ['!=', ['get', 'numberFloors'], None],
                    ['*', ['to-number', ['get', 'numberFloors']], BUILDING_FLOOR_HEIGHT_M],
                    BUILDING_DEFAULT_HEIGHT_M,
                ],
                'fill-extrusion-base': 0,
                'fill-extrusion-opacity': 0.8,
            }},
        ],
    },
    'builtup.Property': {
        'color': '#ef5350',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 5, 'circle-color': '#ef5350', 'circle-stroke-width': 1, 'circle-stroke-color': '#ffffff'}},
        ],
    },

    # ── Energy ─────────────────────────────────────────────────────────────
    'Energy.BuildingEnergyLabel': {
        'color': '#66bb6a',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': [
                'match', ['get', 'energyLabel'],
                'A+++', '#00441b', 'A++', '#00622a', 'A+', '#037f39',
                'A', '#1a9850', 'B', '#66bd63', 'C', '#a6d96a',
                'D', '#fee08b', 'E', '#fdae61', 'F', '#f46d43', 'G', '#d73027',
                '#9e9e9e',
            ], 'fill-opacity': 0.65}},
            {'type': 'line', 'paint': {'line-color': '#37474f', 'line-width': 0.5}},
        ],
    },

    # ── housing ────────────────────────────────────────────────────────────
    'housing.HousingProject': {
        'color': '#ec407a',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#ec407a', 'fill-opacity': 0.25}},
            {'type': 'line', 'paint': {'line-color': '#ec407a', 'line-width': 1.5, 'line-dasharray': [3, 2]}},
        ],
    },

    # ── nature ─────────────────────────────────────────────────────────────
    'nature.ProtectedArea': {
        'color': '#2e7d32',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#2e7d32', 'fill-opacity': 0.2}},
            {'type': 'line', 'paint': {'line-color': '#1b5e20', 'line-width': 1.5}},
        ],
    },
    'nature.WaterWaysLN': {
        'color': '#1e88e5',
        'layers': [
            {'type': 'line', 'paint': {'line-color': '#1e88e5', 'line-width': 2}},
        ],
    },
    'nature.WaterWaysPG': {
        'color': '#039be5',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#039be5', 'fill-opacity': 0.35}},
            {'type': 'line', 'paint': {'line-color': '#0277bd', 'line-width': 1}},
        ],
    },
    
    'nature.WaterBodies': {
        'color': '#039be5',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#039be5', 'fill-opacity': 0.35}},
            {'type': 'line', 'paint': {'line-color': '#0277bd', 'line-width': 1}},
        ],
    },
    'nature.Forests': {
        'color': '#388e3c',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#388e3c', 'fill-opacity': 0.35}},
            {'type': 'line', 'paint': {'line-color': '#1b5e20', 'line-width': 1}},
        ],
    },
    # 3D tree models, layers built per request (mainMap/styles/treeStyles.py)
    'nature.Tree': {
        'color': TREE_COLOR,
    },
    'nature.GreenSpaces': {
        'color': '#81c784',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#81c784', 'fill-opacity': 0.4}},
            {'type': 'line', 'paint': {'line-color': '#388e3c', 'line-width': 1}},
        ],
    },

    # ── urban_heat ─────────────────────────────────────────────────────────
    'urban_heat.NatureBasedSolutionPolygon': {
        'color': '#43a047',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#43a047', 'fill-opacity': 0.4}},
            {'type': 'line', 'paint': {'line-color': '#2e7d32', 'line-width': 1.5}},
        ],
    },
    'urban_heat.NatureBasedSolutionPoint': {
        'color': '#66bb6a',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 6, 'circle-color': '#66bb6a', 'circle-stroke-width': 2, 'circle-stroke-color': '#2e7d32'}},
        ],
    },

    # ── weather ────────────────────────────────────────────────────────────
    'weather.WeatherStation': {
        'color': '#7e57c2',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 7, 'circle-color': '#7e57c2', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff'}},
        ],
    },
}

FALLBACK_COLORS = [
    '#3388ff', '#e74c3c', '#2ecc71', '#9b59b6', '#f39c12',
    '#1abc9c', '#e91e63', '#00bcd4', '#ff5722', '#607d8b',
    '#8bc34a', '#673ab7', '#ffeb3b', '#795548', '#009688',
]
