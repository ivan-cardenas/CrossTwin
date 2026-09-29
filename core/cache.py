"""
Versioned cache keys for data that only changes when rows are written.

Every cached response that depends on a model's rows (the map's GeoJSON,
see mainMap/views.py::model_geojson) builds its key from
`layer_version(model)`. Bumping the version orphans every cached entry for
that model at once, so nothing has to enumerate or delete keys; the old
entries simply age out.

Writers that bypass post_save/post_delete (queryset.update(), bulk_create —
the population cascade, the land-cover urban-area update, the importer's
bulk path) must call `bump_layer_version()` themselves. Every other write is
covered by the receivers in core/signals.py.

See docs/PERFORMANCE.md §1.
"""
import time

from django.core.cache import InvalidCacheBackendError, caches


def get_cache(alias="default"):
    """caches[alias], falling back to the default cache when the alias isn't configured."""
    try:
        return caches[alias]
    except InvalidCacheBackendError:
        return caches["default"]


def _label(model_or_label):
    return model_or_label if isinstance(model_or_label, str) else model_or_label._meta.label


def _version_key(model_or_label):
    return f"layerver:{_label(model_or_label)}"


def layer_version(model_or_label):
    """
    Current cache version of a model's data. A missing version is seeded with
    the current time rather than 0, so that a version evicted from a local
    memory cache can never come back as a value an older entry was keyed on.
    """
    cache = get_cache()
    key = _version_key(model_or_label)
    version = cache.get(key)
    if version is None:
        version = time.time_ns()
        cache.add(key, version, timeout=None)
        version = cache.get(key, version)
    return version


def bump_layer_version(*models_or_labels):
    """Invalidate every cached response built from these models' rows."""
    cache = get_cache()
    for model_or_label in models_or_labels:
        cache.set(_version_key(model_or_label), time.time_ns(), timeout=None)
