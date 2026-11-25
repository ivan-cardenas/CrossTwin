"""
Network accessibility of buildings (DAG node Accessibility): the pandana pass.

For a travel mode (walk / bike) the stored OSM graph (builtup.NetworkNode /
NetworkEdge, importer/osm_network.py) becomes a pandana Network; every
building centroid is snapped to its nearest network node and the k nearest
amenities of each category (builtup.Facility rows and the edges of the parks in
nature.GreenSpaces) are found by network distance. The distances and the
0-100 score of builtup/calculations/chain.py are stored per building and mode
in builtup.Accessibility.

Distance of an amenity = network distance between the two snapped nodes
+ the straight offset of the building centroid to its node
+ the straight offset of the amenity to its node.
A building further than SNAP_MAX_M from the network gets an empty row
(score 0): it is not connected to it.

No views, no receivers here: builtup/signals.py decides when to recompute.
numpy / pandas / pandana / shapely are imported inside the functions
(CLAUDE.md: nothing heavy at start-up).

DAG edges: Facilities -> Accessibility, Streets -> Accessibility,
           Green_Area -> Accessibility
"""
import logging
import math
import threading
from collections import namedtuple

from builtup.calculations import chain

logger = logging.getLogger(__name__)

SNAP_MAX_M = 250.0                # a building further from the network than this is not connected
PARK_ACCESS_SPACING_M = 50.0      # entrance points along a park's edge (a centroid would punish large parks)
PARK_MAX_POINTS = 200             # per park ring, to bound the POI set
BUILDING_CHUNK = 20_000

# Graph = one built pandana network of a mode; nodes = DataFrame(x, y) indexed by node id.
Graph = namedtuple("Graph", "net nodes snapshot")

_lock = threading.RLock()
_graphs = {}                      # mode -> (key, Graph)


# ── amenities ──────────────────────────────────────────────────────────

def facility_category(type_, subtype=None):
    """
    Accessibility category of a Facility row, or None when it is not a destination.
    Rows imported before the accessibility amenities existed keep their old meaning:
    transportNode with subtype 'station' is a train station, 'bus_station' a bus stop;
    an OSM clinic (stored as type hospital) is a GP practice; a market is a shop.
    """
    if type_ == "transportNode":
        return {"station": "train_station", "bus_station": "bus_stop"}.get(subtype)
    if type_ == "hospital" and subtype == "clinic":
        return "clinic_gp"
    if type_ == "market":
        return "shop"
    return type_ if type_ in chain.CATEGORIES else None


def park_access_points(geometry, spacing_m=PARK_ACCESS_SPACING_M, max_points=PARK_MAX_POINTS):
    """Points every `spacing_m` along the outer edge of a (multi)polygon (shapely), at least one per part."""
    points = []
    for polygon in getattr(geometry, "geoms", [geometry]):
        ring = polygon.exterior
        if not ring.length:
            continue
        n = max(1, min(max_points, int(ring.length // spacing_m) + 1))
        step = ring.length / n
        for i in range(n):
            p = ring.interpolate(i * step)
            points.append((p.x, p.y))
    return points


def load_pois(box=None):
    """
    {category: [(x, y), ...]} in the project CRS from the stored facilities and parks;
    only those overlapping `box` (a GEOS polygon) when given: an amenity outside the buildings'
    extent widened by the cut-off cannot be reached, as network distance >= straight distance.
    """
    import shapely

    from builtup.models import Facility
    from nature.models import GreenSpaces

    facilities, parks = Facility.objects.all(), GreenSpaces.objects.park_space()
    if box is not None:
        facilities, parks = facilities.filter(geom__bboverlaps=box), parks.filter(geom__bboverlaps=box)
    pois = {}
    for type_, subtype, geom in facilities.values_list("type", "subtype", "geom").iterator(chunk_size=5000):
        category = facility_category(type_, subtype)
        if category and geom:
            pois.setdefault(category, []).append((geom.x, geom.y))
    for geom in parks.values_list("geom", flat=True).iterator(chunk_size=500):
        if geom:
            pois.setdefault("park", []).extend(park_access_points(shapely.from_wkb(bytes(geom.wkb))))
    return pois


# ── network ────────────────────────────────────────────────────────────

def _key(mode):
    from django.db.models import Count, Max

    from builtup.models import NetworkEdge

    agg = NetworkEdge.objects.filter(**{mode: True}).aggregate(n=Count("id"), last=Max("id"), snap=Max("snapshot_date"))
    return (mode, agg["n"], agg["last"], agg["snap"]), agg["n"], agg["snap"]


def clear_network_cache():
    with _lock:
        _graphs.clear()


def get_graph(mode):
    """
    The pandana Graph of a mode, or None when no edge is stored for it. Built once per
    process and reused until the edge count, last edge id or snapshot date changes
    (an import replaces edges, so its ids and date change).
    """
    key, n_edges, snapshot = _key(mode)
    if not n_edges:
        return None
    with _lock:
        cached = _graphs.get(mode)
        if cached and cached[0] == key:
            return cached[1]
        graph = _build_graph(mode, snapshot)
        _graphs[mode] = (key, graph)
        return graph


def _build_graph(mode, snapshot):
    import pandana
    import pandas as pd
    from django.db.models import FloatField, Func

    from builtup.models import NetworkEdge, NetworkNode

    edges = pd.DataFrame.from_records(
        NetworkEdge.objects.filter(**{mode: True}).values_list("from_node_id", "to_node_id", "length_m").iterator(chunk_size=50_000),
        columns=["from", "to", "length"],
    )
    used = pd.Index(pd.unique(pd.concat([edges["from"], edges["to"]])))
    nodes = pd.DataFrame.from_records(
        NetworkNode.objects.annotate(
            x=Func("geom", function="ST_X", output_field=FloatField()),
            y=Func("geom", function="ST_Y", output_field=FloatField()),
        ).values_list("osm_id", "x", "y").iterator(chunk_size=50_000),
        columns=["id", "x", "y"],
    ).set_index("id")
    nodes = nodes[nodes.index.isin(used)]
    edges = edges[edges["from"].isin(nodes.index) & edges["to"].isin(nodes.index)]
    # pandana wants strictly positive impedances
    weights = edges[["length"]].clip(lower=0.1)
    net = pandana.Network(nodes["x"], nodes["y"], edges["from"], edges["to"], weights)
    logger.info("Accessibility: built the %s network, %d nodes, %d edges", mode, len(nodes), len(edges))
    return Graph(net, nodes, snapshot)


# ── computation ────────────────────────────────────────────────────────

def _nearest_table(graph, category, points, mode, k):
    """
    For one category: (rows, D, P, offsets): rows maps node id -> row of D (k nearest network
    distances, NaN where none within the cut-off) and P (index of the POI found, NaN where none);
    offsets[i] is the straight distance of POI i to its node. None when there is no POI.
    """
    import numpy as np
    import pandas as pd

    if not points:
        return None
    xs = pd.Series([p[0] for p in points], dtype=float)
    ys = pd.Series([p[1] for p in points], dtype=float)
    cutoff = chain.CUTOFF_M[mode]
    net = graph.net
    net.set_pois(category, cutoff, k, xs, ys)
    result = net.nearest_pois(cutoff, category, num_pois=k, include_poi_ids=True)
    D = result[list(range(1, k + 1))].to_numpy(dtype=float)
    P = result[[f"poi{i}" for i in range(1, k + 1)]].to_numpy(dtype=float)
    D[np.isnan(P)] = np.nan   # pandana pads "none found" with the cut-off distance and a NaN id
    snapped = net.get_node_ids(xs, ys)
    offsets = np.hypot(xs.to_numpy() - graph.nodes.loc[snapped, "x"].to_numpy(),
                       ys.to_numpy() - graph.nodes.loc[snapped, "y"].to_numpy())
    return {n: i for i, n in enumerate(result.index)}, D, P, offsets


def compute_points(graph, mode, building_points, pois):
    """
    Distances and score per building for one mode.

    building_points: [(building_id, x, y)]. pois: load_pois(). Returns
    {building_id: (distances {category: [m, ...]}, score)} with the distances along the
    network plus the snapping offsets, sorted, and only those within the mode's cut-off.
    """
    import numpy as np
    import pandas as pd

    if not building_points:
        return {}
    ids = [b[0] for b in building_points]
    bx = pd.Series([b[1] for b in building_points], dtype=float)
    by = pd.Series([b[2] for b in building_points], dtype=float)
    cutoff = chain.CUTOFF_M[mode]
    with _lock:
        node_of = graph.net.get_node_ids(bx, by).to_numpy()
        snap = np.hypot(bx.to_numpy() - graph.nodes.loc[node_of, "x"].to_numpy(),
                        by.to_numpy() - graph.nodes.loc[node_of, "y"].to_numpy())
        tables = {}
        for category, (_, omegas) in chain.CATEGORIES.items():
            table = _nearest_table(graph, category, pois.get(category), mode, len(omegas))
            if table is not None:
                tables[category] = table

    out = {}
    for i, building_id in enumerate(ids):
        distances = {}
        if snap[i] <= SNAP_MAX_M:
            for category, (rows, D, P, offsets) in tables.items():
                row = rows.get(node_of[i])
                if row is None:
                    continue
                found = sorted(
                    D[row, j] + snap[i] + offsets[int(P[row, j])]
                    for j in range(D.shape[1]) if not math.isnan(P[row, j])
                )
                found = [round(d, 1) for d in found if d <= cutoff]
                if found:
                    distances[category] = found
        out[building_id] = (distances, chain.accessibility_score(distances, mode))
    return out


def compute(buildings=None, modes=chain.MODES, after_chunk=None):
    """
    Recompute and store builtup.Accessibility for `buildings` (a Building queryset; all when
    None) in each mode that has a stored network. Returns {mode: rows written}.
    after_chunk(mode, building_ids) is called after each batch is written (builtup/signals.py
    uses it to announce the changed buildings downstream).
    """
    from django.conf import settings
    from django.contrib.gis.db.models import Extent
    from django.contrib.gis.db.models.functions import Centroid
    from django.contrib.gis.geos import Polygon

    from builtup.models import Accessibility, Building
    from core.cache import bump_layer_version

    # No stored network (the usual case before the first OSM import): nothing to load or write.
    graphs = {mode: get_graph(mode) for mode in modes}
    for mode in [m for m, g in graphs.items() if g is None]:
        logger.debug("Accessibility: no %s network stored, skipped", mode)
    graphs = {m: g for m, g in graphs.items() if g is not None}
    if not graphs:
        return {}
    queryset = (Building.objects.all() if buildings is None else buildings).order_by("pk")
    extent = queryset.aggregate(e=Extent("geom"))["e"]
    if extent is None:
        return {}
    reach = max(chain.CUTOFF_M[mode] for mode in graphs)
    box = Polygon.from_bbox((extent[0] - reach, extent[1] - reach, extent[2] + reach, extent[3] + reach))
    box.srid = int(settings.COORDINATE_SYSTEM)
    pois = load_pois(box)
    written = {}
    for mode, graph in graphs.items():
        total = 0
        last = 0
        while True:
            chunk = list(
                queryset.filter(pk__gt=last).annotate(c=Centroid("geom")).values_list("pk", "c")[:BUILDING_CHUNK]
            )
            if not chunk:
                break
            last = chunk[-1][0]
            results = compute_points(graph, mode, [(pk, c.x, c.y) for pk, c in chunk], pois)
            centroid = {pk: c for pk, c in chunk}
            Accessibility.objects.bulk_create(
                [Accessibility(
                    building_id=pk, mode=mode, distances=distances, score=score,
                    method=chain.ACCESS_METHOD, network_snapshot=graph.snapshot, geom=centroid[pk],
                ) for pk, (distances, score) in results.items()],
                update_conflicts=True, unique_fields=["building", "mode"],
                update_fields=["distances", "score", "method", "network_snapshot", "geom", "computed_at"],
                batch_size=5000,
            )
            total += len(results)
            if after_chunk:
                after_chunk(mode, list(results))
        written[mode] = total
    # bulk_create fires no signals: invalidate the cached GeoJSON of the layer here.
    bump_layer_version(Accessibility)
    return written


def buildings_near(geometry, distance_m):
    """Buildings within `distance_m` (project CRS units) of a geometry: the ones a change can affect."""
    from builtup.models import Building

    return Building.objects.filter(geom__dwithin=(geometry, distance_m))
