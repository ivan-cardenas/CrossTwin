"""
Checks on core/DAG.dot (docs/DAG_REVISIONS.md).

- The causal graph is acyclic once the lagged feedback edges (`[lag=1]`) are
  left out: a lagged edge acts one planning step later, so it is not part of
  the same-time graph and no receiver implements it.
- Only the edges listed in LAGGED_EDGES carry a lag; a new loop must be
  argued in docs/DAG_REVISIONS.md before it is added.
- Every `A -> B` that code cites between two DAG nodes is an edge of the
  graph, so a removed edge (e.g. the former Urbanization node) cannot linger
  in docstrings.
"""
import re
from collections import defaultdict, deque
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

DAG_PATH = Path(settings.BASE_DIR) / "core" / "DAG.dot"

# Feedback edges allowed to close a loop, each argued in docs/DAG_REVISIONS.md.
LAGGED_EDGES = {("Network", "New_Units")}

# Relations cited in code before core/test_dag.py existed that are not DAG
# edges (derived quantities between two nodes). Listed here so new drift fails;
# remove an entry once its edge is added to DAG.dot or its citation fixed.
KNOWN_UNDECLARED = {
    ("Total_Population", "Household_Size"),   # housing: average size = population / households
    ("Metered_Res_Water", "OPEX_Recovery"),   # watersupply OPEX recovery docstring
    ("Total_Population", "Total_Water_Prod"), # watersupply: watershed share of extraction
}

SKIP_DIRS = {".venv", ".claude", "graphify-out", "node_modules", "migrations", "__pycache__"}


def parse_dag(text=None):
    """(nodes, edges): edges as (source, target, attrs) tuples, legend excluded."""
    text = DAG_PATH.read_text(encoding="utf-8") if text is None else text
    body = re.sub(r"subgraph cluster_legend \{.*?\n    \}", "", text, flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)
    nodes = set(re.findall(r"^[ \t]*(\w+)[ \t]*\[label", body, flags=re.M))
    edges = re.findall(r"^[ \t]*(\w+)[ \t]*->[ \t]*(\w+)[ \t]*(\[[^\]]*\])?", body, flags=re.M)
    return nodes, edges


def is_acyclic(edges):
    """Kahn's algorithm over (source, target) pairs."""
    out, indegree = defaultdict(set), defaultdict(int)
    nodes = set()
    for a, b in edges:
        nodes |= {a, b}
        if b not in out[a]:
            out[a].add(b)
            indegree[b] += 1
    queue = deque(n for n in nodes if indegree[n] == 0)
    seen = 0
    while queue:
        n = queue.popleft()
        seen += 1
        for m in out[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                queue.append(m)
    return seen == len(nodes)


class DagStructureTests(SimpleTestCase):
    def setUp(self):
        self.nodes, self.edges = parse_dag()
        self.pairs = {(a, b) for a, b, _ in self.edges}
        self.lagged = {(a, b) for a, b, attrs in self.edges if "lag" in attrs}

    def test_every_edge_joins_declared_nodes(self):
        undeclared = sorted({n for pair in self.pairs for n in pair} - self.nodes)
        self.assertEqual(undeclared, [])

    def test_acyclic_without_lagged_edges(self):
        self.assertTrue(is_acyclic(self.pairs - self.lagged))

    def test_only_documented_edges_are_lagged(self):
        self.assertEqual(self.lagged, LAGGED_EDGES)

    def test_lagged_edge_closes_the_urban_growth_loop(self):
        """With the lag the graph has the reinforcing loop; it is why the edge is lagged."""
        self.assertFalse(is_acyclic(self.pairs))

    def test_urbanization_node_is_gone(self):
        """Replaced by Degree_Urbanisation (State) on 2026-11-10."""
        self.assertNotIn("Urbanization", self.nodes)
        self.assertIn("Degree_Urbanisation", self.nodes)
        for edge in [("Total_Population", "Degree_Urbanisation"), ("Buildings", "Degree_Urbanisation"),
                     ("LandCover", "Degree_Urbanisation"), ("New_Units", "Buildings"),
                     ("Streets", "Buildings"), ("Buildings", "LandCover"),
                     ("Streets", "LandCover"), ("LandCover", "CityArea")]:
            self.assertIn(edge, self.pairs)
        self.assertNotIn(("New_Units", "LandCover"), self.pairs)

    def test_parser_reads_lines_without_semicolon(self):
        nodes, edges = parse_dag('A [label="A"];\nB [label="B"];\nC [label="C"];\nA -> B\nB -> C;\n')
        self.assertEqual({(a, b) for a, b, _ in edges}, {("A", "B"), ("B", "C")})


class DagStatusTests(SimpleTestCase):
    """core/dag_status.py (read by tools/dag_view.py) covers exactly the DAG's edges and nodes."""

    def test_every_edge_has_one_status(self):
        from core.dag_status import EDGE_STATUS
        _, edges = parse_dag()
        pairs = {(a, b) for a, b, _ in edges}
        self.assertEqual(sorted(pairs - set(EDGE_STATUS)), [])
        self.assertEqual(sorted(set(EDGE_STATUS) - pairs), [])
        for edge, (status, _, _) in EDGE_STATUS.items():
            self.assertIn(status, {"implemented", "partial", "gap", "lagged"}, edge)

    def test_lagged_status_matches_the_graph(self):
        from core.dag_status import EDGE_STATUS
        self.assertEqual({e for e, (s, _, _) in EDGE_STATUS.items() if s == "lagged"}, LAGGED_EDGES)

    def test_every_node_has_a_sector(self):
        from core.dag_status import NODE_SECTOR
        nodes, _ = parse_dag()
        self.assertEqual(sorted(nodes - set(NODE_SECTOR)), [])


class DagCitationTests(SimpleTestCase):
    def test_code_cites_only_dag_edges(self):
        nodes, edges = parse_dag()
        pairs = {(a, b) for a, b, _ in edges}
        known = nodes | {"Urbanization"}
        stale = defaultdict(set)
        root = Path(settings.BASE_DIR)
        for path in root.rglob("*.py"):
            if SKIP_DIRS & set(path.relative_to(root).parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for a, b in re.findall(r"\b([A-Z][A-Za-z_]+)\s*->\s*([A-Z][A-Za-z_]+)\b", text):
                if a in known and b in known and (a, b) not in pairs and (a, b) not in KNOWN_UNDECLARED:
                    stale[str(path.relative_to(root))].add((a, b))
        self.assertEqual(dict(stale), {})
