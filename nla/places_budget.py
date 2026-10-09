"""Monthly budget for billable Google Places calls.

Google gives 1,000 free Text Search Enterprise calls a month; asking for phone, rating and website
puts our requests in that tier. Every call goes through spend(), which keeps a per-month count in
data/.places_usage.json and refuses calls past NLA_PLACES_MONTHLY_CAP (default 800, leaving margin
for manual tests such as a curl check, which this counter can't see).
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib

USAGE = pathlib.Path(__file__).resolve().parent.parent / "data" / ".places_usage.json"


class BudgetExceeded(RuntimeError):
    pass


def cap() -> int:
    return int(os.getenv("NLA_PLACES_MONTHLY_CAP", "800"))


def _month() -> str:
    return datetime.date.today().strftime("%Y-%m")


def _load() -> dict:
    try:
        return json.loads(USAGE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def used(month: str | None = None) -> int:
    return _load().get(month or _month(), 0)


def remaining() -> int:
    return max(0, cap() - used())


def spend(n: int = 1) -> int:
    """Record n calls about to be made, or raise BudgetExceeded without recording anything."""
    usage, month = _load(), _month()
    now = usage.get(month, 0)
    if now + n > cap():
        raise BudgetExceeded(f"Google Places monthly cap reached: {now}/{cap()} calls used in {month}")
    usage[month] = now + n
    USAGE.write_text(json.dumps(usage, indent=1))
    return usage[month]
