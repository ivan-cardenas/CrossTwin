"""
Degree of Urbanisation (DEGURBA) grid classification: pure numpy/scipy, no ORM.

DAG node: Degree_Urbanisation (State). DAG edges: Total_Population ->
Degree_Urbanisation (cell population), Buildings -> Degree_Urbanisation
(built-up share), LandCover -> Degree_Urbanisation (settlement mask, water).
Method and every deviation from the original: docs/DEGREE_OF_URBANISATION.md.

Two variants run on the same inputs (`resolution_m`):

- 1000 m: the original GHSL/Eurostat rules on 1 km cells (gross density of
  the cell's land area, holes < 15 km² filled, 5-of-8 smoothing).
- 100 m: CrossTwin's local variant. A 1 km support dilutes the pixels at the
  edge of a city (half its window is fields), so density is taken over a 3 x 3
  window (300 m) and divided by the window's *settlement land* only. Fields,
  forest and water beyond the edge leave the denominator, and the edge stays
  at the last dwellings. Only settlement cells can join a centre or cluster,
  hole filling and smoothing are restricted to settlement cells, and cells
  outside the settlement mask fall back to gross window density (rural classes).

Grid classes (level 2 -> level 1):
    30 urban centre                 -> 3 urban centre
    23 dense urban cluster          -> 2 urban cluster
    22 semi-dense urban cluster     -> 2
    21 suburban / peri-urban cells  -> 2
    13 rural cluster                -> 1 rural
    12 low density rural cells      -> 1
    11 very low density rural cells -> 1
    10 water cells                  -> 1
     0 outside the grid (no imported neighborhood)

Sources: Eurostat (2021) Applying the Degree of Urbanisation, 2021 edition,
Methodological manual; Dijkstra et al. (2021) J. Urban Econ. 125, 103312;
Schiavina et al. (2023) GHS-SMOD R2023A; human-settlement.emergency.copernicus.eu
/degurbaDefinitions.php. Constants marked (†) are checked against the manual:
see the decision log in docs/DEGREE_OF_URBANISATION.md.
"""

# -- Thresholds (original values; densities in inhabitants per km²) ----------
CENTRE_DENSITY = 1500          # urban centre and dense urban cluster cells
CLUSTER_DENSITY = 300          # urban cluster and rural cluster cells
LOW_DENSITY = 50               # low (12) vs very low (11) density rural cells
BUILT_UP_SHARE = 0.5           # a cell >= 50 % built-up may join an urban centre
CENTRE_POP = 50_000            # urban centre population
CLUSTER_POP = 5_000            # (dense / semi-dense) urban cluster population
RURAL_CLUSTER_POP = 500        # rural cluster population
HOLE_MAX_KM2 = 15.0            # gaps inside an urban centre below this are filled
SMOOTH_MIN_NEIGHBOURS = 5      # a cell with >= 5 of 8 neighbours in a centre joins it
SEMI_DENSE_BUFFER_KM = 2.0     # (†) semi-dense = > 2 km (edge to edge) from a centre / dense cluster
WATER_SHARE = 0.5              # a cell >= 50 % permanent water without people is water (10)
MIN_LAND_SHARE = 0.05          # below this land share, density uses the whole cell (avoid / ~0)

# -- CrossTwin 100 m variant ---------------------------------------------------
LOCAL_RESOLUTION_M = 100
ORIGINAL_RESOLUTION_M = 1000
LOCAL_WINDOW_CELLS = 3         # 300 m support of the 100 m density
SMOOTH_MAX_ITERATIONS = 200

L2_CLASSES = {
    30: "Urban centre",
    23: "Dense urban cluster",
    22: "Semi-dense urban cluster",
    21: "Suburban or peri-urban",
    13: "Rural cluster",
    12: "Low density rural",
    11: "Very low density rural",
    10: "Water",
}
L1_OF_L2 = {30: 3, 23: 2, 22: 2, 21: 2, 13: 1, 12: 1, 11: 1, 10: 1, 0: 0}
L1_CLASSES = {3: "Urban centre", 2: "Urban cluster", 1: "Rural"}

FOUR = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]
EIGHT = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]


def variant(resolution_m):
    """Default (window_cells, masked) of a resolution: 100 m local, 1 km original."""
    if int(resolution_m) == LOCAL_RESOLUTION_M:
        return LOCAL_WINDOW_CELLS, True
    return 1, False


def _window_sum(a, size):
    """Sum over a size x size window centred on each cell (zero outside the grid)."""
    import numpy as np
    from scipy import ndimage

    if size <= 1:
        return a.astype(float)
    return ndimage.uniform_filter(a.astype(float), size=size, mode="constant", cval=0.0) * (size * size)


def density(pop, water_share, settlement, resolution_m, window_cells=1, masked=False):
    """
    (density inh./km², gross density) per cell.

    gross  = Σ_window pop / Σ_window land km²       (land = cell km² x (1 - water))
    masked = Σ_window pop / Σ_window settlement km² (settlement cells only)

    With masked=True a settlement cell gets the masked density and any other
    cell the gross one. A window with almost no land uses its full area.
    """
    import numpy as np

    cell_km2 = (resolution_m / 1000.0) ** 2
    land = np.clip(1.0 - water_share, 0.0, 1.0)
    pop_w = _window_sum(pop, window_cells)
    land_w = _window_sum(land, window_cells) * cell_km2
    full_w = _window_sum(np.ones_like(pop, dtype=float), window_cells) * cell_km2
    land_w = np.where(land_w < MIN_LAND_SHARE * full_w, full_w, land_w)
    gross = pop_w / land_w
    if not masked:
        return gross, gross
    settle_w = _window_sum(settlement.astype(float), window_cells) * cell_km2
    net = np.divide(pop_w, settle_w, out=gross.copy(), where=settle_w > 0)
    return np.where(settlement, net, gross), gross


def _components(mask, structure):
    from scipy import ndimage

    labels, n = ndimage.label(mask, structure=structure)
    return labels, n


def _component_sums(labels, n, values):
    from scipy import ndimage
    import numpy as np

    if n == 0:
        return np.zeros(1)
    return np.concatenate([[0.0], ndimage.sum(values, labels, index=range(1, n + 1))])


def _keep(mask, pop, structure, lo, hi=None):
    """Cells of the components of `mask` whose population is in [lo, hi)."""
    import numpy as np

    labels, n = _components(mask, structure)
    sums = _component_sums(labels, n, pop)
    ok = sums >= lo
    if hi is not None:
        ok &= sums < hi
    ok[0] = False
    return ok[labels]


def _fill_holes(centre, allowed, resolution_m):
    """Fill gaps enclosed by an urban centre smaller than HOLE_MAX_KM2, only where `allowed`."""
    import numpy as np
    from scipy import ndimage

    filled = ndimage.binary_fill_holes(centre, structure=FOUR)
    holes = filled & ~centre
    if not holes.any():
        return centre
    labels, n = _components(holes, FOUR)
    cell_km2 = (resolution_m / 1000.0) ** 2
    sizes = _component_sums(labels, n, np.ones_like(holes, dtype=float)) * cell_km2
    blocked = _component_sums(labels, n, (~allowed).astype(float))
    fill = (sizes < HOLE_MAX_KM2) & (blocked == 0)
    fill[0] = False
    return centre | fill[labels]


def _smooth(centre, allowed):
    """Repeatedly add cells with >= SMOOTH_MIN_NEIGHBOURS of their 8 neighbours in a centre."""
    import numpy as np
    from scipy import ndimage

    kernel = np.array(EIGHT)
    kernel[1, 1] = 0
    for _ in range(SMOOTH_MAX_ITERATIONS):
        neighbours = ndimage.convolve(centre.astype(int), kernel, mode="constant", cval=0)
        add = ~centre & allowed & (neighbours >= SMOOTH_MIN_NEIGHBOURS)
        if not add.any():
            break
        centre = centre | add
    return centre


def classify(pop, built_m2, water_share, settlement, coverage=None, resolution_m=LOCAL_RESOLUTION_M,
             window_cells=None, masked=None, occupied=None):
    """
    Classify a grid. Arrays are 2-D and aligned (row = y, column = x):

        pop          people per cell
        built_m2     building footprint m² per cell
        water_share  permanent water share 0..1
        settlement   bool, settlement land (land-cover mask or a dwelling)
        coverage     share of the cell inside imported neighborhoods 0..1;
                     0 = outside the grid (class 0)
        occupied     bool, cells that count as settlement because people live
                     there (default: pop > 0). The pipeline passes cells with
                     dwellings, so people spread by area over a neighborhood
                     without dwellings do not turn its fields into settlement.

    window_cells / masked default to the resolution's variant (see variant()).
    Returns a dict of arrays: l2, l1, density, built_up_share, cluster_id,
    cluster_population, edge_effect.
    """
    import numpy as np
    from scipy import ndimage

    pop = np.nan_to_num(np.asarray(pop, dtype=float))
    built_m2 = np.nan_to_num(np.asarray(built_m2, dtype=float))
    water_share = np.nan_to_num(np.asarray(water_share, dtype=float))
    settlement = np.asarray(settlement, dtype=bool)
    coverage = np.ones_like(pop) if coverage is None else np.nan_to_num(np.asarray(coverage, dtype=float))
    default_window, default_masked = variant(resolution_m)
    window_cells = default_window if window_cells is None else int(window_cells)
    masked = default_masked if masked is None else bool(masked)

    valid = coverage > 0
    occupied = (pop > 0) if occupied is None else np.asarray(occupied, dtype=bool)
    settlement = settlement | occupied
    allowed = valid & (settlement if masked else True)

    dens, gross = density(pop, water_share, settlement, resolution_m, window_cells, masked)
    cell_m2 = float(resolution_m) ** 2
    built_share = _window_sum(built_m2, window_cells) / (_window_sum(np.ones_like(pop), window_cells) * cell_m2)

    dense_cell = allowed & ((dens >= CENTRE_DENSITY) | (built_share >= BUILT_UP_SHARE))
    cluster_cell = allowed & (dens >= CLUSTER_DENSITY)

    # Urban centres: 4-connected, >= 50 000, gaps filled, edges smoothed.
    centre = _keep(dense_cell, pop, FOUR, CENTRE_POP)
    if centre.any():
        centre = _fill_holes(centre, allowed, resolution_m)
        centre = _smooth(centre, allowed)

    # Dense urban clusters: the same cells, 4-connected, 5 000 - 49 999, not in a centre.
    dense = _keep(dense_cell & ~centre, pop, FOUR, CLUSTER_POP, CENTRE_POP)

    # Urban clusters: >= 300, 8-connected, >= 5 000 (centres are subsets).
    urban = _keep(cluster_cell | centre | dense, pop, EIGHT, CLUSTER_POP)

    # Semi-dense: whole urban clusters with no centre / dense cell, > buffer from them.
    semi = np.zeros_like(urban)
    core = centre | dense
    labels, n = _components(urban, EIGHT)
    if n:
        if core.any():
            distance_m = ndimage.distance_transform_edt(~core) * resolution_m
        else:
            distance_m = np.full(pop.shape, np.inf)
        has_core = _component_sums(labels, n, core.astype(float)) > 0
        nearest = ndimage.minimum(distance_m, labels, index=range(1, n + 1))
        far = np.concatenate([[False], np.asarray(nearest) > SEMI_DENSE_BUFFER_KM * 1000.0])
        ok = far & ~has_core
        ok[0] = False
        semi = ok[labels]
    suburban = urban & ~core & ~semi

    rural_cluster = _keep(cluster_cell & ~urban, pop, EIGHT, RURAL_CLUSTER_POP, CLUSTER_POP)

    l2 = np.where(valid, 11, 0)
    l2 = np.where(valid & (gross >= LOW_DENSITY), 12, l2)
    if masked:
        l2 = np.where(valid & settlement & (dens >= LOW_DENSITY), 12, l2)
    l2 = np.where(valid & (water_share >= WATER_SHARE) & (pop <= 0), 10, l2)
    l2 = np.where(rural_cluster, 13, l2)
    l2 = np.where(suburban, 21, l2)
    l2 = np.where(semi, 22, l2)
    l2 = np.where(dense, 23, l2)
    l2 = np.where(centre, 30, l2)
    l1 = np.vectorize(L1_OF_L2.get)(l2) if l2.size else l2

    # Cluster ids: centres / dense (4-conn), other urban and rural clusters (8-conn).
    cluster_id = np.zeros(pop.shape, dtype=int)
    cluster_pop = np.zeros(pop.shape, dtype=float)
    edge = np.zeros(pop.shape, dtype=bool)
    offset = 0
    incomplete = ~valid | (coverage < 0.99)
    incomplete_near = ndimage.binary_dilation(incomplete, structure=EIGHT) | _border(pop.shape)
    for mask, structure in ((centre, FOUR), (dense, FOUR), (semi | suburban, EIGHT), (rural_cluster, EIGHT)):
        labels, n = _components(mask, structure)
        if not n:
            continue
        sums = _component_sums(labels, n, pop)
        touches = _component_sums(labels, n, incomplete_near.astype(float)) > 0
        cluster_id = np.where(mask, labels + offset, cluster_id)
        cluster_pop = np.where(mask, sums[labels], cluster_pop)
        edge |= mask & touches[labels]
        offset += n

    return {
        "l2": l2.astype(int), "l1": np.asarray(l1, dtype=int), "density": dens,
        "built_up_share": built_share, "cluster_id": cluster_id,
        "cluster_population": cluster_pop, "edge_effect": edge,
    }


def _border(shape):
    import numpy as np

    b = np.zeros(shape, dtype=bool)
    if b.size:
        b[0, :] = b[-1, :] = b[:, 0] = b[:, -1] = True
    return b
