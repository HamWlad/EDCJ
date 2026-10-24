"""LAN-Freigabe (Tablet im Heimnetz): Zugangscode, Anmeldeseite, Adressen."""

import hashlib
import hmac
import json
import os
import random
import socket
import time

from . import config, settings

LOCAL = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
_FAILS = {}  # ip -> (anzahl, zeitpunkt)


def _read():
    try:
        with open(settings._settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(upd):
    d = _read()
    d.update(upd)
    p = settings._settings_path()
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(p + ".tmp", p)


def enabled():
    return bool(config.CONFIG.get("lan")) or bool(_read().get("lan"))


def code():
    c = _read().get("lan_code")
    if not (isinstance(c, str) and len(c) >= 4):
        c = "%06d" % random.SystemRandom().randrange(1000000)
        _write({"lan_code": c})
    return c


def token():
    return hmac.new(code().encode(), b"edcj-lan", hashlib.sha256).hexdigest()[:40]


def is_local(ip):
    return ip in LOCAL


def addresses(port):
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # sendet nichts, ermittelt nur die passende Netzwerkkarte
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return [f"http://{ip}:{port}/" for ip in ips if ip and not ip.startswith("127.")]


def authed(handler):
    for part in (handler.headers.get("Cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "edcj_auth" and hmac.compare_digest(v, token()):
            return True
    return False


def try_login(ip, given):
    n, t = _FAILS.get(ip, (0, 0))
    if n >= 5 and time.time() - t < 60:
        return None  # gesperrt
    if isinstance(given, str) and hmac.compare_digest(given.strip(), code()):
        _FAILS.pop(ip, None)
        return token()
    _FAILS[ip] = (n + 1 if time.time() - t < 60 else 1, time.time())
    time.sleep(0.8)
    return ""


def info(port):
    return {"on_now": bool(config.CONFIG.get("lan_active")), "setting": bool(_read().get("lan")),
            "code": code(), "urls": addresses(port), "port": port}


def set_state(on=None, new_code=None):
    upd = {}
    if on is not None:
        upd["lan"] = bool(on)
    if new_code == "":
        upd["lan_code"] = "%06d" % random.SystemRandom().randrange(1000000)
    elif isinstance(new_code, str) and 4 <= len(new_code) <= 32:
        upd["lan_code"] = new_code
    if upd:
        _write(upd)


LOGIN = """<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EDCJ – Anmeldung</title><style>
body{margin:0;background:#000;color:#ffcc99;font-family:'Segoe UI','DejaVu Sans',sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center}
.b{width:min(92vw,420px);border-left:14px solid #ff9900;padding:10px 24px}
h1{margin:0 0 6px;font-size:26px;letter-spacing:.08em;color:#ff9900}p{margin:4px 0 16px;font-size:18px}
input{width:100%;box-sizing:border-box;font-size:30px;padding:12px;background:#111;color:#ffcc99;border:2px solid #9999cc;border-radius:10px;letter-spacing:.2em;text-align:center}
button{margin-top:14px;width:100%;font-size:24px;padding:14px;background:#ff9900;color:#000;border:0;border-radius:24px;cursor:pointer}
#e{color:#ff5555;min-height:24px;margin-top:10px}</style></head><body><div class="b">
<h1>EDCJ</h1><p>Zugangscode eingeben. Er steht in den Settings von EDCJ am Rechner.</p>
<input id="c" type="password" inputmode="numeric" autocomplete="off" autofocus><button id="g">Anmelden</button><div id="e"></div></div>
<script>
async function go(){const r=await fetch('/login',{method:'POST',headers:{'X-EDCJ':'1'},body:document.getElementById('c').value});
 if(r.ok){location.reload()}else{document.getElementById('e').textContent=r.status==429?'Zu viele Versuche, bitte eine Minute warten.':'Code falsch.'}}
document.getElementById('g').onclick=go;document.getElementById('c').onkeydown=e=>{if(e.key==='Enter')go()};
</script></body></html>"""
