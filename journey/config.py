"""Konfiguration, Journal-Suche und gemeinsame Einstellungen."""

import glob
import os

VERSION = "0.9.7.6"  # vor 1.0: Funktionsumfang waechst noch


# ---------------------------------------------------------------------------
# Wo liegt das Journal? (Linux: Steam/Proton, Flatpak-Steam, Lutris, Wine)
# ---------------------------------------------------------------------------
JOURNAL_SUBPATH = os.path.join("Saved Games", "Frontier Developments", "Elite Dangerous")
HOME = os.path.expanduser("~")

CANDIDATE_GLOBS = [
    f"{HOME}/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/{JOURNAL_SUBPATH}",
    f"{HOME}/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/{JOURNAL_SUBPATH}",
    f"{HOME}/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/{JOURNAL_SUBPATH}",
    f"{HOME}/.local/share/Steam/steamapps/compatdata/*/pfx/drive_c/users/steamuser/{JOURNAL_SUBPATH}",
    f"{HOME}/.local/share/lutris/runners/wine/*/{JOURNAL_SUBPATH}",
    f"{HOME}/Games/*/drive_c/users/*/{JOURNAL_SUBPATH}",
    f"{HOME}/.wine/drive_c/users/*/{JOURNAL_SUBPATH}",
    f"{HOME}/.local/share/min-ed-launcher/*/drive_c/users/*/{JOURNAL_SUBPATH}",
]


IS_WIN = os.name == "nt"
_GUID_SAVED_GAMES = "4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4"
_GUID_PICTURES = "33E28130-4E1E-4676-835A-98395C3BC3BB"


def known_folder(guid):
    """Windows: Pfad eines Benutzerordners (auch wenn er verschoben wurde, z.B. nach OneDrive). Sonst None."""
    if not IS_WIN:
        return None
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class _GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]
        g = uuid.UUID(guid)
        ref = _GUID(g.time_low, g.time_mid, g.time_hi_version, (ctypes.c_ubyte * 8).from_buffer_copy(g.bytes[8:]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(ref), 0, None, ctypes.byref(out)) != 0:
            return None
        path = out.value
        ctypes.windll.ole32.CoTaskMemFree(out)
        return path
    except Exception:
        return None


def windows_dirs(kind):
    """Kandidaten fuer 'Saved Games' bzw. 'Pictures' unter Windows (Systemordner, Benutzerprofil, OneDrive)."""
    names = {"saved": ("Saved Games", _GUID_SAVED_GAMES), "pics": ("Pictures", _GUID_PICTURES)}[kind]
    out = []
    kf = known_folder(names[1])
    if kf:
        out.append(kf)
    prof = os.environ.get("USERPROFILE") or HOME
    out.append(os.path.join(prof, names[0]))
    for env in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        od = os.environ.get(env)
        if od:
            out.append(os.path.join(od, names[0]))
    out.append(os.path.join(prof, "OneDrive", names[0]))
    seen, res = set(), []
    for d in out:
        if d.lower() not in seen:
            seen.add(d.lower())
            res.append(d)
    return res


def find_journal_dir(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("ED_JOURNAL_DIR")
    if env:
        return env
    found = []
    if IS_WIN:
        found.extend(p for p in (os.path.join(d, "Frontier Developments", "Elite Dangerous") for d in windows_dirs("saved")) if os.path.isdir(p))
    for pattern in CANDIDATE_GLOBS:
        found.extend(p for p in glob.glob(pattern) if os.path.isdir(p))
    if not found:
        return None
    # Ordner mit dem frischesten Journal gewinnt
    def newest_mtime(d):
        files = glob.glob(os.path.join(d, "Journal*.log"))
        return max((os.path.getmtime(f) for f in files), default=0)
    return max(found, key=newest_mtime)


def latest_journal(directory):
    files = glob.glob(os.path.join(directory, "Journal*.log"))
    return max(files, key=os.path.getmtime) if files else None

CONFIG = {"file": None, "dir": None, "window": 60, "log": None, "backfill": 0}


# ---------------------------------------------------------------------------
# Captain's Log: fortlaufende Markdown-Datei, wird nur angehaengt
# ---------------------------------------------------------------------------
# Portabel-Modus: Liegt neben edcj.py ein Ordner "data", liegen dort Captain's Log, Datenbank (market.db) und Einstellungen.
# Sonst wie bisher unter ~/.local/share/ed-lcars/.  Mit --log laesst sich beides uebersteuern.
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PORTABLE = os.path.join(PROJECT_DIR, "data")
_USERDATA = (os.path.join(os.environ.get("APPDATA") or HOME, "EDCJ") if IS_WIN else os.path.join(HOME, ".local", "share", "ed-lcars"))
DEFAULT_LOG = os.path.join(_PORTABLE if os.path.isdir(_PORTABLE) else _USERDATA, "captains_log.md")


def _journal_dir():
    return os.path.dirname(os.path.abspath(CONFIG["file"])) if CONFIG["file"] else find_journal_dir(CONFIG["dir"])
