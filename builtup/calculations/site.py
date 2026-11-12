"""
Site check of the neighbourhood generator: may a neighbourhood be built on
this outline?

    buildable = outline − ∪ { P ∩ outline : P protected nature (BLOCKING_TYPES) }

- Natura 2000 and Natuurnetwerk Nederland (nature.ProtectedArea of type N2K /
  NNN; catalog entries pdok_natura2000, bij12_nnn) are cut out: housing there
  is not allowed (Wet natuurbescherming / Omgevingswet, provincial
  omgevingsverordening for the NNN). Nothing buildable left -> block.
- Other protected areas (KEA climate buffers, Ramsar) -> warning.
- Zoning (builtup.ZoningArea, HILUCS): residential (HILUCS 5, incl. 5.2
  mixed) is fine; any other zoning under the outline -> warning with its
  share (a plan change would be needed). No zoning stored -> info.
- Existing buildings (BAG, positive id) inside the buildable area -> warning.

One DB helper (queries only, no writes), used by builtup/views_generator.py
for the preview and again before a commit. Findings share the shape of
regulations.check: {code, severity: ok|info|warn|excluded|block, message,
source}; `excluded` = a protected part that is cut out (the rest can still
be built on), `block` = nothing can be stored.
"""
from dataclasses import dataclass, field

BLOCKING_TYPES = ("N2K", "NNN")
WARNING_TYPES = ("OTH", "RAM")
RESIDENTIAL_HILUCS = ("5",)
# Search radius (m) for "is protected-nature data imported around here at all?"
DATA_SEARCH_M = 10_000
DATASETS = {"N2K": "pdok_natura2000", "NNN": "bij12_nnn", "OTH": "kea_klimaatbuffers"}


@dataclass
class SiteCheck:
    buildable: object                     # GEOS geometry, storage CRS (may be empty)
    excluded: object                      # GEOS geometry of the protected parts that were cut out, or None
    warned: list = field(default_factory=list)      # [(GEOS geometry, label)] shown amber on the map
    findings: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)     # stored with the project (reproducibility)

    @property
    def blocked(self):
        return any(f["severity"] == "block" for f in self.findings)


def _finding(code, severity, message, source):
    return {"code": code, "severity": severity, "message": message, "source": source}


def _ha(m2):
    return f"{m2 / 10_000:.2f} ha"


def site_constraints(outline):
    """SiteCheck of a GEOS (Multi)Polygon outline in the storage CRS."""
    from django.contrib.gis.db.models.functions import Intersection
    from django.contrib.gis.measure import D

    from nature.models import ProtectedArea
    from physicalEnv.hilucs import hilucs_q
    from ..models import Building, ZoningArea

    findings, summary, warned = [], {"protected": [], "zoning": [], "datasets": []}, []
    outline_m2 = outline.area

    # ── protected nature ──────────────────────────────────────────
    protected = (ProtectedArea.objects.filter(geom__intersects=outline)
                 .annotate(part=Intersection("geom", outline))
                 .only("pk", "name", "protection_type")
                 .order_by("protection_type", "name", "pk"))
    excluded_parts = []
    for area in protected:
        part = area.part
        if part is None or part.empty or part.area < 1.0:
            continue
        entry = {"id": area.pk, "name": area.name, "type": area.protection_type, "area_m2": round(part.area, 1)}
        summary["protected"].append(entry)
        label = f"{area.get_protection_type_display()}: {area.name}"
        if area.protection_type in BLOCKING_TYPES:
            excluded_parts.append(part)
            findings.append(_finding(
                "protected", "excluded",
                f"{label} covers {_ha(part.area)} of the outline; that part is left unbuilt.",
                "Natura 2000: Omgevingswet / Wet natuurbescherming; NNN: provincial omgevingsverordening"))
        else:
            warned.append((part, label))
            findings.append(_finding(
                "protected", "warn", f"{label} covers {_ha(part.area)} of the outline.",
                "Klimaateffectatlas / Ramsar (no building ban)"))
    excluded = None
    buildable = outline
    if excluded_parts:
        excluded = excluded_parts[0]
        for part in excluded_parts[1:]:
            excluded = excluded.union(part)
        buildable = outline.difference(excluded)

    for kind in BLOCKING_TYPES:
        nearby = ProtectedArea.objects.filter(protection_type=kind, geom__dwithin=(outline, D(m=DATA_SEARCH_M))).exists()
        if nearby:
            summary["datasets"].append(DATASETS[kind])
        else:
            name = dict(ProtectedArea.ProtectionType.choices)[kind]
            findings.append(_finding(
                "protected_data", "info",
                f"No {name} areas stored within {DATA_SEARCH_M / 1000:.0f} km: import '{DATASETS[kind]}' "
                f"(Retrieve Data) to check this site against it.",
                "Importer catalog"))
    if not any(f["code"] == "protected" for f in findings):
        findings.insert(0, _finding("protected", "ok", "No protected nature under the outline.",
                                    "nature.ProtectedArea"))

    if buildable.empty or buildable.area < 1.0:
        findings.insert(0, _finding("buildable", "block", "Nothing is left to build on: the whole outline is protected nature.",
                                    "Site check"))
    elif excluded is not None:
        findings.insert(0, _finding("buildable", "warn",
                                    f"{_ha(buildable.area)} of {_ha(outline_m2)} can be built on.", "Site check"))

    # ── zoning ────────────────────────────────────────────────────
    zones = (ZoningArea.objects.filter(geom__intersects=outline)
             .annotate(part=Intersection("geom", outline))
             .select_related("zone_type").order_by("pk"))
    residential_ids = set(ZoningArea.objects.filter(pk__in=[z.pk for z in zones])
                          .filter(hilucs_q("zone_type", RESIDENTIAL_HILUCS)).values_list("pk", flat=True))
    other = {}
    covered = 0.0
    for zone in zones:
        part = zone.part
        if part is None or part.empty:
            continue
        covered += part.area
        label = str(zone.zone_type) if zone.zone_type_id else (zone.plan_type or "unclassified zoning")
        summary["zoning"].append({"id": zone.pk, "hilucs": zone.zone_type.code if zone.zone_type_id else None,
                                  "area_m2": round(part.area, 1)})
        if zone.pk not in residential_ids:
            other.setdefault(label, [0.0, []])
            other[label][0] += part.area
            other[label][1].append(part)
    if not zones:
        findings.append(_finding("zoning", "info", "No zoning stored under the outline: import planned land use to check it.",
                                 "builtup.ZoningArea (pdok_landcover_kadaster)"))
    elif other:
        for label, (m2, parts) in sorted(other.items(), key=lambda kv: -kv[1][0]):
            for part in parts:
                warned.append((part, label))
            findings.append(_finding(
                "zoning", "warn",
                f"{m2 / outline_m2:.0%} of the outline is zoned '{label}', not residential: a plan change would be needed.",
                "Omgevingsplan (HILUCS planned land use)"))
    else:
        findings.append(_finding("zoning", "ok", f"Zoned residential ({covered / outline_m2:.0%} of the outline covered).",
                                 "Omgevingsplan (HILUCS planned land use)"))

    # ── existing buildings ────────────────────────────────────────
    if not buildable.empty:
        existing = Building.objects.filter(geom__intersects=buildable, pk__gt=0).count()
        if existing:
            findings.append(_finding("existing_buildings", "warn",
                                     f"{existing} existing building(s) stand in the buildable area and would be demolished.",
                                     "builtup.Building (BAG)"))
    summary["findings"] = [{"code": f["code"], "severity": f["severity"]} for f in findings]
    return SiteCheck(buildable=buildable, excluded=excluded, warned=warned, findings=findings, summary=summary)
