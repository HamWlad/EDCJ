"""Kleine Hilfsfunktionen (Zeit, Formatierung)."""

import threading
from datetime import datetime, timedelta, timezone

_L = threading.local()


def set_lang(l):
    _L.v = "en" if l == "en" else "de"


def lang():
    return getattr(_L, "v", "de")


def deN(s):
    """Englisch formatierte Zahl (1,234.5) -> bei Sprache de: 1.234,5."""
    if lang() == "en":
        return s
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_cr(n, sign=False):
    s = deN(f"{int(round(n)):,}")
    if sign and n > 0:
        s = "+" + s
    return s + " Cr"


def fmt_dur(td):
    secs = int(td.total_seconds())
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def _nf(x, d=0):
    return deN(f"{x:,.{d}f}")
