# EDCJ - Elite Dangerous Commander's Journey

Deutsche Fassung der README · English version: [README.md](README.md)

Version 0.9.7.6 (Vorabversion; `python3 edcj.py --version` zeigt sie an, die Oberfläche steht im Kopf neben dem Titel).

Elite Dangerous Commander's Journey: Journal-Auswertung im LCARS-Look (Thema „Star Trek“, weitere Themen wählbar). Nur Python 3, keine weiteren Pakete.

## Installation

**Linux:** `python3 edcj.py` (oder `./edcj.py`). Der Journal-Ordner wird automatisch gefunden (Steam/Proton, Flatpak, Lutris, Wine).
**Windows 10/11:** Python 3 installieren (Haken „Add python.exe to PATH"), ZIP entpacken, `EDCJ-Start.bat` doppelklicken.
Details stehen in `INSTALLATION-WINDOWS.txt` (liegt dem Programm bei). Beide Systeme nutzen denselben Programmcode.

    python3 edcj.py              # Journal automatisch finden, Browser öffnen
    python3 edcj.py --help       # alle Parameter (-d Journal-Ordner, --port, --app, --log, --backfill, ...)

## Daten (Portabel-Modus)

Im Ordner `data/` neben `edcj.py` liegen deine Daten: `market.db` (alles Gesammelte), `captains_log.md` samt `.settings.json`, `.state.json`, `.bodies.json`.
Solange der Ordner `data/` existiert, nutzt das Programm ihn automatisch. Löschst oder benennst du ihn um, fällt es auf `~/.local/share/ed-lcars/` zurück.
Mit `--log /anderer/pfad/captains_log.md` lässt sich beides übersteuern. Sicherung: im Programm unter Einstellungen → „Backup speichern“ oder den Ordner `data/` kopieren (bei beendetem Programm).

**Wichtig zur Vorgeschichte:** Beim ersten Start schreibt EDCJ nur die **letzte Spielsitzung** ins Captain's Log (die Textdatei). Die Auswertungen für Karriere, Spielstil, Rekorde, Fraktionen sowie Körper und Scans lesen dagegen **alle** vorhandenen Journale ein, auch ältere. Märkte und Werften kennt EDCJ nur von Stationen, deren Markt bzw. Outfitting im Journal bzw. in den Marktdateien vorkommt. Wer mehr alte Sitzungen im Captain's Log haben möchte, startet beim allerersten Mal mit `--backfill N` (z. B. `python3 edcj.py --backfill 50`); das wirkt nur auf das Log und nur beim ersten Start.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `data/` | Deine Daten (Datenbank, Captain's Log, Einstellungen) |
| `edcj.py` | Starter (ruft `journey.webserver.main()` auf) |
| `web/index.html`, `web/style.css`, `web/app.js` | Oberfläche (wird vom Server ausgeliefert) |
| `journey/config.py` | Konfiguration, Journal-Ordner finden |
| `journey/timefmt.py`, `journey/helpers.py` | Hilfsfunktionen (Zeit/Format, Entfernung, Zeitraum, Tabellenblöcke) |
| `journey/session.py` | Credit-Auswertung der laufenden Session |
| `journey/bodydata.py` | Systeme, Körper, Ringe, Fraktionen im System |
| `journey/livefeed.py` | Live-Daten für die Oberfläche (`/api/stats`) und Sprachausgabe-Feed |
| `journey/captain.py` | Captain's Log (Markdown) |
| `journey/database.py`, `journey/backup.py` | SQLite-Schema (`market.db`), Backup/Wiederherstellen |
| `journey/market_ingest.py` | Märkte, Module, Fraktions-Messwerte einlesen |
| `journey/career_ingest.py` | Karriere-Ereignisse einlesen (`career_events`, Whitelist `CAREER_EVENTS`, `CAREER_VER`) |
| `journey/status.py`, `journey/cockpit.py` | Status.json, Cockpit und Lage-Erkennung |
| `journey/dienstakte.py` | Journey-Missionen, Dienstgrade, Meilensteine, Personalakte |
| `journey/views_misc.py`, `carrier.py`, `missions.py`, `mining.py` | Ansichten (Flugschreiber, Lücken, Bio-Atlas, Fraktions-Verlauf, Fleet Carrier, Missionsübersicht, Mining) |
| `journey/career_api.py`, `journey/market_api.py` | Abfragen `/api/career`, `/api/market` |
| `journey/exports.py`, `hotx.py`, `notebook.py`, `settings.py` | CSV-Export/Suche, Hotspot-Ausblendung, Notizen, Einstellungen |
| `journey/webserver.py` | HTTP-Server, Instanzverwaltung, `main()` |

Module greifen über `from . import x` aufeinander zu (`x.funktion(...)`), damit zyklische Abhängigkeiten kein Problem sind.

## Erweitern

* **Neue Missionsart:** in `journey/dienstakte.py` (1) Basiswert in `LM_BASE`, (2) Thema in `lm_generate`, (3) Messung in `lm_value`, optional (4) Zähler in `LM_CNT` und Meilensteine in `LM_MILES`.
* **Neuer Meilenstein / Dienstgrad:** Eintrag in `LM_MILES` bzw. `LM_RANKS`.
* **Neues Journal-Ereignis auswerten:** Eventname in `CAREER_EVENTS` (`career_ingest.py`), in `career_events` ein `R(...)` schreiben, `CAREER_VER` erhöhen (die Datenbank wird beim nächsten Start einmal neu aufgebaut).
* **Neuer Reiter (Tabelle):** Abfrage in einem `*_view`, Einbindung in `career_api.py`; in `web/index.html` ein `<div class="grid tab" id="tab-xyz">` plus Einträge in `TABS`, `GROUPS`, `CR` in `web/app.js`.

## Galerie (ab 0.9.1.1)

Reiter Logbuch → Galerie. Drückst du im Spiel die Screenshot-Taste (Standard F10), schreibt Elite ein `Screenshot`-Ereignis ins Journal.
EDCJ liest es, sucht die Bilddatei im Bilderordner des Spiels (`…/Pictures/Frontier Developments/Elite Dangerous`, bei Proton im Wine-Präfix,
oder der Ordner aus dem Feld unten in der Galerie) und kopiert sie nach `data/screenshots/`. Für BMP-Bilder entsteht eine kleine PNG-Vorschau
in `data/screenshots/thumbs/`. Ort, Zeit, Koordinaten, Notiz, Schlagworte und Favoriten stehen in `market.db` (Tabelle `shots`) und sind damit
im Backup. Die Bilddateien selbst gehören nicht ins Backup. Ältere Screenshots werden aus den vorhandenen Journalen nachgetragen.
Tipp: im Spiel PNG oder JPG als Screenshot-Format wählen (BMP ist sehr groß).

## Spielstil (ab 0.9.5)

Karriere → Spielstil. Aus den zehnminütigen Aktivitätsblöcken deines Journals (und den Ereignissen darin) entsteht ein Kreisdiagramm
der Tätigkeiten (Handel, Erkundung, Kampf, Mining, Sonstiges) pro Woche samt Wochenverlauf und Trend, eine Heatmap Wochentag × Uhrzeit
und eine Liste persönlicher Rekorde und Serien. Alles rechnet nur mit den eigenen Daten.


## Tablet und zweiter Bildschirm (Heimnetz)

Das Layout passt sich Tablets quer und hochkant an (größere Touch-Flächen, Tabellen scrollen seitlich, Reisekarte mit Zwei-Finger-Zoom).
Mehrere Fenster (Zweitmonitor, Tablet) laufen gleichzeitig am selben Server und zeigen dieselben Daten.

Freigabe im Heimnetz:
1. Start mit `--lan` (z. B. `python3 edcj.py --lan`) oder in Settings unter „Tablet & Heimnetz“ einschalten und EDCJ neu starten.
2. EDCJ gibt beim Start den Zugangscode und die Adresse aus (z. B. `http://192.168.178.25:8800/`). Beides steht auch in den Settings.
3. Am Tablet die Adresse im Browser öffnen und einmal den Code eingeben. Der Rechner selbst braucht keinen Code.
4. Backup, Wiederherstellen und Beenden gehen nur am Rechner. Fünf falsche Codes sperren eine Minute.
5. Windows fragt beim ersten Start nach der Firewall: für „Private Netzwerke“ zulassen. Ohne `--lan` bleibt EDCJ wie bisher nur auf dem eigenen Rechner erreichbar.

Vollbild: Der Knopf ⛶ im Kopf und die Settings („Vollbild (dieses Gerät)“) schalten den Vollbild des Browsers um. Optional geht das Gerät beim ersten Tippen nach dem Laden automatisch in den Vollbild (der Browser erlaubt es nur nach einer Berührung).

Linux mit ufw: Wenn das Tablet die Seite nicht erreicht, den Port für das Heimnetz freigeben, z. B.
`sudo ufw allow from 192.168.0.0/24 to any port 8800 proto tcp` (Netz-Adresse an das eigene Heimnetz anpassen). Bei firewalld: `sudo firewall-cmd --permanent --add-port=8800/tcp`, dann `sudo firewall-cmd --reload`.

Kurs setzen vom Tablet: Ein Klick auf einen Systemnamen am Tablet legt den Namen in die Zwischenablage des Rechners (Meldung „Kurs gesetzt“). Im Spiel dann in der Galaxiekarte mit Strg+V einfügen. Am Rechner selbst kopiert der Klick wie bisher.
Der Rechner braucht dafür ein Zwischenablage-Werkzeug: Windows `clip` (ist dabei), Linux Wayland `wl-clipboard` (`sudo pacman -S wl-clipboard`), Linux X11 `xclip` oder `xsel`. Fehlt es, nennt die Meldung am Tablet das fehlende Paket.

## Schiffsvergleich, Wartung, Baupläne (0.9.7.1)

- Schiff › Meine Flotte › Vergleich: Die Schiffe stehen als Spalten nebeneinander (Sprungweite, Fracht, Tank, Kernmodule, Schild, Waffen, Optionale Module, Wert, Rebuy). Alles stammt aus dem letzten Loadout je Schiff. Schildstärke und Geschwindigkeit stehen nicht im Journal und werden nicht geraten.
- Cockpit › Wartung vor dem Flug: Treibstoff (auch gegen die geplante Route), Rumpf, Module, Munition und Rebuy gegen den Kontostand, jeweils mit Ampel. Munition wird am höchsten bisher gesehenen Stand der Waffe gemessen. Dafür wird die Karrieredatenbank beim ersten Start einmal neu aus den Journalen aufgebaut.
- Karriere › Baupläne: Aus deinen eigenen Crafts (Zutatenliste im Journal) wird abgeleitet, welche Zutaten dir für einen weiteren Craft fehlen, auch als Summe über alle Baupläne. Der Materialbestand berücksichtigt jetzt auch Crafting, Synthese, Technologiehändler und Materialtausch.

## Wartung, Wochenkapitel, Entdeckungswerte (0.9.7.3)

- Cockpit › Wartung: Die Wartung vor dem Flug ist ein eigener Reiter neben Live und Missionen.
- Journey-Missionen: Die Zielwerte richten sich jetzt nach dem, was du in den letzten acht Wochen selbst geschafft hast (typischer Tag bzw. typische Woche, nie über deinem Bestwert). Einzelverkäufe sind durch deinen größten Einzelverkauf, deine größte Fracht und deine Gewinne je Tonne begrenzt. Neue Auftragsarten: Engineering-Crafts, Materialien sammeln, Erkundungsdaten verkaufen, aktive Stunden, weiter Einzelsprung und „N t mit mindestens X Cr/t Gewinn“ (X stammt aus deinen eigenen Margen).
- Wochenkapitel: Pro Kalenderwoche gibt es ein Kapitel mit drei Teilzielen. Das Thema (Handel, Kampf, Mining, Erkundung) folgt deiner Spielzeit der letzten vier Wochen und wechselt, damit nicht jede Woche dasselbe kommt. 60 Dienstpunkte, eigene Meilensteine.
- Karriere › Entdeckungen: Erstentdeckungen mit Besonderheiten, Systemübersicht, wertvollste Funde und eine Wertschätzung (Formel aus der Spielerforschung; Näherung, echte Auszahlungen weichen ab). „Unverkauft“ bedeutet, dass das System nach dem Scan in keinem verkauften Erkundungsdatensatz auftaucht. Darunter steht eine Prüfung der Schätzung gegen deine echten Verkäufe aus dem Journal. Für die Masse der Körper wird die Karrieredatenbank beim ersten Start neu aufgebaut.

## Sprache / Language (0.9.7.4)

Unter **Settings → Sprache / Language** lässt sich die Oberfläche zwischen **Deutsch** und **English** umschalten (gilt pro Gerät, die Seite lädt neu). Übersetzt werden nur die Texte von EDCJ selbst. Daten aus dem Spiel (Journal, Märkte, Schiffs- und Modulnamen, Missionstexte) erscheinen so, wie der Spielclient sie schreibt – steht der Client auf Englisch, ist auch dort alles englisch. Zahlen- und Datumsformat werden mit umgestellt (1,234.5 statt 1.234,5). Einträge, die EDCJ früher auf Deutsch ins Captain's Log geschrieben hat, werden beim Anzeigen mit übersetzt.

## Language (English)

Use **Settings → Sprache / Language** to switch the interface between German and English (per device, the page reloads). Only EDCJ's own texts are translated; game data is shown exactly as the game client writes it, so with an English client everything is English.

## Schrift / Font (0.9.7.5)

Die Schrift „Antonio“ liegt im Programm (`web/fonts/`, Lizenz SIL Open Font License 1.1, siehe `web/fonts/OFL.txt`). EDCJ lädt keine Schriften oder anderen Inhalte aus dem Internet; die Oberfläche macht keine Anfragen an fremde Server.
The font "Antonio" ships with the program (`web/fonts/`, SIL Open Font License 1.1, see `web/fonts/OFL.txt`). EDCJ loads nothing from the internet; the interface makes no requests to third-party servers.

**About history (English):** On the very first start EDCJ writes only the **last play session** into the Captain's Log (the text file). Career, play style, records, factions, bodies and scans are evaluated from **all** journals found, including older ones. Markets and shipyards are only known for stations whose market or outfitting appears in your journals or market files. To get more old sessions into the Captain's Log, start once with `--backfill N` (e.g. `python3 edcj.py --backfill 50`); this only affects the log and only on the first start.
