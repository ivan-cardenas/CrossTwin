"""Generate the CrossTwin architecture diagram suite (SVG) into docs/architecture/latest/.

Hand-laid-out diagrams (coordinates chosen per diagram) rendered with a tiny SVG DSL.
Flow edges are animated with CSS (stroke-dashoffset); the animation is ignored by
static renderers, so the same SVG is used for PNG/PDF export (tools/arch_export.py).

    python tools/arch_diagrams.py
"""
from pathlib import Path
from html import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture" / "latest"

# name: (stroke, fill, text)
PALETTE = {
    "client":   ("#2563eb", "#eff6ff", "#1e3a8a"),
    "django":   ("#7c3aed", "#f5f3ff", "#4c1d95"),
    "data":     ("#059669", "#ecfdf5", "#064e3b"),
    "external": ("#ea580c", "#fff7ed", "#7c2d12"),
    "raster":   ("#0891b2", "#ecfeff", "#164e63"),
    "cache":    ("#d97706", "#fffbeb", "#78350f"),
    "signal":   ("#e11d48", "#fff1f2", "#881337"),
    "neutral":  ("#475569", "#f8fafc", "#0f172a"),
}

FONT = "'Inter','Segoe UI',system-ui,-apple-system,sans-serif"
MONO = "'IBM Plex Mono','Cascadia Code',Consolas,monospace"

STYLE = f"""
  .t {{ font-family:{FONT}; }}
  .m {{ font-family:{MONO}; }}
  .flow {{ stroke-dasharray:7 5; animation:dash 1.2s linear infinite; }}
  @keyframes dash {{ to {{ stroke-dashoffset:-24; }} }}
  @media (prefers-reduced-motion: reduce) {{ .flow {{ animation:none; }} }}
"""


class Diagram:
    def __init__(self, name, title, subtitle, w=1600, h=1000):
        self.name, self.title, self.subtitle, self.w, self.h = name, title, subtitle, w, h
        self.back, self.mid, self.front = [], [], []

    # -- primitives -------------------------------------------------------
    def group(self, x, y, w, h, label, kind="neutral", tag=None, dashed=False):
        s, f, t = PALETTE[kind]
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.back.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{f}" fill-opacity="0.55" '
            f'stroke="{s}" stroke-opacity="0.55" stroke-width="1.5"{dash}/>'
            f'<text class="t" x="{x+20}" y="{y+30}" font-size="15" font-weight="700" fill="{t}" '
            f'letter-spacing="0.4">{escape(label.upper())}</text>')
        if tag:
            tw = 9 + 7.4 * len(tag)
            self.back.append(
                f'<rect x="{x+w-tw-16}" y="{y+13}" width="{tw}" height="24" rx="12" fill="{s}"/>'
                f'<text class="m" x="{x+w-tw/2-16}" y="{y+30}" font-size="12" fill="#fff" '
                f'text-anchor="middle" font-weight="600">{escape(tag)}</text>')

    def box(self, x, y, w, h, title, lines=(), kind="neutral", tag=None, mono_lines=False):
        s, f, t = PALETTE[kind]
        out = [f'<rect x="{x+2}" y="{y+4}" width="{w}" height="{h}" rx="12" fill="#0f172a" fill-opacity="0.06"/>',
               f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#fff" stroke="{s}" stroke-width="1.8"/>',
               f'<path d="M{x+12},{y} h{w-24} a12,12 0 0 1 12,12 v6 h-{w} v-6 a12,12 0 0 1 12,-12 z" fill="{s}"/>']
        ty = y + 42
        out.append(f'<text class="t" x="{x+16}" y="{ty}" font-size="16" font-weight="700" fill="{t}">{escape(title)}</text>')
        if tag:
            tw = 8 + 7 * len(tag)
            out.append(f'<rect x="{x+w-tw-12}" y="{y+26}" width="{tw}" height="22" rx="11" fill="{f}" stroke="{s}" stroke-width="1"/>'
                       f'<text class="m" x="{x+w-tw/2-12}" y="{y+41}" font-size="11.5" fill="{t}" text-anchor="middle">{escape(tag)}</text>')
        cls = "m" if mono_lines else "t"
        fs = 12 if mono_lines else 13
        for i, ln in enumerate(lines):
            out.append(f'<text class="{cls}" x="{x+16}" y="{ty+22+i*18}" font-size="{fs}" fill="#475569">{escape(ln)}</text>')
        self.mid.append("".join(out))
        return (x, y, w, h)

    def pill(self, x, y, text, kind="neutral"):
        s, f, t = PALETTE[kind]
        w = 16 + 6.9 * len(text)
        self.mid.append(f'<rect x="{x}" y="{y}" width="{w}" height="24" rx="12" fill="{f}" stroke="{s}" stroke-width="1.2"/>'
                        f'<text class="m" x="{x+w/2}" y="{y+16}" font-size="11.5" fill="{t}" text-anchor="middle">{escape(text)}</text>')
        return w

    def note(self, x, y, lines, color="#64748b", size=12.5, italic=True):
        st = ' font-style="italic"' if italic else ""
        for i, ln in enumerate(lines):
            self.front.append(f'<text class="t" x="{x}" y="{y+i*17}" font-size="{size}" fill="{color}"{st}>{escape(ln)}</text>')

    def edge(self, pts, kind="neutral", label=None, step=None, flow=True, dashed=False, label_at=None, both=False):
        s = PALETTE[kind][0]
        d = "M" + " L".join(f"{px},{py}" for px, py in pts)
        cls = ' class="flow"' if flow and not dashed else ""
        dash = ' stroke-dasharray="3 5"' if dashed else ""
        start = f' marker-start="url(#as-{kind})"' if both else ""
        self.front.insert(0, f'<path d="{d}" fill="none" stroke="{s}" stroke-width="2.2" stroke-linejoin="round"'
                             f'{cls}{dash} marker-end="url(#a-{kind})"{start}/>')
        if label or step:
            i = label_at if label_at is not None else (len(pts) - 1) // 2
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if label:
                w = 14 + 6.6 * len(label)
                off = 14 if step else 0
                self.front.append(
                    f'<rect x="{mx-w/2+off}" y="{my-11}" width="{w}" height="22" rx="11" fill="#fff" stroke="{s}" stroke-width="1"/>'
                    f'<text class="t" x="{mx+off}" y="{my+4.5}" font-size="12" fill="#334155" text-anchor="middle">{escape(label)}</text>')
                if step:
                    mx = mx - w / 2 + off - 13
            if step:
                self.front.append(
                    f'<circle cx="{mx}" cy="{my}" r="12" fill="{s}" stroke="#fff" stroke-width="2"/>'
                    f'<text class="t" x="{mx}" y="{my+4.5}" font-size="12.5" font-weight="700" fill="#fff" text-anchor="middle">{step}</text>')

    def legend(self, items, x=None, y=None):
        x = 40 if x is None else x
        y = self.h - 34 if y is None else y
        for kind, label in items:
            s, f, _ = PALETTE[kind]
            self.front.append(f'<rect x="{x}" y="{y-12}" width="16" height="16" rx="4" fill="{f}" stroke="{s}" stroke-width="1.8"/>'
                              f'<text class="t" x="{x+24}" y="{y+1}" font-size="12.5" fill="#475569">{escape(label)}</text>')
            x += 40 + 7.2 * len(label)

    # -- output -------------------------------------------------------------
    def svg(self):
        markers = "".join(
            f'<marker id="a-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{s}"/></marker>'
            f'<marker id="as-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{s}"/></marker>'
            for k, (s, _, _) in PALETTE.items())
        head = (f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>'
                f'<rect width="{self.w}" height="6" fill="#7c3aed"/>'
                f'<text class="t" x="40" y="58" font-size="30" font-weight="800" fill="#0f172a">{escape(self.title)}</text>'
                f'<text class="t" x="40" y="86" font-size="15" fill="#64748b">{escape(self.subtitle)}</text>'
                f'<text class="m" x="{self.w-40}" y="58" font-size="12" fill="#94a3b8" text-anchor="end">CrossTwin · architecture</text>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{escape(self.title)}">'
                f'<title>{escape(self.title)}</title><style>{STYLE}</style><defs>{markers}</defs>'
                f'{head}{"".join(self.back)}'
                + "".join(p for p in self.front if p.startswith("<path"))
                + "".join(self.mid)
                + "".join(p for p in self.front if not p.startswith("<path"))
                + "</svg>")


# =========================================================================
# 1. System overview
# =========================================================================
def overview():
    d = Diagram("01-overview", "CrossTwin — System Overview",
                "Django + PostGIS digital twin for Dutch urban data (EPSG:28992), with a separate TiTiler process for raster tiles", h=1040)
    # Browser
    d.group(40, 120, 300, 700, "Browser", "client")
    d.box(60, 170, 260, 120, "Map UI", ["Mapbox GL JS", "Layers.js · Map_init.js", "mainMap.js · Events.js"], "client")
    d.box(60, 310, 260, 120, "Indicator panels", ["HTMX swaps (hx-get)", "water · heat · housing · builtup", "what-if sliders + switches"], "client")
    d.box(60, 450, 260, 120, "Map editing", ["Editing.js +", "Mapbox GL Draw", "(staff only)"], "client")
    d.box(60, 590, 260, 100, "Population dock", ["forecast curve +", "what-if controls"], "client")
    d.box(60, 710, 260, 90, "Django admin", ["/admin/ (staff login)"], "client")

    # Django
    d.group(400, 120, 640, 700, "Django · DigitalTwin", "django", tag=":8000")
    d.box(420, 170, 600, 76, "URL router  (DigitalTwin/urls.py)", ["/  ·  /api/  ·  /watersupply/  ·  /housing/  ·  /urban_heat/  ·  /weather/  ·  /importer/"], "django")
    d.box(420, 266, 290, 150, "mainMap", ["layer catalog  /api/layers/", "GeoJSON + bounds endpoints", "admin-unit & population panels", "editing.py (forms, backup)"], "django")
    d.box(730, 266, 290, 150, "Domain apps", ["watersupply · housing · urban_heat", "administrative · physicalEnv", "builtup · nature · weather · Energy", "models + calculations.py + views"], "django")
    d.box(420, 436, 290, 150, "core", ["MODEL / VECTOR / RASTER /", "WMS registries (utils.py)", "rasterOperations → COG", "signals · cache versioning"], "django")
    d.box(730, 436, 290, 150, "importer", ["file upload (GeoJSON/SHP)", "external catalog (48 sets)", "SpatialParentIndex", "BulkWriter · deferred_cascades"], "django")
    d.box(420, 606, 290, 120, "weather WMS proxy", ["/weather/wms/<name>/tile/", "keep-alive session", "24 h cache for TIME= frames"], "django")
    d.box(730, 606, 290, 120, "Caches (LocMem)", ["geojson  — 2 min, ≤ 8 MB", "wms_tiles — 24 h / 5 min", "default"], "cache")
    d.note(420, 775, ["Signals keep derived data consistent: population & urban-area cascade,",
                      "watersupply indicator chain, raster → COG export, layer cache bumps."])

    # TiTiler + COG
    d.box(1100, 170, 240, 130, "TiTiler", ["FastAPI · tiler.py", "/cog/tiles/{z}/{x}/{y}", "/cog/info"], "raster", tag=":8001")
    d.box(1100, 436, 240, 130, "COG store", ["cogs/<app_label>/*.tif", "EPSG:4326, rio-cogeo", "written by post_save"], "raster")

    # External
    d.group(1390, 120, 170, 700, "External", "external")
    # title-only boxes: nine sources fill the column (subtitles are in 05-import-pipeline)
    ext = ["PDOK", "CBS", "BIS Nederland", "OpenStreetMap", "Sentinel-2", "Earth Engine", "KNMI", "RIVM", "WMS servers"]
    for i, n in enumerate(ext):
        d.box(1402, 165 + i * 72, 146, 58, n, [], "external")

    # DB
    d.box(400, 865, 940, 90, "PostgreSQL 16 + PostGIS", ["80 models · GeometryField & RasterField (srid 28992) · GiST indexes · pg_stat_statements"], "data")

    # Edges
    d.edge([(320, 230), (420, 230)], "client", "JSON / HTML")
    d.edge([(320, 370), (420, 370)], "client", "HTMX")
    d.edge([(320, 510), (395, 510), (395, 330), (420, 330)], "client")
    d.edge([(320, 640), (408, 640), (408, 400), (420, 400)], "client")
    d.edge([(190, 120), (190, 100), (1220, 100), (1220, 170)], "raster", "XYZ raster tiles (direct)", label_at=1)
    d.edge([(875, 416), (875, 436)], "django", flow=False)
    d.edge([(565, 416), (565, 436)], "django", flow=False)
    d.edge([(565, 586), (565, 606)], "django", flow=False)
    d.edge([(710, 666), (730, 666)], "cache", flow=False, both=True)
    d.edge([(690, 586), (690, 596), (1070, 596), (1070, 520), (1100, 520)], "raster")
    d.edge([(1020, 230), (1100, 230)], "raster", "/cog/info")
    d.edge([(1220, 436), (1220, 300)], "raster", "read COG")
    d.edge([(1402, 626), (1060, 626), (1060, 540), (1020, 540)], "external", "fetch datasets", label_at=0)
    d.edge([(1402, 770), (1370, 770), (1370, 743), (565, 743), (565, 726)], "external", "WMS GetMap", label_at=2)
    d.edge([(720, 820), (720, 865)], "data", "ORM + raw SQL", both=True, flow=False)
    d.legend([("client", "Browser"), ("django", "Django app"), ("raster", "Raster / tiles"),
              ("cache", "Cache"), ("data", "Storage"), ("external", "External source")])
    return d


# =========================================================================
# 2. Django app & registry map
# =========================================================================
def apps():
    d = Diagram("02-django-apps", "Django Apps & the Model Registry",
                "core/utils.py::build_model_registry() scans nine domain apps; every generic endpoint is driven by the registries",
                h=960)
    d.group(40, 120, 1520, 330, "Domain apps (allowed_apps)  —  models · calculations.py · views", "django")
    apps_ = [
        ("administrative", 5, ["Province › City ›", "District › Neighborhood", "PopulationProjection"]),
        ("physicalEnv", 16, ["LandCover · DEM · DSM", "soil map · groundwater", "HILUCS · soil.py (SCS)"]),
        ("watersupply", 17, ["extraction · treatment", "pipes · NRW · OPEX", "SupplySecurity"]),
        ("housing", 8, ["supply/demand · HPI", "mortgage · rentals", "affordability"]),
        ("urban_heat", 11, ["UTCI · PET · Tmrt", "LST · SVF · SUHII", "NBS · WBGT"]),
        ("builtup", 6, ["ZoningArea (HILUCS)", "Street · Park · Facility", "Building · Property"]),
        ("nature", 7, ["green / blue", "layers · trees"]),
        ("weather", 7, ["WMS layers", "time steps"]),
        ("Energy", 3, ["energy labels"]),
    ]
    x = 60
    for i, (n, c, lines) in enumerate(apps_):
        w = 165 if i < 6 else 128
        d.box(x, 170, w, 140 if i < 6 else 110, n, lines, "django", tag=str(c))
        x += w + 12
    d.note(60, 345, ["Number tags = model classes per app. Indicator dashboards (watersupply, housing, urban_heat, builtup) follow",
                     "calculations.py → views._build_indicators() → HTMX partial; MOCK_DATA fills in when a province is missing."])
    d.pill(60, 395, "DAG edges documented in calculations.py docstrings → core/DAG.dot (DPSIR)", "neutral")

    # registry
    d.box(560, 520, 480, 150, "build_model_registry()", ["core/utils.py — scans allowed_apps at startup", "", "has GeometryField, no RasterField → VECTOR", "has RasterField → RASTER  ·  'WMS' in key → WMS"], "django")
    regs = [("MODEL_REGISTRY", 100, "neutral"), ("VECTOR_REGISTRY", 480, "data"), ("RASTER_REGISTRY", 860, "raster"), ("WMS_REGISTRY", 1240, "external")]
    for n, x, k in regs:
        d.box(x, 730, 300, 70, n, ["all models" if n == "MODEL_REGISTRY" else {"VECTOR_REGISTRY": "GeoJSON, bounds, editing",
              "RASTER_REGISTRY": "COG export, tile URLs", "WMS_REGISTRY": "WMS layer catalog"}[n]], k)
        d.edge([(800, 670), (800, 700), (x + 150, 700), (x + 150, 730)], k, flow=False)
    d.edge([(800, 450), (800, 520)], "django", "scan models")

    consumers = [(100, "importer", "field mapping, upsert keys"), (480, "mainMap", "/api/layers/, GeoJSON, editing"),
                 (860, "core.signals", "post_save → COG, cache bump"), (1240, "weather", "WMS catalog, tile proxy")]
    for x, n, sub in consumers:
        d.box(x, 850, 300, 70, n, [sub], "neutral")
        d.edge([(x + 150, 800), (x + 150, 850)], "neutral", flow=False)
    d.legend([("django", "Django"), ("data", "Vector"), ("raster", "Raster"), ("external", "WMS")], x=1000, y=105)
    return d


# =========================================================================
# 3. Vector layer request (GeoJSON)
# =========================================================================
def vector():
    d = Diagram("03-vector-geojson", "Vector Layer Request — GeoJSON Path",
                "mainMap.views.model_geojson: one SQL statement per request, cached by per-model version", h=900)
    d.box(40, 200, 270, 170, "Layers.js", ["≥ 5 000 features →", "load by viewport (?bbox)", "reload on moveend", "(debounced, aborts stale)", "admin layers load whole"], "client")
    d.box(480, 200, 300, 170, "model_geojson", ["VECTOR_REGISTRY lookup", "key = model + version", "     + bbox + zoom", "→ HttpResponse(text)", "X-Cache: HIT | MISS"], "django")
    d.box(900, 160, 300, 120, "geojson cache", ["LocMem · 64 entries", "bodies ≤ 8 MB · TTL 2 min"], "cache")
    d.box(900, 330, 300, 170, "_geojson_sql()", ["ST_AsGeoJSON(", "  ST_Transform(geom, 4326), 6)", "LEFT JOIN FK display names", "geom && bbox (GiST)", "simplify ~1 px if zoom < 14"], "django")
    d.box(1300, 330, 260, 170, "PostGIS", ["one query → one", "FeatureCollection text", "built in the database"], "data")
    d.box(900, 640, 300, 150, "core/cache.py", ["bump_layer_version(model)", "on post_save / post_delete", "new version ⇒ new keys,", "old entries unreachable"], "cache")
    d.box(480, 640, 300, 150, "Writes via Django", ["obj.save() / delete()", "map editor · importer", "(bulk/update() must bump", " the version manually)"], "signal")

    d.edge([(310, 260), (480, 260)], "client", "GET ?bbox&zoom", step=1)
    d.edge([(780, 230), (900, 230)], "cache", "lookup", step=2)
    d.edge([(780, 340), (840, 340), (840, 415), (900, 415)], "django", "MISS", step=3, label_at=1)
    d.edge([(1200, 415), (1300, 415)], "data", "SQL", step=4)
    d.edge([(1430, 500), (1430, 570), (820, 570), (820, 300), (780, 300)], "data", "JSON text → cache.set", step=5, label_at=1)
    d.edge([(480, 330), (310, 330)], "client", "200 + X-Cache", step=6)
    d.edge([(780, 715), (900, 715)], "signal", "signal")
    d.note(480, 830, ["Edits from QGIS/psql bypass Django signals → visible only after the 2-min TTL expires.",
                      "LocMem is per process: with several workers, point CACHES at Redis so a bump reaches all of them."])
    d.note(40, 420, ["/bounds/ uses ST_EstimatedExtent", "only for tables ≥ 100 000 rows,", "exact ST_Extent otherwise."])
    return d


# =========================================================================
# 4. Raster pipeline
# =========================================================================
def raster():
    d = Diagram("04-raster-pipeline", "Raster Pipeline — PostGIS Raster → COG → Tiles",
                "core/rasterOperations.py::export_raster_to_cog() runs from a post_save signal on every RASTER_REGISTRY model", h=820)
    steps = [
        ("Raster import", ["GEE / Sentinel-2 /", "KNMI / file upload", "→ RasterField row"], "external"),
        ("post_save", ["core/signals.py", "RASTER_REGISTRY", "receiver"], "signal"),
        ("ST_AsGDALRaster", ["PostGIS → temp", "GeoTIFF (28992)"], "data"),
        ("Reproject", ["rasterio warp", "→ EPSG:4326"], "raster"),
        ("rio-cogeo", ["Cloud-Optimized", "GeoTIFF, overviews"], "raster"),
        ("COG on disk", ["cogs/<app_label>/", "path → cog_path"], "raster"),
    ]
    for i, (t, lines, k) in enumerate(steps):
        x = 40 + i * 255
        d.box(x, 170, 215, 130, t, lines, k)
        if i:
            d.edge([(x - 40, 235), (x, 235)], k, step=i)
    d.group(40, 380, 1520, 340, "Serving", "raster")
    d.box(80, 440, 300, 150, "Map UI", ["requests tile URL for a", "raster layer, then adds a", "Mapbox raster source"], "client")
    d.box(600, 440, 330, 150, "core.views.get_raster_tiles", ["builds TiTiler URL template:", "/cog/tiles/WebMercatorQuad/", "  {z}/{x}/{y}.png?url=…", "+ rescale · colormap · resampling"], "django")
    d.box(1000, 440, 230, 150, "rasterStyles", ["per-layer colormap", "and value range", "core/rasterStyles.py"], "neutral")
    d.box(1290, 440, 240, 150, "TiTiler :8001", ["FastAPI + rio-tiler", "reads COG byte ranges", "renders PNG tiles"], "raster")
    d.edge([(380, 480), (600, 480)], "client", "GET /api/raster/…/tiles/", step=1)
    d.edge([(600, 550), (380, 550)], "django", "tile_url template", step=2)
    d.edge([(230, 590), (230, 660), (1410, 660), (1410, 590)], "raster", "GET {z}/{x}/{y}.png — browser → TiTiler directly", step=3, label_at=1)
    d.edge([(1000, 515), (930, 515)], "neutral", flow=False, dashed=True)
    d.edge([(1410, 300), (1410, 440)], "raster", "read COG")
    d.note(40, 770, ["Heavy libs (rasterio, rio-cogeo, numpy) are imported inside export_raster_to_cog(), never at module level,",
                     "so Django startup and the URLconf stay fast; tests patch core.rasterOperations.export_raster_to_cog."])
    return d


# =========================================================================
# 5. Import pipeline
# =========================================================================
def importer():
    d = Diagram("05-import-pipeline", "Data Import Pipeline",
                "Two entry points — file upload and the catalog-driven external importers — share batching and deferred cascades", h=1080)
    d.group(40, 120, 330, 760, "Sources", "external")
    srcs = [("PDOK", "18 · WFS/OGC API/ATOM/WCS"), ("CBS", "4 · OData (85173NED…)"),
            ("BIS Nederland", "3 · soil WFS, GHG/GLG WCS"), ("OpenStreetMap", "4 · Overpass API"),
            ("Sentinel-2", "5 · openEO composites"), ("Google Earth Engine", "12 · GEEAuthManager"),
            ("KNMI Data Platform", "1 · fetch_latest (WBGT)"), ("RIVM", "1 · energy labels"),
            ("File upload", "GeoJSON / Shapefile")]
    for i, (n, s) in enumerate(srcs):
        d.box(60, 170 + i * 78, 290, 70, n, [s], "client" if n == "File upload" else "external")

    d.box(470, 170, 320, 150, "external_catalog.py", ["48 dataset definitions", "target model + field map", "__fk_lookup__ (HILUCS, soil)", "bbox_from (parent AOI)"], "django")
    d.box(470, 360, 320, 150, "*Importer classes", ["PDOK (+ BIS) · CBSImporter", "OSMImporter (Overpass)", "Sentinel2 · GEE · KNMI", "→ ImportResult"], "django")
    d.box(470, 580, 320, 150, "importer/views.py", ["upload · map fields", "preview · import", "MODEL_OVERRIDES upsert keys", "savepoints per row"], "django")

    d.group(880, 120, 360, 640, "importer/batching.py", "django")
    d.box(900, 170, 320, 150, "SpatialParentIndex", ["prepared geometries", "+ bbox pre-check", "probe point_on_surface", "→ __spatial_fk__ parent"], "django")
    d.box(900, 360, 320, 150, "BulkWriter", ["BULK_IMPORT_MODELS", "bulk_create × 500", "ON CONFLICT DO UPDATE", "retry row-by-row on error"], "django")
    d.box(900, 580, 320, 150, "deferred_cascades()", ["population cascade +", "urban-area recompute", "run once per parent", "when the block exits"], "signal")

    d.box(1330, 360, 230, 150, "PostGIS", ["vector rows", "raster rows", "(srid 28992)"], "data")
    d.box(1330, 580, 230, 150, "Finalizers", ["replay receivers", "skipped by", "bulk_create", "+ bump_layer_version"], "signal")

    for i in range(8):
        y = 205 + i * 78
        d.edge([(350, y), (410, y), (410, 435), (470, 435)], "external", flow=False)
    d.edge([(630, 320), (630, 360)], "django", "configure")
    d.edge([(350, 829), (440, 829), (440, 655), (470, 655)], "client")
    d.edge([(790, 435), (840, 435), (840, 245), (900, 245)], "django", "features", label_at=1)
    d.edge([(1060, 320), (1060, 360)], "django", "parent FK")
    d.edge([(790, 655), (840, 655), (840, 470), (900, 470)], "django", label_at=1)
    d.edge([(1220, 435), (1330, 435)], "data", "write")
    d.edge([(1220, 655), (1330, 655)], "signal")
    d.edge([(1445, 580), (1445, 510)], "signal", "update()")
    d.edge([(1060, 510), (1060, 580)], "signal", "inside", flow=False, dashed=True)
    d.note(40, 925, ["A model may be in BULK_IMPORT_MODELS only if it has no save() override (BulkImportRegistryTests) —",
                     "e.g. LandCoverVector, Street, Facility, SoilArea, the nature layers, Tree; a new post_save receiver on one needs its finalizer too.",
                     "Known gap: _generic_import (file upload) maps geometry/raster fields only — attribute columns are not imported."])
    d.legend([("external", "External source"), ("client", "User upload"), ("django", "Importer code"), ("signal", "Cascades"), ("data", "Storage")])
    return d


# =========================================================================
# 6. Signal cascades
# =========================================================================
def signals():
    d = Diagram("06-signal-cascades", "Signal-Driven Derived Data",
                "post_save / post_delete receivers keep aggregates and indicator chains consistent; update() avoids recursion", h=1000)
    # administrative
    d.group(40, 120, 470, 560, "administrative/signals.py", "signal")
    lv = ["Neighborhood", "District", "City", "Province"]
    for i, n in enumerate(lv):
        d.box(125, 170 + i * 125, 300, 80, n, ["currentPopulation · density · urban_area" if i else "saved / deleted"], "neutral")
        if i:
            d.edge([(275, 170 + i * 125 - 45), (275, 170 + i * 125)], "signal", "_recompute_population()" if i == 1 else "update()")
    d.note(60, 660, ["Sums both population and urban_area per level."])

    # physicalEnv
    d.group(560, 120, 470, 330, "physicalEnv/signals.py", "signal")
    d.box(600, 170, 390, 80, "LandCoverVector saved", ["schedule_urban_area_recompute(city_id)"], "neutral")
    d.box(600, 300, 390, 120, "One set-based UPDATE … RETURNING", ["ST_Intersection with urban-fabric polygons", "(latest year), skipped when fully inside;", "ST_Area in storage-CRS metres"], "data")
    d.edge([(795, 250), (795, 300)], "signal")
    d.edge([(600, 360), (540, 360), (540, 210), (425, 210)], "signal", "re-enter cascade", label_at=1)

    # core
    d.group(560, 490, 470, 190, "core/signals.py", "signal")
    d.box(590, 540, 200, 110, "RASTER post_save", ["export_raster_to_cog()"], "raster")
    d.box(810, 540, 200, 110, "VECTOR save/delete", ["bump_layer_version()", "→ GeoJSON cache"], "cache")

    # watersupply
    d.group(1080, 120, 480, 840, "watersupply/signals.py + save()", "signal")
    chain = [("Population (cascade)", "neutral"), ("ConsumptionCapita", "django"), ("TotalWaterDemand", "django"),
             ("SupplySecurity", "django"), ("Service_Time", "django")]
    for i, (n, k) in enumerate(chain):
        d.box(1110, 170 + i * 120, 200, 70, n, [], k)
        if i:
            d.edge([(1210, 170 + i * 120 - 50), (1210, 170 + i * 120)], "signal", flow=True)
    prod = [("ExtractionWater", 170), ("ImportedWater", 290), ("TotalWaterProduction", 410)]
    for n, y in prod:
        d.box(1340, y, 200, 70, n, [], "django")
    d.edge([(1440, 240), (1440, 290)], "signal")
    d.edge([(1440, 360), (1440, 410)], "signal")
    d.edge([(1340, 445), (1310, 445), (1310, 530)], "signal", flow=True)
    d.box(1340, 650, 200, 120, "OPEX", ["extraction · imported", "treatment · pipes"], "django")
    d.box(1340, 820, 200, 110, "Coverage", ["PipeNetwork +", "UsersLocation"], "django")
    d.box(1110, 820, 200, 110, "NonRevenueWater", ["→ same-year ILI"], "django")
    d.edge([(1540, 205), (1555, 205), (1555, 710), (1540, 710)], "signal", flow=False, dashed=True)
    d.note(1110, 795, ["WaterTreatment · MeteredResidential · PipeNetwork → OPEX"], size=11.5)

    d.group(40, 720, 990, 240, "Bulk writes  ·  importer/batching.py::deferred_cascades()", "neutral", dashed=True)
    d.note(70, 785, ["= administrative.deferred_population_cascade()  +  physicalEnv.deferred_urban_area()",
                     "",
                     "Inside the block, receivers only record the affected parent; on exit each cascade runs once per parent",
                     "(errors during that flush are logged, never raised over the original exception).",
                     "Always call schedule_urban_area_recompute() rather than the recompute itself, so an enclosing deferral is respected."],
           color="#334155", italic=False, size=13.5)
    return d


# =========================================================================
# 7. Map editing & what-if backup
# =========================================================================
def editing():
    d = Diagram("07-map-editing", "Map Editing & What-If Backup",
                "Staff edit EDITABLE_LAYERS on the map; every change goes through obj.save() and is journalled for one-click restore",
                h=860)
    d.box(40, 170, 300, 170, "Editing.js", ["MutationObserver on #panel-body", "attaches Mapbox GL Draw", "popups & panel refresh", "suspended while editing"], "client")
    d.box(450, 170, 330, 170, "editing.feature_form", ["modelform_factory ModelForm", "geometry: WGS84 GeoJSON in", "hidden field → reprojected", "exclude / optional per layer"], "django")
    d.box(890, 170, 300, 170, "obj.save()", ["derived fields", "signals & cascades", "cache bump", "negative pk for BAG ids"], "django")
    d.box(1300, 170, 260, 170, "PostGIS", ["FKs DEFERRABLE", "INITIALLY DEFERRED", "_check_constraints()", "inside atomic block"], "data")

    d.box(450, 440, 330, 150, "journal()", ["store original row of each", "object before first change", "(first pre-image wins)"], "signal")
    d.box(890, 440, 300, 150, "EditBackup", ["one restore point at a time", "create · restore · discard", "/api/editing/backup/…"], "cache")
    d.box(890, 650, 300, 150, "restore_backup()", ["one transaction:", "raw saves of pre-images,", "delete objects created since,", "roll back on FK conflict"], "signal")
    d.box(40, 440, 300, 150, "HTMX events", ["feature-saved", "backup-restored", "→ Layers.reloadLayer()"], "client")

    d.edge([(340, 230), (450, 230)], "client", "GET/POST", step=1)
    d.edge([(615, 340), (615, 440)], "signal", "before change", step=2)
    d.edge([(780, 230), (890, 230)], "django", "valid", step=3)
    d.edge([(1190, 230), (1300, 230)], "data", "write", step=4)
    d.edge([(450, 300), (400, 300), (400, 515), (340, 515)], "client", "HX-Trigger", step=5, label_at=1)
    d.edge([(780, 515), (890, 515)], "signal", "rows")
    d.edge([(1040, 590), (1040, 650)], "cache", "restore")
    d.edge([(1190, 725), (1430, 725), (1430, 340)], "signal", "revert", label_at=1)
    d.note(40, 680, ["Only edits made through the editor are journalled —", "importer, admin and psql changes are not.",
                     "", "Make a layer editable: add its registry key to", "EDITABLE_LAYERS with exclude (fields save() derives)",
                     "and optional (fields save() fills in)."])
    return d


# =========================================================================
# 8. Soil hydrology & infiltration (SCS Curve Number)
# =========================================================================
def infiltration():
    d = Diagram("08-infiltration", "Soil Hydrology & Infiltration — SCS Curve Number",
                "physicalEnv/soil.py: soil map × land cover × groundwater → hydrologic soil group → curve number → infiltrated share of a rain event",
                h=900)
    # sources
    d.group(40, 120, 320, 580, "Sources", "external")
    d.box(60, 170, 280, 240, "BIS · soil map (WFS)", ["bodem:Bodemkaart50000_v2025", "soilcode · soil name (Dutch)", "1:50 000 · 48 025 polygons", "", "bodemdata_soil_map"], "external")
    d.box(60, 430, 280, 110, "BIS · groundwater (WCS)", ["bodem__ghg / glg-mediaan", "50 m · cm below ground", "254 = deeper · 255 = nodata"], "external")
    d.box(60, 560, 280, 110, "PDOK · BRT land cover", ["lc:landcoverunit (WFS)", "CORINE class names"], "external")
    # models
    d.group(400, 120, 370, 580, "physicalEnv models", "data")
    d.box(420, 170, 330, 110, "SoilType", ["code + name (unique)", "save(): classify_soil_group()", "→ soilGroup A–D, f min/max"], "data")
    d.box(420, 300, 330, 110, "SoilArea", ["mapAreaID · MultiPolygon", "FK soil_type (smallint)", "bulk-written"], "data")
    d.box(420, 430, 330, 110, "GroundwaterDepth", ["RasterField kept in PostGIS", "statistic GHG | GLG", "row per city · year · statistic"], "raster")
    d.box(420, 560, 330, 110, "LandCoverVector", ["+ LandCoverClasses (CORINE)", "latest year in the unit"], "data")
    # computation
    d.group(800, 120, 400, 580, "physicalEnv/soil.py", "django")
    d.box(820, 170, 360, 250, "soil_landcover_composition()", ["(geom, statistic) — one SQL statement:",
          "· pieces = soil ∩ land cover ∩ unit", "· ST_Reclass(GHG|GLG < 60 cm)", "  → ST_DumpAsPolygons → ST_Union",
          "· shallow ∧ undrained → group D", "· drained land keeps its texture group",
          "→ [(group, class, m²)], shallow, drained"], "data")
    d.box(820, 470, 360, 210, "summarize_infiltration(P)", ["pure Python, no query:", "curve_number(): TR-55 × CORINE",
          "S = 25400/CN − 254 · Ia = 0.2 S", "Q = (P − Ia)² / (P − Ia + S)", "runoff per piece, area-weighted",
          "→ C_inf · mean CN · V_inf · V_run"], "django")
    # dashboard
    d.group(1230, 120, 330, 580, "Water dashboard", "client")
    d.box(1250, 170, 290, 90, "Rain Event slider", ["rain_mm 1–100 mm (default 25)"], "client")
    d.box(1250, 290, 290, 90, "Groundwater switch", ["wet → GHG · dry → GLG"], "client")
    d.box(1250, 410, 290, 110, "watersupply/views.py", ["_get_adminUnit_data(season)", "_build_indicators(rain_mm)", "_infiltration_indicators()"], "django")
    d.box(1250, 550, 290, 130, "Infiltration card", ["C_inf % · mean CN", "infiltrated / runoff m³", "shallow GW → D · drained %", "soil groups + f range"], "client")
    # edges
    d.edge([(340, 225), (420, 225)], "external", "import")
    d.edge([(340, 355), (420, 355)], "external")
    d.edge([(340, 485), (420, 485)], "external", "WCS")
    d.edge([(340, 615), (420, 615)], "external", "WFS")
    d.edge([(750, 225), (820, 225)], "data", flow=False)
    d.edge([(750, 355), (820, 355)], "data", flow=False)
    d.edge([(750, 485), (795, 485), (795, 395), (820, 395)], "raster", flow=False)
    d.edge([(750, 615), (805, 615), (805, 410), (820, 410)], "data", flow=False)
    d.edge([(1000, 420), (1000, 470)], "django", "pieces")
    d.edge([(1395, 380), (1395, 410)], "client", flow=False)
    d.edge([(1540, 215), (1552, 215), (1552, 465), (1540, 465)], "client", flow=False)
    d.edge([(1250, 440), (1215, 440), (1215, 300), (1180, 300)], "django", "season", label_at=1)
    d.edge([(1250, 500), (1180, 500)], "django", "rain_mm")
    d.edge([(1180, 615), (1250, 615)], "client", "indicators")
    d.note(40, 755, ["Soil group from the Dutch texture words in the soil name (zand A · zavel/leem B · lichte klei C · klei/veen D); the most restrictive layer wins.",
                     "NEH 630: a water table within 60 cm makes a soil group D; drained land covers (urban fabric, industrial, roads, ports, airports) keep their texture letter.",
                     "BIS has no GHG/GLG under most built-up land (85 % of urban-fabric cells in Enschede) or water: nodata counts as not shallow; water/wetland CN = 100/98.",
                     "Only the season re-runs the spatial query; moving the rain slider re-evaluates the pure SCS functions."])
    d.legend([("external", "External source"), ("data", "Vector model / SQL"), ("raster", "Raster"), ("django", "Python"), ("client", "Dashboard")])
    return d


DIAGRAMS = [overview, apps, vector, raster, importer, signals, editing, infiltration]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    built = []
    for fn in DIAGRAMS:
        dg = fn()
        (OUT / f"{dg.name}.svg").write_text(dg.svg(), encoding="utf-8")
        built.append(dg)
        print("wrote", dg.name)
    return built


if __name__ == "__main__":
    main()
