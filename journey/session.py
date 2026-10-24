"""Credit-Auswertung der laufenden Session (Journal lesen, analysieren, Konsolenausgabe)."""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone

from . import timefmt


# ---------------------------------------------------------------------------
# Events -> Credits.  (Kategorie, Betrag)  positiv = Einnahme, negativ = Ausgabe
# ---------------------------------------------------------------------------
def credit_changes(ev):
    e = ev.get("event")
    g = ev.get

    # --- Einnahmen ---
    if e == "MarketSell":
        yield "Handel", g("TotalSale", 0)
    elif e == "SellDrones":
        yield "Handel", g("TotalSale", 0)
    elif e in ("SellExplorationData", "MultiSellExplorationData"):
        yield "Exploration", g("TotalEarnings", 0)
    elif e == "SellOrganicData":
        total = sum(b.get("Value", 0) + b.get("Bonus", 0) for b in ev.get("BioData", []))
        yield "Exobiologie", total
    elif e == "RedeemVoucher":
        yield "Kopfgelder/Bonds", g("Amount", 0)
    elif e == "MissionCompleted":
        yield "Missionen", g("Reward", 0)
    elif e in ("CommunityGoalReward", "SearchAndRescue", "CapShipBond"):
        yield "Sonstige Einnahmen", g("Reward", 0)
    elif e in ("ShipyardSell", "SellShipOnRebuy"):
        yield "Verkauf Schiffe/Module", g("ShipPrice", 0)
    elif e in ("ModuleSell", "ModuleSellRemote"):
        yield "Verkauf Schiffe/Module", g("SellPrice", 0)

    # --- Ausgaben ---
    elif e == "MarketBuy":
        yield "Kosten & Käufe", -g("TotalCost", 0)
    elif e == "BuyDrones":
        yield "Kosten & Käufe", -g("TotalCost", 0)
    elif e in ("BuyAmmo", "RefuelAll", "RefuelPartial", "Repair", "RepairAll",
               "RestockVehicle", "Resurrect", "BuyExplorationData", "BuyTradeData",
               "ModuleRetrieve"):
        yield "Kosten & Käufe", -(g("Cost", 0) or 0)
    elif e == "ShipyardBuy":
        yield "Kosten & Käufe", -g("ShipPrice", 0)
    elif e == "ModuleBuy":
        yield "Kosten & Käufe", -g("BuyPrice", 0)
        if "SellPrice" in ev:  # altes Modul wird direkt verkauft
            yield "Verkauf Schiffe/Module", g("SellPrice", 0)
    elif e == "ShipyardTransfer":
        yield "Kosten & Käufe", -g("TransferPrice", 0)
    elif e == "FetchRemoteModule":
        yield "Kosten & Käufe", -g("TransferCost", 0)
    elif e in ("PayFines", "PayBounties"):
        yield "Kosten & Käufe", -g("Amount", 0)
    elif e == "NpcCrewPaidWage":
        yield "Kosten & Käufe", -g("Amount", 0)


def read_events(path):
    events = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # halb geschriebene letzte Zeile im Live-Betrieb
    return events


def read_status_balance(directory):
    """Aktueller Kontostand aus Status.json (wird vom Spiel laufend geschrieben)."""
    try:
        with open(os.path.join(directory, "Status.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("Balance")
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Auswertung
# ---------------------------------------------------------------------------
def analyse(events, window_min, live):
    if not events:
        return None

    load = next((e for e in events if e.get("event") == "LoadGame"), None)
    start_ts = timefmt.parse_ts(load["timestamp"]) if load else timefmt.parse_ts(events[0]["timestamp"])
    start_balance = load.get("Credits") if load else None

    last_ts = timefmt.parse_ts(events[-1]["timestamp"])
    now = datetime.now(timezone.utc)
    # Live: Zeit laeuft weiter; sonst bis zum letzten Eintrag
    end_ts = now if live else last_ts
    elapsed = max(end_ts - start_ts, timedelta(seconds=1))

    cats = defaultdict(int)
    win_net = 0
    jumps = 0
    jump_dist = 0.0
    carrier_jumps = 0
    win_jumps = 0
    win_start = end_ts - timedelta(minutes=window_min)

    for ev in events:
        if "timestamp" not in ev:
            continue
        ts = timefmt.parse_ts(ev["timestamp"])
        if ev.get("event") == "FSDJump":
            jumps += 1
            jump_dist += ev.get("JumpDist", 0) or 0
            if ts >= win_start:
                win_jumps += 1
        elif ev.get("event") == "CarrierJump":
            carrier_jumps += 1
        for cat, amount in credit_changes(ev):
            if not amount:
                continue
            cats[cat] += amount
            if ts >= win_start:
                win_net += amount

    income = sum(v for v in cats.values() if v > 0)
    expense = sum(v for v in cats.values() if v < 0)
    net = income + expense

    hours = elapsed.total_seconds() / 3600
    win_hours = min(elapsed, timedelta(minutes=window_min)).total_seconds() / 3600

    return {
        "start_ts": start_ts,
        "end_ts": end_ts,
        "elapsed": elapsed,
        "hours": hours,
        "start_balance": start_balance,
        "cats": dict(cats),
        "income": income,
        "expense": expense,
        "net": net,
        "rate_net": net / hours,
        "rate_gross": income / hours,
        "win_min": window_min,
        "win_net": win_net,
        "win_rate": win_net / win_hours if win_hours else 0,
        "jumps": jumps,
        "jump_dist": jump_dist,
        "carrier_jumps": carrier_jumps,
        "jumps_per_hour": jumps / hours,
        "win_jumps_per_hour": win_jumps / win_hours if win_hours else 0,
        "commander": (load or {}).get("Commander"),
    }


def render(r, journal_path, live, status_balance):
    out = []
    bar = "=" * 58
    out.append(bar)
    out.append(f"  Elite Dangerous - Credits pro Stunde" + (f"   CMDR {r['commander']}" if r["commander"] else ""))
    out.append(bar)
    out.append(f"  Journal:       {os.path.basename(journal_path)}")
    out.append(f"  Session-Start: {r['start_ts'].astimezone().strftime('%H:%M:%S')} (lokal)")
    out.append(f"  Spielzeit:     {timefmt.fmt_dur(r['elapsed'])}" + ("  (laeuft)" if live else ""))
    out.append("")

    out.append("  Einnahmen / Ausgaben nach Kategorie")
    out.append("  " + "-" * 54)
    if r["cats"]:
        for cat, val in sorted(r["cats"].items(), key=lambda kv: -kv[1]):
            out.append(f"  {cat:<26}{timefmt.fmt_cr(val, sign=True):>28}")
    else:
        out.append("  (noch keine Credit-relevanten Events in dieser Session)")
    out.append("  " + "-" * 54)
    out.append(f"  {'Einnahmen':<26}{timefmt.fmt_cr(r['income'], True):>28}")
    out.append(f"  {'Ausgaben':<26}{timefmt.fmt_cr(r['expense'], True):>28}")
    out.append(f"  {'Netto':<26}{timefmt.fmt_cr(r['net'], True):>28}")
    out.append("")

    out.append(f"  >> Brutto:  {timefmt.fmt_cr(r['rate_gross']):>20} / Stunde")
    out.append(f"  >> NETTO:   {timefmt.fmt_cr(r['rate_net']):>20} / Stunde   (Session)")
    out.append(f"  >> Tempo:   {timefmt.fmt_cr(r['win_rate']):>20} / Stunde   (letzte {r['win_min']} Min.)")

    out.append("")
    out.append("  Spruenge")
    out.append("  " + "-" * 54)
    out.append(f"  {'Hyperraum-Spruenge (Schiff)':<30}{r['jumps']:>24}")
    out.append(f"  {'Strecke':<30}{r['jump_dist']:>21,.1f} Ly".replace(",", "."))
    if r["jumps"]:
        out.append(f"  {'Durchschnitt pro Sprung':<30}{r['jump_dist'] / r['jumps']:>21,.1f} Ly".replace(",", "."))
    out.append(f"  {'Spruenge pro Stunde':<30}{r['jumps_per_hour']:>24.1f}")
    out.append(f"  {'  letzte ' + str(r['win_min']) + ' Min.':<30}{r['win_jumps_per_hour']:>24.1f}")
    out.append(f"  {'Flottentraeger-Spruenge':<30}{r['carrier_jumps']:>24}")

    if status_balance is not None and r["start_balance"] is not None:
        diff = status_balance - r["start_balance"]
        out.append("")
        out.append(f"  Kontrolle per Kontostand (Status.json):")
        out.append(f"    Start: {timefmt.fmt_cr(r['start_balance'])}   Jetzt: {timefmt.fmt_cr(status_balance)}")
        out.append(f"    Differenz: {timefmt.fmt_cr(diff, True)}  ->  {timefmt.fmt_cr(diff / r['hours'])} / Stunde")
    out.append(bar)
    return "\n".join(out)
