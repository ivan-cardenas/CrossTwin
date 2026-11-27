"""
DNB MFI interest rate statistics -> housing.MortgageRate (catalog entry DNB_MORTGAGE_RATE).

Source: the DNB statistics export "MFI household deposits and loans, interest rates (Month)" (JSON, table
5_2_7_1_BVR): `labels` = BalancesheetSide, Instrument, Flowtype, MaturityOriginal, InitialRateFixation, Period
(ms since the epoch), waarde (% per year); `data` = one list per observation. Only the loans for house
purchase are stored (instruments starting "Loans for house purchasing"); consumer credit and deposits are not.
The file is read from the path given by the `DNB_MFI_RATES_FILE` setting (.env), or passed to `load_file`.
Labels are stored without their trailing spaces and footnote asterisks.
"""
import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.db import transaction

from .console import say

logger = logging.getLogger(__name__)

HOUSING_PREFIX = "Loans for house purchasing"
BATCH = 1000


def _result(status, message, created=0, updated=0):
    from .external_data import ImportResult

    return ImportResult(status, message, created, updated)


def clean(label):
    """A DNB label without its trailing spaces and footnote asterisk."""
    return str(label).replace("*", "").strip()


def parse(payload):
    """
    [{year, month, instrument, flowType, maturity, rateFixation, ratePct}] of the loans for house purchase in the
    DNB export `payload`. Observations without a value are skipped.
    """
    rows = []
    for _side, instrument, flow, maturity, fixation, period_ms, value in payload.get("data", []):
        instrument = clean(instrument)
        if not instrument.startswith(HOUSING_PREFIX) or value is None:
            continue
        when = datetime.fromtimestamp(period_ms / 1000, tz=timezone.utc)
        rows.append({"year": when.year, "month": when.month, "instrument": instrument, "flowType": clean(flow),
                     "maturity": clean(maturity), "rateFixation": clean(fixation), "ratePct": float(value)})
    return rows


def load_rows(rows):
    """Upsert the parsed rows; (created, updated)."""
    from housing.models import MortgageRate

    key = lambda r: (r["year"], r["month"], r["instrument"], r["flowType"], r["maturity"], r["rateFixation"])
    created = updated = 0
    with transaction.atomic():
        existing = {key(m.__dict__): m for m in MortgageRate.objects.all()}
        new, changed = [], []
        for r in rows:
            row = existing.get(key(r))
            if row is None:
                new.append(MortgageRate(**r))
            elif row.ratePct != r["ratePct"]:
                row.ratePct = r["ratePct"]
                changed.append(row)
        MortgageRate.objects.bulk_create(new, batch_size=BATCH)
        if changed:
            MortgageRate.objects.bulk_update(changed, ["ratePct"], batch_size=BATCH)
        created, updated = len(new), len(changed)
    return created, updated


def load_file(path):
    """Read a DNB export and store its housing rates; (created, updated, rows read)."""
    with open(path, encoding="utf-8-sig") as handle:
        rows = parse(json.load(handle))
    created, updated = load_rows(rows)
    return created, updated, len(rows)


def fetch(dataset, bbox=None):
    """Import the housing interest rates of the DNB export named by the DNB_MFI_RATES_FILE setting."""
    path = getattr(settings, "DNB_MFI_RATES_FILE", "") or ""
    if not path:
        return _result("error", "Set DNB_MFI_RATES_FILE in .env to the downloaded DNB export "
                                "('MFI household deposits and loans, interest rates (Month)', JSON).")
    say("dnb", f"Reading {path} ...")
    try:
        created, updated, read = load_file(path)
    except (OSError, ValueError) as exc:
        return _result("error", f"Could not read the DNB file: {exc}")
    if not read:
        return _result("error", "The DNB file holds no loans for house purchase.")
    return _result("success", f"Imported {read} monthly housing interest rate(s) from DNB: created {created}, "
                              f"updated {updated}.", created, updated)
