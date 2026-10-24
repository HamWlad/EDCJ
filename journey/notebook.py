"""Eigene Notizen zu Stationen und Systemen."""

import sqlite3
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import database


def notes_api(body=None):
    c = database._mdb()
    c.row_factory = sqlite3.Row
    try:
        if body:
            kind, name = str(body.get("kind", "")), str(body.get("name", "")).strip()[:200]
            txt = str(body.get("txt", "")).strip()[:2000]
            if kind not in ("station", "system") or not name:
                return {"error": "ungueltig"}
            if txt:
                c.execute("INSERT OR REPLACE INTO notes VALUES(?,?,?,?)", (kind, name, txt, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
            else:
                c.execute("DELETE FROM notes WHERE kind=? AND name=?", (kind, name))
            c.commit()
        notes = [dict(r) for r in c.execute("SELECT kind, name, txt, ts FROM notes ORDER BY kind, name COLLATE NOCASE")]
        stn = [r[0] for r in c.execute("SELECT DISTINCT name FROM stdb UNION SELECT DISTINCT name FROM station ORDER BY 1 COLLATE NOCASE")]
        sy = [r[0] for r in c.execute("SELECT system FROM syspos UNION SELECT DISTINCT system FROM station ORDER BY 1 COLLATE NOCASE")]
        return {"notes": notes, "stations": stn[:3000], "systems": sy[:5000]}
    finally:
        c.close()
