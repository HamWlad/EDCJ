"""Zwischenablage des Rechners setzen (fuer Klicks vom Tablet aus)."""

import os
import shutil
import subprocess
import sys

from . import config


def _tool():
    if config.IS_WIN:
        return ["clip"], "utf-16"
    if sys.platform == "darwin":
        return ["pbcopy"], "utf-8"
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        return ["wl-copy"], "utf-8"
    if shutil.which("xclip") and os.environ.get("DISPLAY"):
        return ["xclip", "-selection", "clipboard"], "utf-8"
    if shutil.which("xsel") and os.environ.get("DISPLAY"):
        return ["xsel", "-ib"], "utf-8"
    if shutil.which("wl-copy"):
        return ["wl-copy"], "utf-8"
    return None, None


def available():
    cmd, _ = _tool()
    return cmd[0] if cmd else None


def set_clip(text):
    text = "".join(ch for ch in str(text) if ch >= " ")[:120].strip()
    if not text:
        return {"ok": False, "error": "leer"}
    cmd, enc = _tool()
    if not cmd:
        return {"ok": False, "error": "Kein Zwischenablage-Werkzeug gefunden. Auf Linux Wayland: wl-clipboard installieren (z. B. sudo pacman -S wl-clipboard), auf X11: xclip."}
    try:
        subprocess.run(cmd, input=text.encode(enc), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": f"{cmd[0]} fehlgeschlagen: {exc}"}
    return {"ok": True, "text": text}
