"""SQLite-Datenbank (market.db): Schema und Verbindung."""

import os
import sqlite3
import zlib

from . import config


# ---------------------------------------------------------------------------
# Markt: Market.json -> SQLite (market.db neben dem Captain's Log)
# ---------------------------------------------------------------------------
MK = {"mt": 0}
# Zuletzt bekannter Eintrag je Station und Ware (nach Zeitstempel, nicht nach Einfuegereihenfolge) - fuer die Suche "wo war der Preis zuletzt"
MK_LATEST = """FROM item i JOIN snap s ON s.id = i.snap_id JOIN station st ON st.market_id = s.market_id
 WHERE i.snap_id = (SELECT s2.id FROM snap s2 JOIN item i2 ON i2.snap_id = s2.id
                    WHERE s2.market_id = s.market_id AND i2.name = i.name ORDER BY s2.ts DESC, s2.id DESC LIMIT 1)"""
# Aktueller Stand: nur der juengste Marktstand der Station zaehlt. Fehlt eine Ware dort, ist sie dort nicht handelbar.
MK_CURRENT = """FROM item i JOIN snap s ON s.id = i.snap_id JOIN station st ON st.market_id = s.market_id
 WHERE s.id = (SELECT s2.id FROM snap s2 WHERE s2.market_id = s.market_id ORDER BY s2.ts DESC, s2.id DESC LIMIT 1)"""
MK_COLS = "i.name, i.cat, i.buy, i.sell, i.mean, i.stock, i.demand, s.market_id, s.seen, st.name AS station, st.system, st.type"


def _mdb():
    path = os.path.join(os.path.dirname(os.path.abspath(config.CONFIG["log"])), "market.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript("""PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS station(market_id INTEGER PRIMARY KEY, name TEXT, system TEXT, type TEXT, last_ts TEXT);
        CREATE TABLE IF NOT EXISTS snap(id INTEGER PRIMARY KEY AUTOINCREMENT, market_id INTEGER, ts TEXT, seen TEXT, hash TEXT);
        CREATE TABLE IF NOT EXISTS item(snap_id INTEGER, cid INTEGER, name TEXT, cat TEXT, buy INTEGER, sell INTEGER,
                                        mean INTEGER, stock INTEGER, demand INTEGER, sb INTEGER, db INTEGER);
        CREATE INDEX IF NOT EXISTS ix_item_snap ON item(snap_id);
        CREATE INDEX IF NOT EXISTS ix_item_name ON item(name);
        CREATE INDEX IF NOT EXISTS ix_snap_m ON snap(market_id, ts);
        CREATE TABLE IF NOT EXISTS fac(addr INTEGER, system TEXT, ts TEXT, name TEXT, inf REAL, state TEXT, active TEXT,
                                       gov TEXT, rep REAL, ctrl INTEGER, PRIMARY KEY(addr, ts, name));
        CREATE INDEX IF NOT EXISTS ix_fac_sys ON fac(system, ts);
        CREATE TABLE IF NOT EXISTS jstate(name TEXT PRIMARY KEY, off INTEGER);
        CREATE TABLE IF NOT EXISTS ce(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, file TEXT, pos INTEGER, kind TEXT, sys TEXT,
                                      ship TEXT, k1 TEXT, k2 TEXT, k3 TEXT, x TEXT, y TEXT, n1 REAL, n2 REAL, n3 REAL,
                                      UNIQUE(file, pos, kind, k1, k2));
        CREATE INDEX IF NOT EXISTS ix_ce_kind ON ce(kind, ts);
        CREATE TABLE IF NOT EXISTS jc(name TEXT PRIMARY KEY, off INTEGER, sys TEXT, ship TEXT, station TEXT, zone TEXT,
                                      first TEXT, last TEXT, rank TEXT);
        CREATE TABLE IF NOT EXISTS snapkv(k TEXT PRIMARY KEY, ts TEXT, js TEXT);
        CREATE TABLE IF NOT EXISTS wealth(ts TEXT, src TEXT, v REAL, PRIMARY KEY(ts, src));
        CREATE TABLE IF NOT EXISTS act(b TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS modelog(ts TEXT PRIMARY KEY, mode TEXT);
        CREATE TABLE IF NOT EXISTS stdb(system TEXT, name TEXT, market_id INTEGER, type TEXT, faction TEXT, gov TEXT, eco TEXT,
                                        dist REAL, via TEXT, first TEXT, last TEXT, PRIMARY KEY(system, name));
        CREATE TABLE IF NOT EXISTS pads(market_id INTEGER PRIMARY KEY, name TEXT, system TEXT, s INTEGER, m INTEGER, l INTEGER, ts TEXT);
        CREATE TABLE IF NOT EXISTS hotx(ring TEXT, mineral TEXT, ts TEXT, PRIMARY KEY(ring, mineral));
        CREATE TABLE IF NOT EXISTS notes(kind TEXT, name TEXT, txt TEXT, ts TEXT, PRIMARY KEY(kind, name));
        CREATE TABLE IF NOT EXISTS lm(id TEXT PRIMARY KEY, scope TEXT, period TEXT, created TEXT, ends TEXT, status TEXT, done_ts TEXT,
                                      dp INTEGER, spec TEXT, prog TEXT);
        CREATE TABLE IF NOT EXISTS colonies(system TEXT PRIMARY KEY, a INTEGER, amax INTEGER, b INTEGER, bmax INTEGER, build INTEGER, note TEXT);
        CREATE TABLE IF NOT EXISTS ckstock(ware TEXT PRIMARY KEY, base REAL, since TEXT);
        CREATE TABLE IF NOT EXISTS syspos(system TEXT PRIMARY KEY, x REAL, y REAL, z REAL);
        CREATE TABLE IF NOT EXISTS modst(market_id INTEGER, kind TEXT, name TEXT, system TEXT, ts TEXT, PRIMARY KEY(market_id, kind));
        CREATE TABLE IF NOT EXISTS gear(market_id INTEGER, kind TEXT, iid INTEGER, code TEXT, label TEXT, cat TEXT, cls TEXT,
                                        price INTEGER, merc INTEGER, PRIMARY KEY(market_id, kind, iid));""")
    _migrate_old_mods(c)
    return c


def _migrate_old_mods(c):
    """Aeltere Versionen speicherten Ausruestung in der Tabelle 'mods'. Diese Daten werden einmalig in 'gear' uebernommen
    (nur fuer Stationen, zu denen 'gear' noch nichts hat), danach heisst die alte Tabelle 'mods_legacy'."""
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mods'").fetchone():
        return
    rows = c.execute("""SELECT market_id, kind, code, label, cat, cls, price FROM mods m
                        WHERE NOT EXISTS (SELECT 1 FROM gear g WHERE g.market_id=m.market_id AND g.kind=m.kind)""").fetchall()
    for r in rows:
        iid = -(zlib.crc32(str(r[2]).encode("utf-8")) % 2147483647 + 1)
        c.execute("INSERT OR IGNORE INTO gear VALUES(?,?,?,?,?,?,?,?,0)", (r[0], r[1], iid, r[2], r[3], r[4], r[5], r[6] or 0))
    c.execute("ALTER TABLE mods RENAME TO mods_legacy")
    c.commit()
