"""Grobe Wertschaetzung von Erkundungsdaten nach der bekannten Community-Formel.

Das Journal nennt keinen Wert je Koerper. Die Zahlen hier sind eine Naeherung (Formel und k-Werte aus Spielerforschung, Forum-Thread
'Exploration value formulae'); echte Auszahlungen weichen ab. Deshalb wird die Schaetzung gegen die echten Verkaeufe aus dem Journal geprueft.
"""

import math

Q = 0.56591828
# Klasse -> (k, zusaetzliches k fuer Terraformbar). 'immer' = Bonus gilt bei dieser Klasse stets (erdaehnliche Welt)
K_PLANET = {
    "metal rich body": (21790, 0), "high metal content body": (9654, 100677), "sudarsky class ii gas giant": (9654, 100677),
    "sudarsky class i gas giant": (1656, 0), "ammonia world": (96932, 0), "water world": (64831, 116295),
    "earthlike body": (64831, 116295), "rocky body": (300, 93328),
}
K_GAS_OTHER = 1656
K_DEFAULT = 300


def _base(k, mass):
    return k + k * Q * (max(mass, 0.0) ** 0.2)


def body_value(cls, mass, terra=False, first=False, mapped=False, first_map=False, eff=False):
    """Geschaetzter Verkaufswert eines Koerpers in Cr. cls = Klassenname aus dem Scan ('Stern N' fuer Sterne)."""
    c = (cls or "").lower()
    if c.startswith("stern "):
        t = c[6:].strip().upper()
        k = 22628 if t.startswith("N") or t.startswith("H") else 14057 if t.startswith("D") else 1200
        v = math.ceil(k + (mass or 0) * k / 66.25)
        mult = 1.0
        if mapped:
            mult = 3.699622554 if (first and first_map) else 8.0956 if first_map else 3.3333333333
            mult *= 1.25 if eff else 1.0
        v = v * mult
        return int(round(v * (2.6 if first else 1.0)))
    k, kt = K_PLANET.get(c, (K_GAS_OTHER if "gas giant" in c else K_DEFAULT, 0))
    v = _base(k, mass)
    if kt and (terra or c == "earthlike body"):
        v += _base(kt, mass)
    mult = 1.0
    if mapped:
        mult = 3.699622554 if (first and first_map) else 8.0956 if first_map else 3.3333333333
        mult *= 1.25 if eff else 1.0
    v = max(500, v * mult)
    return int(round(v * (2.6 if first else 1.0)))


def special(cls, terra, landable, grav, rings, atm):
    """Besonderheiten als Textliste (nur Fakten aus dem Scan)."""
    c = (cls or "").lower()
    t = []
    names = {"earthlike body": "Erdähnliche Welt", "water world": "Wasserwelt", "ammonia world": "Ammoniakwelt",
             "stern n": "Neutronenstern", "stern h": "Schwarzes Loch"}
    if c in names:
        t.append(names[c])
    elif c.startswith("stern d"):
        t.append("Weißer Zwerg")
    elif c.startswith("stern ") and c[6:].upper() in ("W", "WN", "WNC", "WC", "WO", "C", "CN", "CJ", "TTS", "AEBE"):
        t.append("Seltener Stern")
    if terra:
        t.append("Terraformbar")
    if landable:
        t.append("Landbar")
        if grav and grav >= 2:
            t.append(f"Hohe Schwerkraft {grav:.1f} g".replace(".", ","))
    if rings:
        t.append("Ringe")
    if atm and atm.lower() not in ("none", "keine"):
        t.append("Atmosphäre")
    return t
