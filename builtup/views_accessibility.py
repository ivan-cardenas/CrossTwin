"""
Map card for the network accessibility score (core/static/js/AccessibilityTool.js).

GET  /builtup/accessibility/info/        what is stored: network, scored buildings, mean score (open)
POST /builtup/accessibility/calculate/   recompute every building in both modes (staff)

After the first run the scores stay current through builtup/signals.py (a facility, park or
network segment changed). Method: builtup/calculations/chain.py, docs/functions_and_equations.tex.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


def _json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={"default": str})


def status():
    """Stored state per mode: network size and snapshot, scored buildings, mean score."""
    from django.db.models import Avg, Count, Max

    from .calculations import chain
    from .models import Accessibility, Building, NetworkEdge

    modes = {}
    for mode in chain.MODES:
        edges = NetworkEdge.objects.filter(**{mode: True}).aggregate(n=Count("id"), snapshot=Max("snapshot_date"))
        scores = Accessibility.objects.filter(mode=mode).aggregate(n=Count("id"), mean=Avg("score"), computed=Max("computed_at"))
        modes[mode] = {
            "edges": edges["n"], "network_snapshot": edges["snapshot"],
            "buildings": scores["n"], "mean_score": None if scores["mean"] is None else round(scores["mean"], 1),
            "computed_at": scores["computed"],
            "full_value_m": chain.FULL_VALUE_M[mode], "cutoff_m": chain.CUTOFF_M[mode],
            "layer": f"builtup.Accessibility{mode.capitalize()}",
        }
    return {
        "method": chain.ACCESS_METHOD,
        "buildings": Building.objects.count(),
        "has_network": any(m["edges"] for m in modes.values()),
        "modes": modes,
    }


@require_GET
def accessibility_info(request):
    data = status()
    data["can_calculate"] = request.user.is_staff
    return _json(data)


@require_POST
def accessibility_calculate(request):
    if not request.user.is_staff:
        return _json({"error": "Log in as a staff user to calculate accessibility."}, status=403)
    import logging

    from .signals import recompute_accessibility

    data = status()
    if not data["has_network"]:
        return _json({"error": "No street network is stored yet: import 'Walk & bike network (OpenStreetMap)' first."}, status=409)
    try:
        written = recompute_accessibility()
    except Exception:
        logging.getLogger(__name__).exception("Accessibility calculation failed")
        return _json({"error": "The calculation failed; see the server log."}, status=500)
    data = status()
    data["can_calculate"] = True
    data["written"] = written
    return _json(data)
