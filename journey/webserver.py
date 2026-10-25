"""Webserver (Handler), Instanzverwaltung und main()."""

import argparse
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.parse import parse_qs, urlparse

from . import backup, captain, career_api, career_ingest, clip, cockpit, config, dienstakte, exports, gallery, helpers, hotx, livefeed, lan, market_api, kolonien, market_ingest, notebook, profil, settings, sitzungen, stationsakte, status


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _gate(self, post):
        """LAN-Zugang: Rechner selbst immer frei, andere Geraete nur mit Zugangscode."""
        ip = self.client_address[0]
        path = urlparse(self.path).path
        if lan.is_local(ip):
            return True
        if post and path == "/login":
            n = min(200, int(self.headers.get("Content-Length") or 0))
            tok = lan.try_login(ip, self.rfile.read(n).decode("utf-8", "replace"))
            if tok:
                data = b"ok"
                self.send_response(200)
                self.send_header("Set-Cookie", f"edcj_auth={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send(429 if tok is None else 403, "nein", "text/plain")
            return False
        if not lan.authed(self):
            if path.startswith("/api/"):
                self._send(401, json.dumps({"error": "Zugangscode noetig"}), "application/json; charset=utf-8")
            else:
                self._send(200, lan.LOGIN, "text/html; charset=utf-8")
            return False
        if post and path in ("/api/shutdown", "/api/restore", "/api/lan", "/api/journaldir"):
            self._send(403, json.dumps({"error": "nur am Rechner selbst"}), "application/json; charset=utf-8")
            return False
        if path in ("/api/backup", "/api/lan", "/api/journaldir"):
            self._send(403, json.dumps({"error": "nur am Rechner selbst"}), "application/json; charset=utf-8")
            return False
        return True

    def _lang(self):
        from . import timefmt
        timefmt.set_lang("en" if "edcj_lang=en" in (self.headers.get("Cookie") or "") else "de")

    def do_POST(self):
        self._lang()
        if self._gate(True):
            self._post()

    def do_GET(self):
        self._lang()
        if self._gate(False):
            self._get()

    def _post(self):
        if urlparse(self.path).path == "/api/clip" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(1000, int(self.headers.get("Content-Length") or 0))
                d = json.loads(self.rfile.read(n) or b"{}")
                out = clip.set_clip(d.get("text", ""))
            except (ValueError, OSError):
                out = {"ok": False, "error": "ungueltig"}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/lan" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(2000, int(self.headers.get("Content-Length") or 0))
                d = json.loads(self.rfile.read(n) or b"{}")
                lan.set_state(d.get("on"), d.get("code"))
            except (ValueError, OSError):
                pass
            self._send(200, json.dumps(lan.info(self.server.server_address[1])), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/journaldir" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(4000, int(self.headers.get("Content-Length") or 0))
                self._send(200, json.dumps(settings.set_journal_dir(json.loads(self.rfile.read(n) or b"{}").get("dir"))), "application/json; charset=utf-8")
            except (ValueError, OSError, AttributeError):
                self._send(400, json.dumps({"error": "ungueltig"}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/settings" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(20000, int(self.headers.get("Content-Length") or 0))
                d = json.loads(self.rfile.read(n) or b"{}")
                out = settings.save_settings(d)
                self._send(200, json.dumps(out), "application/json; charset=utf-8")
            except (ValueError, OSError):
                self._send(400, json.dumps({"error": "ungueltig"}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/gallery" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(8000, int(self.headers.get("Content-Length") or 0))
                self._send(200, json.dumps(gallery.gallery_post(json.loads(self.rfile.read(n) or b"{}"))), "application/json; charset=utf-8")
            except (ValueError, OSError):
                self._send(400, json.dumps({"error": "ungueltig"}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/lm" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(4000, int(self.headers.get("Content-Length") or 0))
                self._send(200, json.dumps(dienstakte.lm_api(json.loads(self.rfile.read(n) or b"{}"))), "application/json; charset=utf-8")
            except (ValueError, OSError):
                self._send(400, json.dumps({"error": "ungueltig"}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/hotx" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(8000, int(self.headers.get("Content-Length") or 0))
                self._send(200, json.dumps(hotx.hotx_api(json.loads(self.rfile.read(n) or b"{}"))), "application/json; charset=utf-8")
            except (ValueError, OSError):
                self._send(400, json.dumps({"error": "ungueltig"}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/kolonien" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(2000, int(self.headers.get("Content-Length") or 0))
                self._send(200, json.dumps(kolonien.set_stock(json.loads(self.rfile.read(n) or b"{}"))), "application/json; charset=utf-8")
            except (ValueError, OSError):
                self._send(400, json.dumps({"error": "ungueltig"}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/notes" and self.headers.get("X-EDCJ") == "1":
            try:
                n = min(8000, int(self.headers.get("Content-Length") or 0))
                self._send(200, json.dumps(notebook.notes_api(json.loads(self.rfile.read(n) or b"{}"))), "application/json; charset=utf-8")
            except (ValueError, OSError):
                self._send(400, json.dumps({"error": "ungueltig"}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/restore" and self.headers.get("X-EDCJ") == "1":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 2 * 1024 ** 3:
                    raise ValueError
                out = backup.restore_backup(self.rfile.read(n))
                self._send(200, json.dumps(out), "application/json; charset=utf-8")
            except (ValueError, OSError) as exc:
                self._send(400, json.dumps({"error": "Upload ungültig: " + str(exc)}), "application/json; charset=utf-8")
            return
        if urlparse(self.path).path == "/api/shutdown" and self.headers.get("X-EDCJ") == "1":
            self._send(200, json.dumps({"ok": True}), "application/json; charset=utf-8")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._send(403, "verboten", "text/plain; charset=utf-8")

    def _get(self):
        url = urlparse(self.path)
        if url.path == "/api/me":
            self._send(200, json.dumps({"local": lan.is_local(self.client_address[0]), "clip": clip.available()}), "application/json; charset=utf-8")
        elif url.path == "/api/journaldir":
            self._send(200, json.dumps(config.journal_info()), "application/json; charset=utf-8")
        elif url.path == "/api/lan":
            self._send(200, json.dumps(lan.info(self.server.server_address[1])), "application/json; charset=utf-8")
        elif url.path == "/api/stats":
            q = parse_qs(url.query)
            try:
                window = max(1, min(1440, int(q.get("window", [config.CONFIG["window"]])[0])))
            except ValueError:
                window = config.CONFIG["window"]
            try:
                payload = livefeed.build_payload(window)
            except Exception as exc:  # Anzeige statt Absturz
                payload = {"error": f"Auswertung fehlgeschlagen: {exc}"}
            self._send(200, json.dumps(payload), "application/json; charset=utf-8")
        elif url.path == "/api/hotx":
            self._send(200, json.dumps(hotx.hotx_api()), "application/json; charset=utf-8")
        elif url.path == "/api/notes":
            self._send(200, json.dumps(notebook.notes_api()), "application/json; charset=utf-8")
        elif url.path == "/api/market":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                out = market_api.market_api(q)
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/career":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                out = career_api.career_api(q)
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/lm":
            try:
                out = dienstakte.lm_api()
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/stationsakte":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                out = stationsakte.stationsakte_api(q)
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/sessions":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                out = sitzungen.sitzungen_api(q)
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/profile":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                out = profil.profile_api(q)
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/gallery":
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                out = gallery.gallery_api(q)
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/shot":
            q = parse_qs(url.query)
            try:
                img = gallery.image_bytes(int(q.get("id", ["0"])[0]), q.get("t", ["0"])[0] == "1")
            except (ValueError, OSError):
                img = None
            if not img:
                self._send(404, "nicht gefunden", "text/plain; charset=utf-8")
            else:
                self.send_response(200)
                self.send_header("Content-Type", img[1])
                self.send_header("Content-Length", str(len(img[0])))
                self.send_header("Cache-Control", "private, max-age=3600")
                self.end_headers()
                self.wfile.write(img[0])
        elif url.path == "/api/settings":
            self._send(200, json.dumps(settings.load_settings()), "application/json; charset=utf-8")
        elif url.path == "/api/cockpit":
            try:
                out = cockpit.cockpit_api(helpers._num_range(parse_qs(url.query).get("range", ["0"])[0]))
            except Exception as exc:
                out = {"error": str(exc)}
            self._send(200, json.dumps(out), "application/json; charset=utf-8")
        elif url.path == "/api/backup":
            data, nm = backup.make_backup()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{nm}"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif url.path == "/api/export":
            body, nm = exports.export_csv(parse_qs(url.query).get("what", [""])[0])
            if body is None:
                self._send(404, "unbekannter Export", "text/plain; charset=utf-8")
            else:
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="ed_{nm}_{datetime.now().strftime("%Y-%m-%d")}.csv"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
        elif url.path == "/api/search":
            q = parse_qs(url.query).get("q", [""])[0][:200]
            self._send(200, json.dumps(exports.search_log(q)), "application/json; charset=utf-8")
        elif url.path == "/api/log":
            try:
                with open(config.CONFIG["log"], "rb") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 800000))
                    text = f.read().decode("utf-8", "replace")
            except OSError:
                text = ""
            self._send(200, json.dumps({"path": config.CONFIG["log"], "text": text, "error": captain.LOG_STATE["error"]}),
                       "application/json; charset=utf-8")
        elif url.path in ("/", "/index.html"):
            self._send(200, _web_file("index.html"), "text/html; charset=utf-8")
        elif url.path in ("/static/app.js", "/static/style.css", "/static/i18n.js", "/static/i18n_en.js"):
            name = url.path.rsplit("/", 1)[1]
            body = _web_file(name).replace("{{WINDOW}}", str(config.CONFIG["window"]))
            self._send(200, body, "application/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8")
        elif url.path in ("/static/fonts/Antonio-Regular.ttf", "/static/fonts/Antonio-Bold.ttf", "/static/fonts/OFL.txt"):
            try:
                with open(os.path.join(WEB_DIR, "fonts", url.path.rsplit("/", 1)[1]), "rb") as f:
                    data = f.read()
            except OSError:
                self._send(404, "nicht gefunden", "text/plain; charset=utf-8")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8" if url.path.endswith(".txt") else "font/ttf")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send(404, "nicht gefunden", "text/plain; charset=utf-8")


WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def _web_file(name):
    with open(os.path.join(WEB_DIR, name), encoding="utf-8") as f:
        text = f.read()
    return text.replace("{{VERSION}}", config.VERSION) if name == "index.html" else text


def _app_browsers():
    names = ["chromium", "google-chrome-stable", "google-chrome", "brave", "brave-browser", "chromium-browser", "vivaldi"]
    paths = [shutil.which(n) for n in names]
    if config.IS_WIN:
        roots = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        for r in filter(None, roots):
            for rel in (r"BraveSoftware\Brave-Browser\Application\brave.exe", r"Google\Chrome\Application\chrome.exe",
                        r"Microsoft\Edge\Application\msedge.exe", r"Vivaldi\Application\vivaldi.exe"):
                paths.append(os.path.join(r, rel))
    return [p for p in paths if p and os.path.isfile(p)]


def open_app_window(url):
    for path in _app_browsers():
        if path:
            subprocess.Popen([path, f"--app={url}", "--window-size=1500,900"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    return False


def _on_term(*_):
    raise KeyboardInterrupt  # SIGTERM -> sauberes Beenden inkl. Log-Sicherung


def _other_instances():
    """PIDs anderer laufender edcj.py-Prozesse (auch alte ed_lcars.py) (Linux, /proc)."""
    me, found = os.getpid(), []
    for d in glob.glob("/proc/[0-9]*"):
        try:
            pid = int(os.path.basename(d))
            with open(d + "/cmdline", "rb") as f:
                argv = f.read().decode("utf-8", "replace").split("\0")
        except (OSError, ValueError):
            continue
        if pid != me and "python" in os.path.basename(argv[0]) and any(os.path.basename(x) in ("edcj.py", "ed_lcars.py") for x in argv[1:]):
            found.append(pid)
    return found


def _alive(pid):
    """Prozess laeuft noch (Zombies zaehlen als beendet)."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            return f.read().rsplit(b") ", 1)[1][:1] != b"Z"
    except (OSError, IndexError):
        return False


def _wait_gone(pids, secs):
    end = time.time() + secs
    while time.time() < end and any(_alive(p) for p in pids):
        time.sleep(0.2)
    return [p for p in pids if _alive(p)]


def stop_old_instances(port):
    if config.IS_WIN:  # keine /proc-Suche: Vorgaenger ueber den Offline-Befehl beenden, falls auf dem Port einer laeuft
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/shutdown", method="POST",
                                                          headers={"X-EDCJ": "1"}), timeout=2).read()
            print("Laufende Instanz beendet.")
            time.sleep(1.5)
        except Exception:
            pass
        return
    pids = _other_instances()
    if not pids:
        return
    print(f"Laufende Instanz gefunden (PID {', '.join(map(str, pids))}), wird beendet ...")
    graceful = False
    try:  # erst freundlich ueber den Offline-Befehl (sichert das Log)
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/shutdown", method="POST",
                                                      headers={"X-EDCJ": "1"}), timeout=2).read()
        graceful = True
    except Exception:
        pass  # aeltere Version ohne Offline-Befehl oder anderer Port
    left = _wait_gone(pids, 8 if graceful else 0)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if not left:
            break
        for p in left:
            try:
                os.kill(p, sig)
            except OSError:
                pass
        left = _wait_gone(left, 5)
    print("Alte Instanz beendet." if not left else f"Konnte Prozess {left} nicht beenden.")


class Server(ThreadingHTTPServer):
    # Windows: SO_REUSEADDR erlaubt dort einen zweiten Server auf demselben Port. Das wollen wir nicht.
    allow_reuse_address = not config.IS_WIN


def main():
    for _st in (sys.stdout, sys.stderr):  # Windows-Konsole: Umlaute und Sonderzeichen nicht abstuerzen lassen
        try:
            _st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="EDCJ - Elite Dangerous Commander's Journey")
    ap.add_argument("--version", action="version", version="EDCJ " + config.VERSION)
    ap.add_argument("file", nargs="?", help="Journal-Datei (sonst: neueste automatisch)")
    ap.add_argument("-d", "--dir", help="Journal-Ordner")
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--window", type=int, default=60, help="Minuten fuer 'aktuelles Tempo'")
    ap.add_argument("--log", default=config.DEFAULT_LOG, help="Pfad der Captain's-Log-Datei")
    ap.add_argument("--backfill", type=int, default=0, help="beim ersten Start so viele aeltere Journale nachtragen")
    ap.add_argument("--app", action="store_true", help="als App-Fenster oeffnen (Chromium-basiert)")
    ap.add_argument("--lan", action="store_true", help="im Heimnetz freigeben (z.B. fuer ein Tablet), Zugriff nur mit Zugangscode")
    ap.add_argument("--no-browser", action="store_true", help="Browser nicht automatisch oeffnen")
    args = ap.parse_args()

    config.CONFIG.update(file=args.file, dir=args.dir, window=args.window, log=os.path.expanduser(args.log), backfill=args.backfill)
    if args.dir and not os.path.isdir(os.path.expanduser(args.dir)):
        print(f"Warnung: Der Ordner \"{args.dir}\" (Parameter -d) existiert nicht und wird ignoriert. "
              "Den Journal-Ordner kannst du in der Oberflaeche unter Settings setzen.")
        args.dir = None
    if args.dir:
        config.CONFIG["dir"] = os.path.expanduser(args.dir)
    else:
        config.CONFIG["dir"] = None
    if not args.file and not config.find_journal_dir(config.CONFIG["dir"]):
        print("Warnung: Journal-Ordner nicht gefunden. EDCJ startet trotzdem; bitte in der Oberflaeche unter Settings den Journal-Ordner eintragen "
              "(unter Windows liegt er normalerweise in C:\\Users\\NAME\\Saved Games\\Frontier Developments\\Elite Dangerous).")
    if not args.file and not config.journal_info()["files"]:
        print("Hinweis: Im Journal-Ordner liegen noch keine Journal-Dateien. EDCJ startet trotzdem; den Ordner kannst du in der Oberflaeche unter Settings aendern.")

    if args.lan:
        config.CONFIG["lan"] = True
    lan_on = lan.enabled()
    config.CONFIG["lan_active"] = lan_on
    signal.signal(signal.SIGTERM, _on_term)
    stop_old_instances(args.port)
    server, last = None, None
    for _try in range(30 if config.IS_WIN else 1):  # Windows: kurz warten, bis die eben beendete Instanz den Port freigibt
        try:
            server = Server(("0.0.0.0" if lan_on else "127.0.0.1", args.port), Handler)
            break
        except OSError as exc:
            last = exc
            time.sleep(0.5)
    if server is None:
        sys.exit(f"Port {args.port} nicht verfuegbar ({last}). Laeuft EDCJ schon in einem anderen Fenster? Sonst anderen Port mit --port waehlen.")

    threading.Thread(target=captain.log_worker, daemon=True).start()
    threading.Thread(target=market_ingest.faction_worker, daemon=True).start()
    threading.Thread(target=career_ingest.career_worker, daemon=True).start()
    threading.Thread(target=status.status_worker, daemon=True).start()
    print(f"Captain's Log: {config.CONFIG['log']}")
    url = f"http://127.0.0.1:{args.port}/"
    print(f"EDCJ {config.VERSION} laeuft auf {url}   (Strg+C zum Beenden)")
    if lan_on:
        print(f"LAN-Freigabe AN. Zugangscode: {lan.code()}   Adressen fuer das Tablet: " + (", ".join(lan.addresses(args.port)) or "(keine gefunden)"))
    if not args.no_browser:
        def launch():
            time.sleep(0.5)
            if not (args.app and open_app_window(url)):
                webbrowser.open(url)
        threading.Thread(target=launch, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeende.")
    finally:
        server.server_close()
        try:
            with captain.LOG_LOCK:
                captain.process_journals()  # Captain's Log vor dem Beenden vollstaendig nachtragen
        except Exception:
            pass
        try:
            market_ingest.ingest_market(config._journal_dir())
        except Exception:
            pass
        print("Offline. Captain's Log gesichert.")
