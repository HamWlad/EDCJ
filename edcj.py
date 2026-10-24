#!/usr/bin/env python3
"""
edcj.py - EDCJ, Elite Dangerous Commander's Journey (Journal-Auswertung im Star-Trek-TNG-Look).

Startet einen kleinen lokalen Webserver und oeffnet das Dashboard im Browser.
Es liest dein Journal live mit und zeigt Credits/Stunde, Spruenge und mehr.

Nutzung:
  ./edcj.py                  # Journal automatisch finden, Browser oeffnen
  ./edcj.py --app            # als eigenes Fenster (Chromium/Chrome/Brave, ohne Adressleiste)
  ./edcj.py -d /pfad/Journal # Journal-Ordner vorgeben
  ./edcj.py --port 9000      # anderen Port nutzen
  ./edcj.py --window 30      # Standard-Fenster fuer "aktuelles Tempo"
  ./edcj.py --no-browser     # Browser nicht automatisch oeffnen
  ./edcj.py --log ~/captains_log.md   # Log-Datei an eigenem Ort
  ./edcj.py --backfill 5     # beim ersten Start die letzten 5 aelteren Journale nachtragen

Beenden mit Strg+C. Nur Python 3, keine weiteren Pakete.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from journey.webserver import main  # noqa: E402

if __name__ == "__main__":
    main()
