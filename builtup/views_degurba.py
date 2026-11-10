"""
Map card for the Degree of Urbanisation (core/static/js/DegurbaTool.js).

GET  /builtup/degurba/info/        status of the stored grid (open)
POST /builtup/degurba/calculate/   rebuild the grid for the current population year (staff)

Everything else stays current through builtup/signals.py once the grid exists.
Method: docs/DEGREE_OF_URBANISATION.md.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


def _json(data, status=200):
    return JsonResponse(data, status=status, json_dumps_params={"default": str})


@require_GET
def degurba_info(request):
    from .urbanisation import status

    data = status()
    data["can_calculate"] = request.user.is_staff
    return _json(data)


@require_POST
def degurba_calculate(request):
    if not request.user.is_staff:
        return _json({"error": "Log in as a staff user to calculate the Degree of Urbanisation."}, status=403)
    from .urbanisation import rebuild, status

    summary = rebuild()
    if summary is None:
        return _json({"error": "The calculation failed; see the server log."}, status=500)
    data = status()
    data["can_calculate"] = True
    data["summary"] = {str(k): v for k, v in summary.items()}
    return _json(data)
