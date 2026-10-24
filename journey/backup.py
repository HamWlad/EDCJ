"""Datensicherung: ZIP-Backup erstellen und einspielen."""

import io
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone

from . import config, database


def _backup_extra():
    """Dateien neben der Datenbank, die ins Backup gehoeren (Captain's Log, Einstellungen, Koerper-Cache, Zustand)."""
    base = config.CONFIG["log"]
    return [f for f in (base, base + ".settings.json", base + ".bodies.json", base + ".state.json") if os.path.isfile(f)]


def make_backup():
    """ZIP mit konsistentem Abzug der Datenbank (SQLite-Backup-API) plus Zusatzdateien. Gibt (bytes, name) zurueck."""
    tmpd = tempfile.mkdtemp(prefix="edbak_")
    try:
        snap = os.path.join(tmpd, "market.db")
        src = database._mdb()
        try:
            dst = sqlite3.connect(snap)
            src.backup(dst)
            dst.close()
        finally:
            src.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "market.db")
            for f in _backup_extra():
                z.write(f, os.path.basename(f))
            z.writestr("BACKUP.txt", "EDCJ Backup " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        return buf.getvalue(), "edcj_backup_" + datetime.now().strftime("%Y-%m-%d_%H%M") + ".zip"
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def restore_backup(data):
    """Backup einspielen. Der alte Stand wird vorher als ZIP neben die Datenbank gelegt. Gibt Statusdict zurueck."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return {"error": "Das ist keine gültige ZIP-Datei."}
    names = z.namelist()
    if "market.db" not in names:
        return {"error": "Im ZIP fehlt market.db – das ist kein EDCJ-Backup."}
    tmpd = tempfile.mkdtemp(prefix="edres_")
    try:
        cand = os.path.join(tmpd, "market.db")
        with open(cand, "wb") as fh:
            fh.write(z.read("market.db"))
        try:
            t = sqlite3.connect(cand)
            ok = t.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            tabs = {r[0] for r in t.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            t.close()
        except sqlite3.Error:
            return {"error": "Die Datenbank im Backup ist beschädigt."}
        if not ok or not {"station", "snap", "item"} <= tabs:
            return {"error": "Die Datenbank im Backup ist unvollständig oder beschädigt."}
        # Sicherung des aktuellen Stands
        old, oname = make_backup()
        bdir = os.path.dirname(os.path.abspath(config.CONFIG["log"]))
        with open(os.path.join(bdir, "vor_wiederherstellung_" + oname), "wb") as fh:
            fh.write(old)
        src = sqlite3.connect(cand)
        dst = database._mdb()
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
        base = os.path.basename(config.CONFIG["log"])
        allowed = {base, base + ".settings.json", base + ".bodies.json", base + ".state.json"}
        for n_ in names:
            if n_ in allowed:
                with open(os.path.join(bdir, n_), "wb") as fh:
                    fh.write(z.read(n_))
        return {"ok": True, "safety": "vor_wiederherstellung_" + oname, "files": [n_ for n_ in names if n_ in allowed]}
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)
