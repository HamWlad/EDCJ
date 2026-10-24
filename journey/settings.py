"""Einstellungen (Reiter, Thema) der Oberfläche."""

import json
import os

from . import config


SETTINGS_TABS = {"cockpit", "maint", "stats", "system", "bodies", "all", "kampf", "mining", "missions", "carrier", "bgs", "bio", "gaps", "replay", "akte", "lmis", "lmil", "karriere", "bilanz", "flotte", "market", "gear", "ana", "sana",
                 "ware", "notes", "map", "hot", "log", "search", "shots", "profil", "off"}
SETTINGS_THEMES = {"startrek", "elite", "elite84", "mono"}


def _settings_path():
    return config.CONFIG["log"] + ".settings.json"


def load_raw():
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load_settings():
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    hid = [t for t in d.get("hidden", []) if t in SETTINGS_TABS] if isinstance(d.get("hidden"), list) else []
    return {"hidden": hid, "theme": d.get("theme") if d.get("theme") in SETTINGS_THEMES else "startrek",
            "shots_dir": d.get("shots_dir") if isinstance(d.get("shots_dir"), str) else ""}


def save_settings(d):
    old = load_raw()
    out = {"hidden": sorted({t for t in (d.get("hidden") or []) if t in SETTINGS_TABS}),
           "theme": d.get("theme") if d.get("theme") in SETTINGS_THEMES else "startrek",
           "shots_dir": (d["shots_dir"] if isinstance(d.get("shots_dir"), str) else "") if "shots_dir" in d else load_settings()["shots_dir"]}
    for k in ("lan", "lan_code"):  # LAN-Einstellungen bleiben beim Speichern der Oberflaeche erhalten
        if k in old:
            out[k] = old[k]
    tmp = _settings_path() + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(tmp)), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f)
    os.replace(tmp, _settings_path())
    return out
