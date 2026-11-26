"""
NVM quarterly housing-market reports (PDF) -> housing.NVMMarketReport and
housing.NVMRegionMapping.

The PDFs are not downloaded here. NVM's terms (www.nvm.nl/special-pages/copyright
and /disclaimer) allow the site's content for non-commercial private use only and
reserve reproduction and redistribution, so a person fetches the PDFs from
https://www.nvm.nl/wonen/marktinformatie-wonen/ and puts them in `NVM_PDF_DIR`
(default `<MEDIA_ROOT>/nvm`); the catalog entry `nvm_market_reports` reads that
folder. robots.txt allows the pages but does not change the terms. Ask NVM for
written permission before the figures are redistributed (published tables,
shared databases).

Layout read (checked on "Marktoverzicht Nederland, 3e kwartaal 2026"): the page
footer "NVM Woningmarkt kwartaalcijfers <region> | <q>e kwartaal <year>" names
the region and the report quarter; each figure is a block whose header line
carries three period labels ("2025-3 2026-2 2026-3": same quarter last year,
previous quarter, report quarter) and whose rows are a dwelling type followed by
the three values (and, for most figures, the two % changes, which are ignored).
Numbers use Dutch notation ("10.314", "1,2%"). A line that does not match is
skipped, so an unfamiliar report yields no rows rather than wrong ones.
"""
import hashlib
import logging
import re
import unicodedata
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .console import say

logger = logging.getLogger(__name__)

PARSER_VERSION = "1"
MARKET_PAGE = "https://www.nvm.nl/wonen/marktinformatie-wonen/"
MAPPING_FILE_HINT = "gebiedsindeling"
DWELLING_TYPES = ("Tussenwoning", "Hoekwoning", "2-onder-1-kap", "Vrijstaand", "Appartement", "Totaal")

_NUMBER = r"-?\d[\d.]*(?:,\d+)?%?"
_PERIODS = re.compile(r"(\d{4})-([1-4])\s+(\d{4})-([1-4])\s+(\d{4})-([1-4])")
_ROW = re.compile(
    rf"(?<![\w-])({'|'.join(re.escape(t) for t in DWELLING_TYPES)})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})(?!\d)"
)
_FOOTER = re.compile(r"kwartaalcijfers\s+(.+?)\s*\|\s*([1-4])e kwartaal (\d{4})")

# header text (lower case) -> (model field, scale); order matters: "per m2" before the price.
_METRICS = (
    ("aantal transacties", "transactions", 1),
    ("transactieprijs per m2", "pricePerSqm_EUR", 1),
    ("transactieprijs", "medianPrice_EUR", 1000),     # NVM prints x 1 000 euro
    ("verkooptijd", "daysOnMarket", 1),
    ("vraag-verkoopprijsverschil", "askingGap_pct", 1),
    ("% boven vraagprijs", "aboveAsking_pct", 1),
)


def parse_number(token):
    """Dutch number ("10.314", "1,2%", "-0,1%") as a float; None when it is not one."""
    try:
        return float(token.rstrip("%").replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _metric(header_text):
    text = header_text.strip().lower()
    for prefix, field, scale in _METRICS:
        if text.startswith(prefix):
            return field, scale
    return None, None


def parse_text(pages):
    """
    Records from the text of a report's pages.

    Returns (region, (report_year, report_quarter), records); `region` is None
    without the footer line. A record is {"year", "quarter", "dwellingType",
    <field>: value ...}, merged over the figures of the PDF. Pure: no I/O.
    """
    region = report = None
    merged = {}
    field = scale = None
    periods = None
    for page in pages:
        for line in (page or "").splitlines():
            footer = _FOOTER.search(line)
            if footer and region is None:
                region, report = footer.group(1).strip(), (int(footer.group(3)), int(footer.group(2)))
            header = _PERIODS.search(line)
            if header:
                g = header.groups()
                periods = [(int(g[0]), int(g[1])), (int(g[2]), int(g[3])), (int(g[4]), int(g[5]))]
                field, scale = _metric(line[:header.start()])
                continue
            row = _ROW.search(line)
            if row and field and periods:
                for (year, quarter), token in zip(periods, row.groups()[1:]):
                    value = parse_number(token)
                    if value is None:
                        continue
                    record = merged.setdefault((year, quarter, row.group(1)), {})
                    record[field] = round(value * scale) if field in ("transactions", "medianPrice_EUR") else value * scale
    records = [{"year": y, "quarter": q, "dwellingType": t, **values} for (y, q, t), values in merged.items()]
    return region, report, records


def extract_pages(path):
    """Text of each page of a PDF (pdfplumber is imported here, not at startup)."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def extract_tables(path):
    """Rows of every table of a PDF."""
    import pdfplumber

    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                rows.extend(table)
    return rows


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest_report(path, source_url=MARKET_PAGE):
    """
    Store one report PDF. Returns (rows created, rows updated, rows kept because
    a newer report already holds the figure). A figure is only replaced by a
    report of the same or a later quarter.
    """
    from housing.models import NVMMarketReport
    from .batching import deferred_cascades

    path = Path(path)
    region, report, records = parse_text(extract_pages(path))
    if region is None or not records:
        return 0, 0, 0
    sha = sha256_of(path)
    created = updated = kept = 0
    with transaction.atomic(), deferred_cascades():
        for record in records:
            key = {"region": region, "year": record.pop("year"), "quarter": record.pop("quarter"),
                   "dwellingType": record.pop("dwellingType")}
            existing = NVMMarketReport.objects.filter(**key).first()
            if existing and (existing.reportYear, existing.reportQuarter) > report:
                kept += 1
                continue
            values = {**record, "reportYear": report[0], "reportQuarter": report[1], "source_url": source_url,
                      "source_file": path.name, "pdf_sha256": sha, "parser_version": PARSER_VERSION}
            if existing:
                for name, value in values.items():
                    setattr(existing, name, value)
                existing.save()
                updated += 1
            else:
                NVMMarketReport.objects.create(**key, **values)
                created += 1
    return created, updated, kept


# ── COROP region -> municipalities ───────────────────────────────────

def _unwrap(text):
    """A table cell broken over lines: 'Hendrik-Ido-\\nAmbacht' -> 'Hendrik-Ido-Ambacht'."""
    return " ".join(re.sub(r"-\n", "-", text or "").split())


def _fold(name):
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold().strip()


def parse_region_rows(rows):
    """[(number, region, [municipality names])] from the rows of NVM's COROP table (header and noise skipped)."""
    result = []
    for row in rows:
        if not row or len(row) < 3 or not (row[0] or "").strip().isdigit():
            continue
        names = [n.strip() for n in _unwrap(row[2]).split(",") if n.strip()]
        result.append((int(row[0]), _unwrap(row[1]), names))
    return result


def ingest_region_mapping(path):
    """
    Store the NVM region of every municipality of the list that is a stored City.
    Returns (rows written, names of the list that match no stored City).
    """
    from administrative.models import City
    from housing.models import NVMRegionMapping

    cities = {_fold(c.cityName): c for c in City.objects.all()}
    entries = parse_region_rows(extract_tables(path))
    written, unmatched = 0, []
    with transaction.atomic():
        for number, region, names in entries:
            for name in names:
                city = cities.get(_fold(name))
                if city is None:
                    unmatched.append(name)
                    continue
                NVMRegionMapping.objects.update_or_create(
                    city=city, defaults={"region": region, "regionNumber": number, "source": Path(path).name})
                written += 1
    return written, unmatched


# ── catalog entry ────────────────────────────────────────────────────

def pdf_dir():
    return Path(getattr(settings, "NVM_PDF_DIR", None) or Path(settings.MEDIA_ROOT) / "nvm")


def fetch(dataset, bbox=None):
    """Read every PDF of `pdf_dir()`: the region list first, then the market reports not read yet."""
    from housing.models import NVMMarketReport
    from .external_data import ImportResult

    folder = pdf_dir()
    files = sorted(folder.glob("*.pdf")) if folder.is_dir() else []
    if not files:
        return ImportResult(
            "error",
            f"No NVM PDF found in {folder}. Download the quarterly reports yourself from {MARKET_PAGE} "
            "(NVM's terms allow non-commercial private use only) and put them there.")

    created = updated = 0
    notes = []
    for path in sorted(files, key=lambda p: (MAPPING_FILE_HINT not in p.name.lower(), p.name)):
        if MAPPING_FILE_HINT in path.name.lower():
            written, unmatched = ingest_region_mapping(path)
            say("nvm", f"{path.name}: {written} municipality -> region row(s)")
            notes.append(f"{path.name}: {written} municipalities mapped"
                         + (f", {len(unmatched)} names without a stored city" if unmatched else ""))
            continue
        sha = sha256_of(path)
        if NVMMarketReport.objects.filter(pdf_sha256=sha, parser_version=PARSER_VERSION).exists():
            say("nvm", f"{path.name}: already read, skipped")
            continue
        new, changed, kept = ingest_report(path, dataset.get("params", {}).get("source_page", MARKET_PAGE))
        say("nvm", f"{path.name}: {new} new, {changed} updated, {kept} kept")
        created += new
        updated += changed
        if not (new or changed or kept):
            notes.append(f"{path.name}: no market figures recognised")
    return ImportResult("success", f"Read {len(files)} NVM PDF(s): figures created {created}, updated {updated}. "
                                   + "; ".join(notes), created, updated)
