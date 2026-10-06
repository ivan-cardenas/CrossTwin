"""
INSPIRE HILUCS (Hierarchical INSPIRE Land Use Classification System) helpers.

A HILUCS value is referenced by URI, e.g.
http://inspire.ec.europa.eu/codelist/HILUCSValue/6_3_2_WaterAreasNotInOtherEconomicUse
and stored as physicalEnv.HILUCSLandUse(code='6.3.2', ...). Lookups go by the
code, never the full URI: PDOK's planned land use file spells some URIs
differently from the registry (5_2_ResidentialUseWithOtherComptibleUses vs
...CompatibleUses), while the leading code is the same.
"""
import re

from django.db.models import Q

_HREF = re.compile(r"(?:^|/)(\d+(?:_\d+)*)_?([A-Za-z]*)$")


def parse_hilucs_href(href):
    """
    (code, label) of a HILUCS URI, or None if it is not one.
    The label is spelled out from the URI's CamelCase name, lower case like
    the registry's: '6_3_2_WaterAreasNotInOtherEconomicUse' ->
    ('6.3.2', 'water areas not in other economic use'). It is only used for
    codes missing from the table; the registry's own label wins otherwise.
    """
    if not href:
        return None
    match = _HREF.search(str(href).strip().rstrip("/"))
    if not match:
        return None
    code = match.group(1).replace("_", ".")
    label = re.sub(r"(?<!^)(?=[A-Z])", " ", match.group(2)).lower()
    return code, label or code


def hilucs_lookup(href):
    """
    __fk_lookup__ parser for HILUCS URIs (importer/external_data.py):
    returns (code, get_or_create defaults) or None.
    """
    parsed = parse_hilucs_href(href)
    if parsed is None:
        return None
    code, label = parsed
    return code, {"label": label, "description": ""}


def hilucs_q(field, codes):
    """
    Q matching rows whose HILUCS FK `field` is one of `codes` or below it in
    the hierarchy: hilucs_q('zone_type', ['5']) matches 5, 5.1, 5.2, 5.3, ...
    """
    q = Q()
    for code in codes:
        q |= Q(**{f"{field}__code": code}) | Q(**{f"{field}__code__startswith": f"{code}."})
    return q
