"""
OpenStreetMap walk / bike routing graph for the Accessibility node.

The catalog entry `osm_network` (format "overpass_network") asks Overpass for
every routable `highway` way inside the bbox. Each way is classified as
walkable and/or cyclable (way_modes), cut at intersections (split_ways) and
stored as builtup.NetworkNode / builtup.NetworkEdge, which
builtup/calculations/accessibility.py turns into a pandana network.

Re-importing an area replaces the edges of every way that comes back; a way
deleted from OSM since the last import is not removed (v1). Every edge carries
the snapshot date and a hash of the Overpass statements (NETWORK_PARSER_VERSION
included), so a score can be traced to the network it was computed on.

DAG edges: Streets -> Accessibility
"""
import hashlib
import json
import math
from collections import Counter
from datetime import date

NETWORK_PARSER_VERSION = "v1"
CHUNK = 5000

# highway values that are never part of the pedestrian / bicycle network
EXCLUDED_HIGHWAYS = (
    "motorway|motorway_link|trunk|trunk_link|proposed|construction|raceway|"
    "bus_guideway|escape|elevator|corridor|via_ferrata|services|rest_area"
)
OVERPASS_STATEMENTS = [f'way["highway"]["highway"!~"^({EXCLUDED_HIGHWAYS})$"]["area"!="yes"]']

# Roads open to everyone on foot / by bicycle (OSMnx "walk" / "bike" filters, simplified).
_ROADS = {
    "living_street", "residential", "service", "unclassified", "road",
    "tertiary", "tertiary_link", "secondary", "secondary_link", "primary", "primary_link",
}
WALK_HIGHWAYS = _ROADS | {"footway", "pedestrian", "path", "steps", "track", "bridleway", "crossing"}
BIKE_HIGHWAYS = _ROADS | {"cycleway", "path", "track"}
_ALLOW = {"yes", "designated", "permissive"}
_DENY = {"no", "private"}
_RESTRICTED_ACCESS = {"private", "no", "customers", "delivery", "agricultural", "forestry"}


def way_modes(tags):
    """(walk, bike) for the tags of one OSM way."""
    highway = tags.get("highway")
    foot, bicycle = tags.get("foot"), tags.get("bicycle")
    if tags.get("access") in _RESTRICTED_ACCESS:
        return foot in _ALLOW, bicycle in _ALLOW
    if highway == "service" and tags.get("service") == "parking_aisle":
        return False, False
    walk = highway in WALK_HIGHWAYS and foot not in _DENY
    if highway == "cycleway":  # a cycle path is not for pedestrians unless signed so
        walk = foot in _ALLOW
    bike = highway in BIKE_HIGHWAYS and bicycle not in _DENY
    if highway in ("footway", "pedestrian", "bridleway", "crossing"):  # only where cycling is allowed
        bike = bicycle in _ALLOW
    return walk, bike


def query_hash(dataset):
    """Short hash of the Overpass statements and the parser version (what produced the edges)."""
    payload = json.dumps([dataset.get("osm_query"), NETWORK_PARSER_VERSION])
    return hashlib.sha1(payload.encode()).hexdigest()[:16]


def split_ways(elements, project):
    """
    Overpass `out geom` ways -> (nodes, edges).

    nodes: {osm_id: (x, y)} in the project CRS, for the nodes the edges use.
    edges: dicts with osm_id (way), highway, walk, bike, from_node, to_node,
           length_m and coords [(x, y), ...].
    A way is cut where a node is shared with another way (or visited twice) and at
    its ends; positions outside the bbox come back as null and break the way.
    `project(lons, lats)` -> (xs, ys) converts WGS84 to the project CRS.
    """
    ways = []
    usage = Counter()
    for element in elements:
        if element.get("type") != "way":
            continue
        ids, geometry = element.get("nodes") or [], element.get("geometry") or []
        tags = element.get("tags", {})
        walk, bike = way_modes(tags)
        if len(ids) < 2 or len(ids) != len(geometry) or not (walk or bike):
            continue
        ways.append((element["id"], tags.get("highway", ""), walk, bike, ids, geometry))
        usage.update(ids)

    # one projection call for all points
    lons, lats = [], []
    for *_, geometry in ways:
        for point in geometry:
            if point:
                lons.append(point["lon"])
                lats.append(point["lat"])
    xs, ys = project(lons, lats) if lons else ([], [])
    cursor = iter(zip(xs, ys))

    nodes, edges = {}, []
    for way_id, highway, walk, bike, ids, geometry in ways:
        points = [next(cursor) if point else None for point in geometry]
        runs, run = [], []
        for node_id, xy in zip(ids, points):
            if xy is None:
                if len(run) > 1:
                    runs.append(run)
                run = []
            else:
                run.append((node_id, xy))
        if len(run) > 1:
            runs.append(run)
        for run in runs:
            cuts = [i for i, (node_id, _) in enumerate(run) if i in (0, len(run) - 1) or usage[node_id] >= 2]
            for start, end in zip(cuts, cuts[1:]):
                part = run[start:end + 1]
                from_node, to_node = part[0][0], part[-1][0]
                if from_node == to_node:
                    continue
                coords = [xy for _, xy in part]
                length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(coords, coords[1:]))
                nodes[from_node], nodes[to_node] = part[0][1], part[-1][1]
                edges.append({
                    "osm_id": way_id, "highway": highway[:50], "walk": walk, "bike": bike,
                    "from_node": from_node, "to_node": to_node, "length_m": length, "coords": coords,
                })
    return nodes, edges


def save_network(nodes, edges, dataset, snapshot=None):
    """Replace the stored edges of the returned ways and add the nodes. Returns (nodes, edges) created."""
    from django.conf import settings
    from django.contrib.gis.geos import LineString, Point, Polygon
    from django.db import transaction

    from builtup.models import NetworkEdge, NetworkNode
    from core.cache import bump_layer_version

    srid = settings.COORDINATE_SYSTEM
    snapshot = snapshot or date.today()
    digest = query_hash(dataset)
    way_ids = sorted({e["osm_id"] for e in edges})
    with transaction.atomic():
        for i in range(0, len(way_ids), CHUNK):
            # raw: a normal delete() would load every edge to send post_delete to
            # builtup/signals.py; one refresh over the whole import is scheduled below.
            NetworkEdge.objects.filter(osm_id__in=way_ids[i:i + CHUNK])._raw_delete(NetworkEdge.objects.db)
        NetworkNode.objects.bulk_create(
            [NetworkNode(osm_id=node_id, geom=Point(x, y, srid=srid)) for node_id, (x, y) in nodes.items()],
            ignore_conflicts=True, batch_size=CHUNK,
        )
        NetworkEdge.objects.bulk_create(
            [NetworkEdge(
                from_node_id=e["from_node"], to_node_id=e["to_node"], length_m=e["length_m"],
                walk=e["walk"], bike=e["bike"], osm_id=e["osm_id"], highway=e["highway"],
                snapshot_date=snapshot, query_hash=digest, geom=LineString(e["coords"], srid=srid),
            ) for e in edges],
            batch_size=CHUNK,
        )
    # bulk_create / the raw delete fire no signals: invalidate the cached GeoJSON of both
    # layers and the pandana graph here, and replay Streets -> Accessibility over the extent
    # (builtup/signals.py; deferred to the end of an enclosing deferred_cascades() block).
    from builtup.calculations.accessibility import clear_network_cache
    from builtup.signals import schedule_accessibility

    bump_layer_version(NetworkNode, NetworkEdge)
    clear_network_cache()
    xs, ys = [xy[0] for xy in nodes.values()], [xy[1] for xy in nodes.values()]
    extent = Polygon.from_bbox((min(xs), min(ys), max(xs), max(ys)))
    extent.srid = int(srid)
    schedule_accessibility([extent])
    return len(nodes), len(edges)


def fetch(dataset, bbox):
    """Download the walk/bike network inside bbox [west, south, east, north] (WGS84) and store it."""
    from django.conf import settings
    from pyproj import Transformer

    from importer.console import say
    from importer.external_data import ImportResult, OSMImporter

    query = OSMImporter.build_query(dataset, bbox, as_points=False)
    response = OSMImporter._post(query, dataset)
    if isinstance(response, ImportResult):
        return response
    body = response.json()
    remark = body.get("remark") or ""
    if "runtime error" in remark:
        return ImportResult("error", f"Overpass query failed ({remark.strip()}). Try a smaller area.")

    transformer = Transformer.from_crs(4326, settings.COORDINATE_SYSTEM, always_xy=True)
    nodes, edges = split_ways(
        body.get("elements", []),
        lambda lons, lats: tuple(list(axis) for axis in transformer.transform(lons, lats)),
    )
    say("osm", f"Overpass returned {len(body.get('elements', []))} element(s) -> {len(edges)} edge(s), {len(nodes)} node(s)")
    if not edges:
        return ImportResult("success", "No walkable or cyclable ways found in the specified area.", 0)
    n_nodes, n_edges = save_network(nodes, edges, dataset)
    walk, bike = sum(e["walk"] for e in edges), sum(e["bike"] for e in edges)
    return ImportResult(
        "success",
        f"Imported the OpenStreetMap network: {n_edges} edges ({walk} walkable, {bike} cyclable), {n_nodes} nodes. "
        "Accessibility of the buildings in the area was recomputed.",
        n_edges,
    )
