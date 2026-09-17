import hashlib
import re
from datetime import datetime, timedelta
from xml.etree import ElementTree

import requests
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from .models import WMSLayer

# ADAGUC/WMS capabilities documents are namespaced; strip the namespace
# instead of hardcoding it, since it can vary between WMS servers.
WMS_NS_RE = re.compile(r'^\{[^}]+\}')


def _wms_auth_headers(layer):
    """Authorization header for a WMS layer configured with an API key.

    `layer.api_key_setting` names a Django setting (e.g. "KNMI_API_KEY")
    rather than baking in any one provider — any WMS with an authenticated,
    higher-rate-limit tier can opt in the same way.
    """
    if not layer.api_key_setting:
        return {}
    api_key = getattr(settings, layer.api_key_setting, None)
    if not api_key:
        return {}
    return {'Authorization': api_key}


def _fetch_with_retry(url, headers=None, timeout=15, attempts=2):
    """GET a URL, retrying once on transient network errors (timeouts, resets).

    Time-dimension WMS servers are often slow (generating a capabilities
    document on the fly), so a single blip shouldn't take the layer down.
    """
    last_error = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            last_error = exc
    raise last_error


# Minimal ISO8601 duration parser — covers the P[n]Y[n]M[n]DT[n]H[n]M[n]S
# components actually used by WMS TIME dimension "resolution" strings
# (e.g. "PT5M"), not the full ISO8601 duration grammar.
ISO8601_DURATION_RE = re.compile(
    r'^P(?:(?P<days>\d+)D)?'
    r'(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$'
)


def _parse_iso8601_duration(value):
    match = ISO8601_DURATION_RE.match(value)
    if not match:
        raise ValueError(f"Unsupported ISO8601 duration: {value!r}")
    parts = {k: int(v) for k, v in match.groupdict(default=0).items()}
    return timedelta(days=parts['days'], hours=parts['hours'],
                      minutes=parts['minutes'], seconds=parts['seconds'])


def _parse_iso8601(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _local_tag(element):
    return WMS_NS_RE.sub('', element.tag)


def _find_dimension_values(capabilities_xml, layer_name):
    """Return the raw text of the <Dimension name="time"> for a given layer."""
    root = ElementTree.fromstring(capabilities_xml)

    for layer_el in root.iter():
        if _local_tag(layer_el) != 'Layer':
            continue
        name_el = next(
            (child for child in layer_el if _local_tag(child) == 'Name'), None
        )
        if name_el is None or (name_el.text or '').strip() != layer_name:
            continue

        for dim_el in layer_el:
            if _local_tag(dim_el) == 'Dimension' and dim_el.get('name') == 'time':
                return (dim_el.text or '').strip()

    return None


def _last_n_time_steps(dimension_text, count):
    """Resolve the most recent `count` timestamps from a WMS time Dimension value.

    Handles both a "start/end/resolution" ISO8601 interval (the common case
    for gridded/radar WMS servers, e.g. "2026-09-09T12:25:00Z/2026-09-16T14:20:00Z/PT5M")
    and a plain comma-separated list of timestamps.
    """
    if '/' in dimension_text:
        start_str, end_str, resolution_str = dimension_text.split('/')
        end = _parse_iso8601(end_str)
        step = _parse_iso8601_duration(resolution_str)
        start = _parse_iso8601(start_str)

        steps = []
        current = end
        while current >= start and len(steps) < count:
            steps.append(current)
            current -= step
        steps.reverse()
        return [t.strftime('%Y-%m-%dT%H:%M:%SZ') for t in steps]

    values = [v.strip() for v in dimension_text.split(',') if v.strip()]
    return values[-count:]


def wms_time_steps(request, wms_name):
    """Resolve the most recent time steps for an animated WMS layer.

    Fetches and briefly caches the layer's GetCapabilities document
    server-side (browsers can be blocked from fetching it directly by CORS),
    then extracts the WMS TIME dimension for the configured layer.
    """
    try:
        layer = WMSLayer.objects.get(name=wms_name, has_time_dimension=True)
    except WMSLayer.DoesNotExist:
        return JsonResponse({'error': 'Animated WMS layer not found'}, status=404)

    cache_key = f'wms_capabilities_{layer.name}'
    stale_cache_key = f'wms_capabilities_stale_{layer.name}'
    capabilities_xml = cache.get(cache_key)
    if capabilities_xml is None:
        separator = '&' if '?' in layer.url else '?'
        capabilities_url = f'{layer.url}{separator}SERVICE=WMS&REQUEST=GetCapabilities'
        try:
            response = _fetch_with_retry(capabilities_url, headers=_wms_auth_headers(layer))
        except requests.exceptions.RequestException as exc:
            # Transient network errors shouldn't take the layer down —
            # fall back to the last known-good capabilities doc if we have one.
            capabilities_xml = cache.get(stale_cache_key)
            if capabilities_xml is None:
                return JsonResponse(
                    {'error': f'Could not reach WMS server: {exc}'}, status=502,
                )
        else:
            capabilities_xml = response.text
            cache.set(cache_key, capabilities_xml, timeout=60)
            cache.set(stale_cache_key, capabilities_xml, timeout=86400)

    dimension_text = _find_dimension_values(capabilities_xml, layer.layers_param)
    if not dimension_text:
        return JsonResponse(
            {'error': f'No time dimension found for layer "{layer.layers_param}"'},
            status=404,
        )

    times = _last_n_time_steps(dimension_text, layer.time_frame_count)
    if not times:
        return JsonResponse({'error': 'No time steps resolved'}, status=404)

    return JsonResponse({'times': times, 'default': times[-1]})


def wms_tile_proxy(request, wms_name):
    """Proxy a GetMap tile request to a WMS that requires an API key.

    Mapbox GL's raster tile source has no way to attach custom headers to
    the image requests it fires, so a layer's Authorization header can't be
    set client-side — and the key must never reach the browser anyway. This
    forwards the request Mapbox already builds (the same querystring
    `addWmsLayer`/`addAnimatedWmsLayer` construct for a direct WMS) to the
    real WMS URL with the header attached, and streams the image back.
    """
    layer = get_object_or_404(WMSLayer, name=wms_name)

    query_hash = hashlib.sha1(request.META.get("QUERY_STRING", "").encode()).hexdigest()
    cache_key = f'wms_tile_{layer.name}_{query_hash}'
    cached = cache.get(cache_key)
    if cached is not None:
        content, content_type = cached
        return HttpResponse(content, content_type=content_type)

    separator = '&' if '?' in layer.url else '?'
    upstream_url = f'{layer.url}{separator}{request.META.get("QUERY_STRING", "")}'

    try:
        response = _fetch_with_retry(
            upstream_url, headers=_wms_auth_headers(layer), timeout=10,
        )
    except requests.exceptions.RequestException:
        # A missing tile is a normal, non-fatal thing for a raster source —
        # Mapbox just leaves that area blank rather than breaking the layer.
        return HttpResponse(status=502)

    content_type = response.headers.get('Content-Type', 'image/png')
    cache.set(cache_key, (response.content, content_type), timeout=300)
    return HttpResponse(response.content, content_type=content_type)
