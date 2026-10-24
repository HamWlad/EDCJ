"""Screenshot-Galerie: liest die Screenshot-Ereignisse des Journals, kopiert die Bilder nach data/screenshots/
und stellt sie samt Ort, Notiz, Stern und Schlagworten bereit. Alles lokal, nichts geht ins Netz."""

import glob
import json
import os
import re
import shutil
import struct
import time
import zlib

from . import config, database, settings

THUMB_W = 480
_RETRY = {}          # id -> Zeitpunkt des letzten Suchversuchs (nur im Speicher)
_RETRY_SECS = 300
IMG_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".bmp": "image/bmp"}


def shots_dir():
    return os.path.join(os.path.dirname(os.path.abspath(config.CONFIG["log"])), "screenshots")


def _thumb_dir():
    return os.path.join(shots_dir(), "thumbs")


def _schema(c):
    c.executescript("""CREATE TABLE IF NOT EXISTS shots(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, jfile TEXT, fname TEXT UNIQUE,
        sys TEXT, body TEXT, lat REAL, lon REAL, alt REAL, hdg REAL, w INTEGER, h INTEGER,
        stored TEXT DEFAULT '', thumb TEXT DEFAULT '', fav INTEGER DEFAULT 0, tags TEXT DEFAULT '', note TEXT DEFAULT '',
        hidden INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS ix_shots_ts ON shots(ts);""")


def _db():
    c = database._mdb()
    _schema(c)
    return c


# ---------------------------------------------------------------------------
# Bilder finden und kopieren
# ---------------------------------------------------------------------------
def source_dirs():
    """Moegliche Ordner, in denen das Spiel die Bilder ablegt (Einstellung zuerst, dann Proton/Wine und ~/Pictures)."""
    out = []
    custom = (settings.load_settings().get("shots_dir") or "").strip()
    if custom:
        out.append(os.path.expanduser(custom))
    jd = config._journal_dir()
    if jd:
        # .../users/<name>/Saved Games/Frontier Developments/Elite Dangerous -> .../users/<name>/Pictures/Frontier Developments/Elite Dangerous
        norm = os.path.abspath(jd)
        marker = os.sep + "Saved Games" + os.sep
        if marker in norm:
            out.append(norm.replace(marker, os.sep + "Pictures" + os.sep, 1))
    out.append(os.path.join(config.HOME, "Pictures", "Frontier Developments", "Elite Dangerous"))
    if config.IS_WIN:
        out.extend(os.path.join(d, "Frontier Developments", "Elite Dangerous") for d in config.windows_dirs("pics"))
    for pat in (f"{config.HOME}/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Pictures/Frontier Developments/Elite Dangerous",
                f"{config.HOME}/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Pictures/Frontier Developments/Elite Dangerous",
                f"{config.HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Pictures/Frontier Developments/Elite Dangerous"):
        out.append(pat)
    seen, res = set(), []
    for d in out:
        if d not in seen and os.path.isdir(d):
            seen.add(d)
            res.append(d)
    return res


def _find_source(fname):
    base = re.split(r"[\\/]", fname)[-1]
    if not base:
        return None
    for d in source_dirs():
        p = os.path.join(d, base)
        if os.path.isfile(p):
            return p
        hit = glob.glob(os.path.join(glob.escape(d), "**", glob.escape(base)), recursive=True)
        if hit:
            return hit[0]
    return None


def _safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:80] or "shot"


def make_thumb_bmp(src, dst):
    """Verkleinerte PNG-Vorschau aus einer unkomprimierten BMP (24/32 Bit), nur mit Standardbibliothek. True bei Erfolg."""
    try:
        with open(src, "rb") as f:
            hdr = f.read(54)
            if hdr[:2] != b"BM":
                return False
            off = struct.unpack_from("<I", hdr, 10)[0]
            dib, w, h, planes, bpp, comp = struct.unpack_from("<IiiHHI", hdr, 14)
            if dib < 40 or bpp not in (24, 32) or comp not in (0, 3) or w <= 0 or h == 0:
                return False
            top_down = h < 0
            h = abs(h)
            bp = bpp // 8
            stride = ((w * bpp + 31) // 32) * 4
            step = max(1, w // THUMB_W)
            tw, th = (w + step - 1) // step, (h + step - 1) // step
            raw = bytearray()
            for ty in range(th):
                sy = ty * step
                row_i = sy if top_down else (h - 1 - sy)
                f.seek(off + row_i * stride)
                row = f.read(w * bp)
                if len(row) < w * bp:
                    return False
                px = bytearray(tw * 3)
                px[0::3] = row[2::bp * step][:tw]   # R
                px[1::3] = row[1::bp * step][:tw]   # G
                px[2::3] = row[0::bp * step][:tw]   # B
                raw += b"\x00" + px
    except (OSError, struct.error):
        return False

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", tw, th, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(png)
    return True


def _store(c, row):
    """Bild suchen, nach data/screenshots/ kopieren, ggf. Vorschau anlegen. Gibt True zurueck, wenn die Datei gefunden wurde."""
    src = _find_source(row["fname"])
    if not src:
        return False
    ext = os.path.splitext(src)[1].lower()
    if ext not in IMG_TYPES:
        return False
    stamp = re.sub(r"[^0-9]", "", row["ts"] or "")[:14] or "0"
    name = f"{stamp}_{_safe(os.path.basename(src))}"
    os.makedirs(shots_dir(), exist_ok=True)
    dst = os.path.join(shots_dir(), name)
    if not os.path.isfile(dst):
        shutil.copy2(src, dst)
    thumb = ""
    if ext == ".bmp":
        tn = os.path.splitext(name)[0] + ".png"
        if os.path.isfile(os.path.join(_thumb_dir(), tn)) or make_thumb_bmp(dst, os.path.join(_thumb_dir(), tn)):
            thumb = tn
    c.execute("UPDATE shots SET stored=?, thumb=? WHERE id=?", (name, thumb, row["id"]))
    return True


# ---------------------------------------------------------------------------
# Journal einlesen
# ---------------------------------------------------------------------------
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def scan():
    """Neue Screenshot-Ereignisse aus allen Journalen aufnehmen und fehlende Bilder (erneut) suchen. Gibt die Zahl neuer Bilder zurueck."""
    jd = config._journal_dir()
    if not jd or not os.path.isdir(jd):
        return 0
    files = [config.CONFIG["file"]] if config.CONFIG["file"] else sorted(glob.glob(os.path.join(jd, "Journal*.log")), key=os.path.getmtime)
    c = _db()
    new = 0
    try:
        r = c.execute("SELECT js FROM snapkv WHERE k='shots_off'").fetchone()
        offs = json.loads(r["js"]) if r else {}
        dirty = False
        for f in files:
            name = os.path.basename(f)
            try:
                size = os.path.getsize(f)
            except OSError:
                continue
            o = offs.get(name, 0)
            if size <= o:
                continue
            with open(f, "rb") as fh:
                fh.seek(o)
                data = fh.read(size - o)
            cut = data.rfind(b"\n")
            if cut < 0:
                continue
            offs[name] = o + cut + 1
            dirty = True
            for line in data[:cut + 1].splitlines():
                if b'"Screenshot"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("event") != "Screenshot" or not ev.get("Filename"):
                    continue
                cur = c.execute("""INSERT OR IGNORE INTO shots(ts, jfile, fname, sys, body, lat, lon, alt, hdg, w, h)
                                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                                (ev.get("timestamp", ""), name, ev["Filename"], ev.get("System", ""), ev.get("Body", ""),
                                 _num(ev.get("Latitude")), _num(ev.get("Longitude")), _num(ev.get("Altitude")), _num(ev.get("Heading")),
                                 ev.get("Width"), ev.get("Height")))
                new += cur.rowcount
        if dirty:
            c.execute("INSERT OR REPLACE INTO snapkv VALUES('shots_off', ?, ?)", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), json.dumps(offs)))
        now = time.time()
        for row in c.execute("SELECT id, ts, fname FROM shots WHERE stored='' AND hidden=0").fetchall():
            if now - _RETRY.get(row["id"], 0) < _RETRY_SECS:
                continue
            _RETRY[row["id"]] = now
            try:
                _store(c, row)
            except OSError:
                pass
        # fehlende Vorschauen nachziehen (z.B. nach Update)
        c.commit()
    finally:
        c.close()
    return new


def rescan_missing():
    _RETRY.clear()
    return scan()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def _row(r, visits):
    d = dict(r)
    d["visits"] = visits.get(d["sys"], 0)
    d["has_file"] = bool(d["stored"])
    d["src"] = ("/api/shot?id=%d" % d["id"]) if d["stored"] else ""
    d["tsrc"] = ("/api/shot?id=%d&t=1" % d["id"]) if d["stored"] else ""
    return d


def gallery_api(p):
    op = p.get("op", "list")
    c = _db()
    try:
        visits = {}
        try:
            visits = {r["k1"]: r["n"] for r in c.execute("SELECT k1, COUNT(*) AS n FROM ce WHERE kind='jump' GROUP BY k1")}
        except Exception:
            pass
        if op == "list":
            where, args = ["hidden=0"], []
            if p.get("fav") == "1":
                where.append("fav=1")
            if p.get("found") == "1":
                where.append("stored!=''")
            for t in (p.get("q") or "").lower().split()[:6]:
                where.append("lower(sys||' '||body||' '||tags||' '||note) LIKE ?")
                args.append("%" + t + "%")
            rows = c.execute("SELECT * FROM shots WHERE " + " AND ".join(where) + " ORDER BY ts DESC, id DESC LIMIT 1500", args).fetchall()
            tot = c.execute("SELECT COUNT(*) AS n, SUM(stored!='') AS f, SUM(fav) AS s FROM shots WHERE hidden=0").fetchone()
            size = 0
            try:
                size = sum(os.path.getsize(os.path.join(shots_dir(), n)) for n in os.listdir(shots_dir()) if os.path.isfile(os.path.join(shots_dir(), n)))
            except OSError:
                pass
            tags = {}
            for r in c.execute("SELECT tags FROM shots WHERE hidden=0 AND tags!=''"):
                for t in r["tags"].split(","):
                    t = t.strip()
                    if t:
                        tags[t] = tags.get(t, 0) + 1
            return {"rows": [_row(r, visits) for r in rows], "total": tot["n"] or 0, "found": tot["f"] or 0, "favs": tot["s"] or 0,
                    "bytes": size, "dir": shots_dir(), "sources": source_dirs(), "custom": settings.load_settings().get("shots_dir", ""),
                    "tags": sorted(tags.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:40]}
        return {"error": "unbekannte Abfrage"}
    finally:
        c.close()


def gallery_post(d):
    act, c = d.get("act", ""), _db()
    try:
        if act == "rescan":
            n = rescan_missing()
            return {"ok": True, "new": n}
        if act == "dir":
            s = settings.load_settings()
            s["shots_dir"] = str(d.get("dir", ""))[:500].strip()
            settings.save_settings(s)
            return {"ok": True, "n": rescan_missing()}
        try:
            sid = int(d.get("id"))
        except (TypeError, ValueError):
            return {"error": "keine ID"}
        row = c.execute("SELECT * FROM shots WHERE id=?", (sid,)).fetchone()
        if not row:
            return {"error": "unbekannt"}
        if act == "fav":
            c.execute("UPDATE shots SET fav=? WHERE id=?", (1 if d.get("v") else 0, sid))
        elif act == "meta":
            tags = ", ".join(sorted({t.strip()[:30] for t in str(d.get("tags", "")).split(",") if t.strip()}, key=str.lower))[:300]
            c.execute("UPDATE shots SET note=?, tags=? WHERE id=?", (str(d.get("note", ""))[:2000], tags, sid))
        elif act == "delete":
            # Eintrag bleibt (verborgen), damit das Journal ihn nicht erneut anlegt; die kopierte Datei wird geloescht
            for sub, nm in ((shots_dir(), row["stored"]), (_thumb_dir(), row["thumb"])):
                if nm:
                    try:
                        os.remove(os.path.join(sub, nm))
                    except OSError:
                        pass
            c.execute("UPDATE shots SET hidden=1, stored='', thumb='' WHERE id=?", (sid,))
        else:
            return {"error": "unbekannte Aktion"}
        c.commit()
        return {"ok": True}
    finally:
        c.close()


def image_bytes(sid, thumb):
    """(Inhalt, Content-Type) der kopierten Datei oder None. Nur Dateien, die in der Datenbank stehen und im Bilderordner liegen."""
    c = _db()
    try:
        row = c.execute("SELECT stored, thumb FROM shots WHERE id=? AND hidden=0", (sid,)).fetchone()
    finally:
        c.close()
    if not row or not row["stored"]:
        return None
    name, base = row["stored"], shots_dir()
    path = os.path.join(base, name)
    if thumb and row["thumb"]:
        name, base = row["thumb"], _thumb_dir()
        path = os.path.join(base, name)
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(base) + os.sep) or not os.path.isfile(real):
        return None
    with open(real, "rb") as f:
        return f.read(), IMG_TYPES.get(os.path.splitext(real)[1].lower(), "application/octet-stream")
