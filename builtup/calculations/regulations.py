"""
Indicative checks of a generated layout against Dutch building rules
(Besluit bouwwerken leefomgeving, Bbl, in force since 1 January 2024).

Pure functions, no ORM. The constants are the rules the neighbourhood
generator can check from footprints and floors alone; the rest of the Bbl
works at room level, and the omgevingsplan (height, building lines,
parking) is municipal and not stored, so the result is indicative, never a
permit check.

    min dwelling GFA = MIN_VERBLIJFSGEBIED_M2 / VERBLIJFSGEBIED_SHARE / GO_PER_GFA
                     = 18 / 0.55 / 0.8 ≈ 41 m² gross floor area

Sources:
- Bbl art. 4.163 lid 2: at least 55 % of a dwelling's gebruiksoppervlakte
  (usable floor area, GO) is verblijfsgebied.
  https://iplo.nl/regelgeving/regels-voor-activiteiten/technische-bouwactiviteit/nieuwbouw/rijksregels/vrije-indeelbaarheid/
- Bbl woonfunctie: at least 18 m² verblijfsgebied per dwelling (IPLO,
  infoblad "Besluit bouwwerken leefomgeving en woning", February 2026).
- NEN 2580: GO is typically about 80 % of the gross floor area (BVO); an
  estimate, the real ratio depends on walls and shafts.
- Fire spread (brandoverslag, Bbl fire-compartment rules computed with
  NEN 6068): facades of separate buildings less than 5 m apart need
  fire-resistant walls (WBDBO 60 min).
- Daylight: Bbl §4.3.10 (NEN 2057) is checked per room; the 45° obstruction
  angle between slabs is a design rule of thumb, reported as a warning.
"""
import math

MIN_VERBLIJFSGEBIED_M2 = 18.0    # Bbl woonfunctie, per dwelling
VERBLIJFSGEBIED_SHARE = 0.55     # Bbl art. 4.163 lid 2
GO_PER_GFA = 0.8                 # NEN 2580, typical GO / BVO
FIRE_SPREAD_M = 5.0              # brandoverslag distance without fire-resistant facades
DAYLIGHT_ANGLE_DEG = 45.0        # obstruction angle between facing slabs (rule of thumb)
# Distances within this margin count as meeting a rule (floating-point geometry).
TOLERANCE_M = 0.05
# Typologies whose buildings face each other across a courtyard or open space
# (slab spacing is checked for them); low-rise rows share party walls by design.
SPACED_TYPOLOGIES = {"slab", "tower"}

BBL = "Bbl (Besluit bouwwerken leefomgeving)"


def min_unit_gfa_m2():
    """Smallest gross floor area of one dwelling that can hold the Bbl minimum living space."""
    return MIN_VERBLIJFSGEBIED_M2 / VERBLIJFSGEBIED_SHARE / GO_PER_GFA


def _finding(code, severity, message, source):
    return {"code": code, "severity": severity, "message": message, "source": source}


def check(buildings, unit_gfa_m2):
    """
    Findings for a layout: `buildings` = [{geom (shapely, metres), floors,
    height_m, units, typology, plot (id of the plot, None for a shared one)}].
    severity: ok | warn | block | info.
    """
    findings = []
    smallest = min_unit_gfa_m2()
    if unit_gfa_m2 < smallest:
        findings.append(_finding(
            "unit_size", "block",
            f"Dwellings of {unit_gfa_m2:.0f} m² gross floor area are below the {smallest:.0f} m² needed for "
            f"{MIN_VERBLIJFSGEBIED_M2:.0f} m² of living space (verblijfsgebied ≥ {VERBLIJFSGEBIED_SHARE:.0%} of the usable area).",
            f"{BBL} art. 4.163; NEN 2580"))
    else:
        tight = [b for b in buildings if b["units"] > 1 and b["geom"].area * b["floors"] / b["units"] < smallest]
        if tight:
            findings.append(_finding(
                "unit_size", "block",
                f"{len(tight)} building(s) split into dwellings smaller than {smallest:.0f} m² gross.",
                f"{BBL} art. 4.163; NEN 2580"))
        else:
            findings.append(_finding(
                "unit_size", "ok",
                f"Every dwelling has at least {smallest:.0f} m² gross floor area ({MIN_VERBLIJFSGEBIED_M2:.0f} m² living space).",
                f"{BBL} art. 4.163"))

    findings.append(fire_spread(buildings))
    daylight = daylight_spacing(buildings)
    if daylight:
        findings.append(daylight)
    findings.append(_finding(
        "omgevingsplan", "info",
        "Height limits, building lines and parking norms of the municipal omgevingsplan are not checked.",
        "Omgevingswet: omgevingsplan"))
    return findings


def _close_pairs(buildings, distance):
    """Pairs (i, j) of buildings that are closer than `distance` but do not touch (party walls are allowed)."""
    from shapely.strtree import STRtree

    geoms = [b["geom"] for b in buildings]
    if len(geoms) < 2:
        return []
    tree = STRtree(geoms)
    pairs = []
    for i, geom in enumerate(geoms):
        for j in tree.query(geom.buffer(distance)):
            j = int(j)
            if j <= i:
                continue
            gap = geom.distance(geoms[j])
            if TOLERANCE_M < gap < distance - TOLERANCE_M:
                pairs.append((i, j, gap))
    return pairs


def fire_spread(buildings):
    """Separate buildings less than FIRE_SPREAD_M apart: warn (they need fire-resistant facades)."""
    pairs = _close_pairs(buildings, FIRE_SPREAD_M)
    if not pairs:
        return _finding("fire_spread", "ok",
                        f"Separate buildings stand at least {FIRE_SPREAD_M:.0f} m apart or share a party wall.",
                        f"{BBL}, fire spread (NEN 6068)")
    closest = min(gap for _, _, gap in pairs)
    return _finding("fire_spread", "warn",
                    f"{len(pairs)} pair(s) of buildings stand closer than {FIRE_SPREAD_M:.0f} m (closest {closest:.1f} m): "
                    f"those facades need fire-resistant walls (WBDBO 60 min).",
                    f"{BBL}, fire spread (NEN 6068)")


def _alongside(a, b):
    """True when b's centre lies beside a's long facade (not beyond its short end wall)."""
    rect = a.minimum_rotated_rectangle
    coords = list(rect.exterior.coords) if rect.geom_type == "Polygon" else []
    if len(coords) < 4:
        return True
    (x0, y0), (x1, y1), (x2, y2) = coords[0][:2], coords[1][:2], coords[2][:2]
    e1, e2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
    (ux, uy), half = (((x1 - x0) / e1, (y1 - y0) / e1), e1 / 2) if e1 >= e2 else (((x2 - x1) / e2, (y2 - y1) / e2), e2 / 2)
    ca, cb = a.centroid, b.centroid
    return abs((cb.x - ca.x) * ux + (cb.y - ca.y) * uy) < half


def daylight_spacing(buildings):
    """
    Slabs/towers whose facades face each other closer than height /
    tan(DAYLIGHT_ANGLE_DEG): warn. End walls (one building beyond the other's
    short side) are not counted. None when there are no slabs or towers.
    """
    spaced = [b for b in buildings if b.get("typology") in SPACED_TYPOLOGIES]
    if len(spaced) < 2:
        return None
    tan = math.tan(math.radians(DAYLIGHT_ANGLE_DEG))
    tallest = max(b["height_m"] for b in spaced)
    pairs = [(i, j, gap) for i, j, gap in _close_pairs(spaced, tallest / tan)
             if gap < max(spaced[i]["height_m"], spaced[j]["height_m"]) / tan - TOLERANCE_M
             and (_alongside(spaced[i]["geom"], spaced[j]["geom"]) or _alongside(spaced[j]["geom"], spaced[i]["geom"]))]
    if not pairs:
        return _finding("daylight", "ok",
                        f"Slabs and towers keep a {DAYLIGHT_ANGLE_DEG:.0f}° daylight angle to each other.",
                        "Rule of thumb; Bbl §4.3.10 (NEN 2057) is checked per room")
    return _finding("daylight", "warn",
                    f"{len(pairs)} pair(s) of slabs/towers are closer than their height (45° daylight angle).",
                    "Rule of thumb; Bbl §4.3.10 (NEN 2057) is checked per room")
