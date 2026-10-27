"""
The map's settings panel (staff only): which layers are editable on the map,
and the map styles (mainMap/styles/overrides.py). Opened from the header's
"Map settings" button; core/static/js/MapSettings.js shows it and applies a
change to the map when the HTMX response triggers editable-changed or
style-changed.

A style is stored as the difference from its code default only, so a
property nobody changed keeps following the code, and Reset deletes the row.
"""
import json

from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_http_methods, require_POST

from core.editing import FIELD_RULES, editable_keys, enable_blocker
from core.utils import VECTOR_REGISTRY

from .models import EditableLayer, LayerStyleOverride
from .styles.overrides import (
    HEX_COLOR, OTHER, base_vector_style, is_color_match, is_scalar, match_categories,
)
from .styles.rasterStyles import default_raster_style, raster_style_choices

PANEL_TEMPLATE = 'mainMap/partials/map_settings.html'
EDITABLE_ROW_TEMPLATE = 'mainMap/partials/settings_editable_row.html'
STYLE_FORM_TEMPLATE = 'mainMap/partials/settings_style_form.html'


def _forbidden():
    return HttpResponseForbidden('Map settings require a staff login.')


def _layer_name(key):
    return VECTOR_REGISTRY[key]._meta.verbose_name_plural.title()


def _editable_row(key, keys):
    return {
        'key': key,
        'name': _layer_name(key),
        'app_label': key.split('.')[0],
        'enabled': key in keys,
        'has_rules': key in FIELD_RULES,
        'blocker': enable_blocker(key),
    }


def map_settings(request):
    """The panel: editable layers tab + styles tab. URL: /api/settings/"""
    if not request.user.is_staff:
        return _forbidden()
    keys = editable_keys()
    rows = sorted((_editable_row(key, keys) for key in VECTOR_REGISTRY), key=lambda r: (r['app_label'], r['name']))
    targets = [(f'vector:{key}', f'{_layer_name(key)} ({key})') for key in sorted(VECTOR_REGISTRY)]
    raster_targets = [(f'raster:{key}', label) for key, label in raster_style_choices()]
    return render(request, PANEL_TEMPLATE, {
        'rows': rows, 'vector_targets': targets, 'raster_targets': raster_targets,
    })


@require_POST
def settings_editable(request):
    """Switch one layer editable on/off (POST key, enabled). URL: /api/settings/editable/"""
    if not request.user.is_staff:
        return _forbidden()
    key = request.POST.get('key', '')
    if key not in VECTOR_REGISTRY:
        return HttpResponseBadRequest(f'Unknown vector layer {key!r}')
    enabled = request.POST.get('enabled') == 'on'
    error = None
    if enabled:
        error = enable_blocker(key)
        if error is None:
            EditableLayer.objects.get_or_create(key=key, defaults={'added_by': request.user})
    else:
        EditableLayer.objects.filter(key=key).delete()

    row = _editable_row(key, editable_keys())
    response = render(request, EDITABLE_ROW_TEMPLATE, {'row': row, 'error': error})
    if error is None:
        response['HX-Trigger'] = json.dumps({'editable-changed': {'key': key, 'enabled': row['enabled']}})
    return response


# ── styles ─────────────────────────────────────────────────────────────────

def _parse_target(target):
    kind, _, key = (target or '').partition(':')
    if kind == LayerStyleOverride.VECTOR and key in VECTOR_REGISTRY:
        return kind, key
    if kind == LayerStyleOverride.RASTER and key in dict(raster_style_choices()):
        return kind, key
    return None, None


def _vector_fields(key, data):
    """Form fields of a vector style: default value, current value, input kind."""
    color, style_layers, legend = base_vector_style(key)
    data = data or {}
    fields = [{'name': 'color', 'label': 'Catalog colour', 'kind': 'color',
               'default': color, 'value': data.get('color') or color}]
    paint_overrides = data.get('paint') or {}
    categories = None
    for i, layer in enumerate(style_layers or []):
        for prop, value in (layer.get('paint') or {}).items():
            if is_scalar(value):
                current = paint_overrides.get(str(i), {}).get(prop, value)
                fields.append({
                    'name': f'paint:{i}:{prop}', 'label': f'{layer["type"]} · {prop}',
                    'kind': 'color' if isinstance(value, str) else 'number',
                    'default': value, 'value': current,
                    'layer_index': i, 'prop': prop,
                    'step': '0.05' if prop.endswith('opacity') else '0.1',
                    'max': 1 if prop.endswith('opacity') else None,
                })
            elif categories is None and is_color_match(value):
                categories = match_categories(value)

    category_fields = []
    if categories:
        labels = {item.get('value'): item['label'] for item in legend or [] if 'value' in item}
        cat_overrides = data.get('categories') or {}
        for value, default in categories:
            category_fields.append({
                'name': f'cat:{value}', 'label': labels.get(value, 'Other' if value == OTHER else str(value)),
                'kind': 'color', 'default': default, 'value': cat_overrides.get(value, default),
            })
    return fields, category_fields


def _vector_data(post, fields, category_fields):
    """Override data from a POST: only the values that differ from the default."""
    errors = []
    data = {}
    for f in fields + category_fields:
        raw = post.get(f['name'], '').strip()
        if raw == '':
            continue
        if f['kind'] == 'color':
            if not HEX_COLOR.match(raw):
                errors.append(f'{f["label"]}: "{raw}" is not a #rrggbb colour')
                continue
            value = raw.lower()
            if value == str(f['default']).lower():
                continue
        else:
            try:
                value = float(raw)
            except ValueError:
                errors.append(f'{f["label"]}: "{raw}" is not a number')
                continue
            if value < 0 or (f.get('max') is not None and value > f['max']):
                errors.append(f'{f["label"]}: must be between 0 and {f.get("max") or "∞"}')
                continue
            if value == f['default']:
                continue
        if f['name'] == 'color':
            data['color'] = value
        elif f['name'].startswith('paint:'):
            data.setdefault('paint', {}).setdefault(str(f['layer_index']), {})[f['prop']] = value
        else:
            data.setdefault('categories', {})[f['name'][len('cat:'):]] = value
    return data, errors


def _colormaps():
    from rio_tiler.colormap import cmap   # heavy (scipy): only when the raster form is opened
    return sorted(cmap.list())


def _raster_fields(key, data):
    colormap, rescale, label, unit = default_raster_style(key)
    data = data or {}
    current_rescale = data['rescale'] if 'rescale' in data else rescale
    return {
        'label': label, 'unit': unit,
        'default_colormap': colormap, 'colormap': data.get('colormap') or colormap,
        'default_rescale': rescale,
        'min': current_rescale[0] if current_rescale else '',
        'max': current_rescale[1] if current_rescale else '',
        'colormaps': _colormaps() if colormap is not None else [],
    }


def _raster_data(post, key):
    colormap, rescale, _, _ = default_raster_style(key)
    errors = []
    data = {}
    chosen = post.get('colormap', '').strip()
    if colormap is not None and chosen and chosen != colormap:
        if chosen not in _colormaps():
            errors.append(f'Unknown colormap "{chosen}"')
        else:
            data['colormap'] = chosen
    vmin, vmax = post.get('min', '').strip(), post.get('max', '').strip()
    if vmin == '' and vmax == '':
        new_rescale = None   # stretch to the raster's own min/max
    else:
        try:
            new_rescale = [float(vmin), float(vmax)]
        except ValueError:
            errors.append('Min and max must both be numbers, or both empty (range from the data)')
            new_rescale = rescale
        else:
            if new_rescale[0] >= new_rescale[1]:
                errors.append('Min must be below max')
    if not errors and (tuple(new_rescale) if new_rescale else None) != (tuple(rescale) if rescale else None):
        data['rescale'] = new_rescale
    return data, errors


@require_http_methods(['GET', 'POST'])
def settings_style(request):
    """
    Style form of one layer (?target=vector:<key> | raster:<style key>).
    POST saves the override (only what differs from the default),
    POST action=reset deletes it; both trigger style-changed.
    URL: /api/settings/style/
    """
    if not request.user.is_staff:
        return _forbidden()
    params = request.POST if request.method == 'POST' else request.GET
    kind, key = _parse_target(params.get('target'))
    if kind is None:
        return HttpResponseBadRequest('Choose a layer')

    override = LayerStyleOverride.objects.filter(kind=kind, key=key).first()
    data = override.data if override else None
    errors, message = [], None

    if request.method == 'POST':
        if params.get('action') == 'reset':
            LayerStyleOverride.objects.filter(kind=kind, key=key).delete()
            data, message = None, 'Reset to the default style.'
        else:
            if kind == LayerStyleOverride.VECTOR:
                new_data, errors = _vector_data(params, *_vector_fields(key, None))
            else:
                new_data, errors = _raster_data(params, key)
            if not errors:
                if new_data:
                    LayerStyleOverride.objects.update_or_create(
                        kind=kind, key=key, defaults={'data': new_data, 'updated_by': request.user})
                else:
                    LayerStyleOverride.objects.filter(kind=kind, key=key).delete()
                data, message = new_data or None, 'Saved.'

    context = {'target': f'{kind}:{key}', 'kind': kind, 'key': key, 'errors': errors,
               'message': message, 'has_override': bool(data)}
    if kind == LayerStyleOverride.VECTOR:
        context['fields'], context['category_fields'] = _vector_fields(key, data)
    else:
        context['raster'] = _raster_fields(key, data)
    response = render(request, STYLE_FORM_TEMPLATE, context)
    if request.method == 'POST' and not errors:
        response['HX-Trigger'] = json.dumps({'style-changed': {'kind': kind, 'key': key}})
    return response
