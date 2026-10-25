let win = {{WINDOW}};
const $ = id => document.getElementById(id);
const fmt = n => Math.round(n).toLocaleString('de-DE');
const sgn = n => (n > 0 ? '+' : '') + fmt(n);
const dur = s => { s = Math.floor(s); const h = Math.floor(s/3600), m = Math.floor(s%3600/60), x = s%60;
  return h + 'h ' + String(m).padStart(2,'0') + 'm ' + String(x).padStart(2,'0') + 's'; };
const pad = n => String(n).padStart(2,'0');

function stardate(d){ // Spielzeit: Elite-Jahr = Jahr + 1286, Zeit in UTC
  const wd = (window.EDCJ_LANG==='en'?['Sun','Mon','Tue','Wed','Thu','Fri','Sat']:['So','Mo','Di','Mi','Do','Fr','Sa'])[d.getUTCDay()];
  return wd + ' ' + pad(d.getUTCDate()) + '.' + pad(d.getUTCMonth() + 1) + '.' + (d.getUTCFullYear() + 1286) + ', ' +
    pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ':' + pad(d.getUTCSeconds()) + ' UTC';
}
function tick(){
  const d = new Date();
  $('clock').textContent = pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  $('stardate').textContent = 'Sternzeit ' + stardate(d);
}
setInterval(tick, 1000); tick();

document.querySelectorAll('button[data-w]').forEach(b => {
  b.addEventListener('click', () => { win = +b.dataset.w; poll(); });
});
function markButtons(){
  document.querySelectorAll('button[data-w]').forEach(b => b.classList.toggle('on', +b.dataset.w === win));
}

function setStatus(ok, text){
  $('dot').className = 'dot ' + (ok === 'live' ? 'live' : ok === 'off' ? 'off' : '');
  $('statustxt').textContent = text;
}

const esc = v => String(v == null ? '' : v).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Systemnamen: Klick kopiert den Namen in die Zwischenablage (zum Einfügen in die Galaxiekarte im Spiel)
const SYSH = (n, html) => n ? '<span class="cp" data-cp="' + esc(n) + '" title="Klicken: Systemname kopieren">' + (html == null ? esc(n) : html) + '</span>' : (html == null ? '' : html);
const SYS = n => SYSH(n);
function renderSystem(sys){
  const info = $('sysinfo'), fac = $('factions');
  if (!sys){
    $('sysname').textContent = 'Unbekannt';
    info.innerHTML = '';
    fac.innerHTML = '<div class="empty">Noch kein System im Journal. Springe oder lade das Spiel.</div>';
    return;
  }
  $('sysname').textContent = sys.name;
  let station = sys.station;
  if (station && sys.station_type === 'FleetCarrier') station += ' (Flottenträger)';
  const rows = [
    ['Zugehörigkeit', sys.allegiance], ['Regierung', sys.government],
    ['Wirtschaft', sys.economy + (sys.economy2 && sys.economy2 !== sys.economy ? ' / ' + sys.economy2 : '')],
    ['Sicherheit', sys.security], ['Bevölkerung', fmt(sys.population)],
    ['Kontrolle', sys.controlling ? sys.controlling + (sys.controlling_state ? ' (' + sys.controlling_state + ')' : '') : ''],
    ['Station', station], ['Macht', sys.power]
  ].filter(r => r[1] !== '' && r[1] != null);
  info.innerHTML = rows.map(r => '<div class="row"><span>' + esc(r[0]) + '</span><span>' + esc(r[1]) + '</span></div>').join('');

  if (!sys.factions.length){
    fac.innerHTML = '<div class="empty">' + (sys.population === 0
      ? 'Unbewohntes System. Hier gibt es keine Fraktionen.'
      : 'Keine Fraktionsdaten im Journal. Springe erneut in das System.') + '</div>';
    return;
  }
  let h = '<div class="fachead"><span>Fraktion</span><span>Status</span><span>Einfluss</span><span style="text-align:right">Ruf</span></div>';
  h += sys.factions.map(f => {
    const states = f.active.length ? f.active.join(', ') : (f.state || '-');
    const extra = [];
    if (f.pending.length) extra.push('Droht: ' + f.pending.join(', '));
    if (f.recovering.length) extra.push('Klingt ab: ' + f.recovering.join(', '));
    const rc = f.reputation > 0 ? 'pos' : f.reputation < 0 ? 'neg' : 'zero';
    return '<div class="fac">' +
      '<div class="fn">' + esc(f.name) + (f.controlling ? '<span class="tag">Kontrolle</span>' : '') +
        (f.government ? '<small>' + esc(f.government) + '</small>' : '') + '</div>' +
      '<div class="fs">' + esc(states) + (extra.length ? '<small>' + esc(extra.join(' | ')) + '</small>' : '') + '</div>' +
      '<div class="inf"><div class="track"><div class="fillbar" style="width:' + Math.min(100, f.influence) + '%"></div></div>' +
        '<b>' + f.influence.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1}) + ' %</b></div>' +
      '<div class="rep ' + rc + '">' + (f.reputation > 0 ? '+' : '') + f.reputation + '</div></div>';
  }).join('');
  if (sys.conflicts.length){
    h += sys.conflicts.map(c => '<div class="conf">' + esc(c.type || 'Konflikt') + (c.status ? ' (' + esc(c.status) + ')' : '') + ': <span>' +
      esc(c.f1) + ' ' + c.w1 + ' : ' + c.w2 + ' ' + esc(c.f2) + '</span></div>').join('');
  }
  fac.innerHTML = h;
}

function render(r){
  $('net').textContent   = fmt(r.rate_net);
  $('gross').textContent = fmt(r.rate_gross);
  $('pace').textContent  = fmt(r.win_rate);
  $('netsub').textContent   = 'Gesamt ' + sgn(r.net) + ' Cr';
  $('grosssub').textContent = 'Einnahmen ' + fmt(r.income) + ' Cr';
  $('pacesub').textContent  = 'Hochgerechnet aus den letzten ' + r.win_min + ' Min.';
  $('winlbl').textContent = r.win_min + ' Min';
  $('jwinlbl').textContent = 'Tempo ' + r.win_min + ' Min';

  $('jumps').textContent = r.jumps;
  $('dist').textContent  = r.jump_dist.toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1}) + ' Ly';
  $('avg').textContent   = r.jumps ? (r.jump_dist / r.jumps).toLocaleString('de-DE',{minimumFractionDigits:1,maximumFractionDigits:1}) + ' Ly' : '-';
  $('jph').textContent   = r.jumps_per_hour.toFixed(1).replace('.',',');
  $('jwin').textContent  = r.win_jumps_per_hour.toFixed(1).replace('.',',');
  $('cj').textContent    = r.carrier_jumps;

  $('elapsed').textContent = dur(r.elapsed_s);
  $('start').textContent = new Date(r.start_ts).toLocaleTimeString('de-DE');
  $('cmdr').textContent = r.commander || '-';
  $('inc').textContent = fmt(r.income) + ' Cr';
  $('exp').textContent = fmt(r.expense) + ' Cr';
  $('netall').textContent = sgn(r.net) + ' Cr';
  $('live').textContent = r.live ? 'Läuft' : 'Beendet';

  // Kontostand
  const bal = $('balance');
  if (r.balance != null && r.start_balance != null){
    const diff = r.balance - r.start_balance;
    bal.innerHTML = '<div class="rows">' +
      '<div class="row"><span>Start</span><span>' + fmt(r.start_balance) + ' Cr</span></div>' +
      '<div class="row"><span>Jetzt</span><span>' + fmt(r.balance) + ' Cr</span></div>' +
      '<div class="row"><span>Differenz</span><span>' + sgn(diff) + ' Cr</span></div>' +
      '<div class="row"><span>Pro Stunde</span><span>' + sgn(diff / r.hours) + ' Cr</span></div></div>';
  } else {
    bal.innerHTML = '<div class="empty">' + (r.start_balance != null
      ? 'Status.json nicht verfügbar. Startkonto ' + fmt(r.start_balance) + ' Cr'
      : 'Keine Daten') + '</div>';
  }

  // Kategorien
  const entries = Object.entries(r.cats).sort((a,b) => b[1]-a[1]);
  const box = $('cats');
  if (!entries.length){
    box.innerHTML = '<div class="empty">Noch keine Credit-Ereignisse in dieser Session</div>';
  } else {
    const max = Math.max(...entries.map(e => Math.abs(e[1])));
    box.innerHTML = entries.map(([k,v]) =>
      '<div class="cat"><span class="lbl">' + k.replace(/&/g,'&amp;') + '</span>' +
      '<div class="track"><div class="fillbar ' + (v<0?'neg':'') + '" style="width:' + (Math.abs(v)/max*100).toFixed(1) + '%"></div></div>' +
      '<span class="val ' + (v<0?'neg':'pos') + '">' + sgn(v) + ' Cr</span></div>').join('');
  }
  $('jname').textContent = r.journal;
  renderSystem(r.system);
  renderBodies(r.bodies);
  renderRings(r.bodies);
  const newSys = r.system ? r.system.name : '';
  if (newSys && newSys !== window.__sys && window.__saFollow){ window.__saManual = false; window.__sys = newSys; saGoCurrent(); }
  window.__sys = newSys;
  renderAll(r.allstats);
}

async function poll(){
  if (window.__off) return;
  markButtons();
  if (!$('tab-log').hidden) loadLog();
  if (!$('tab-market').hidden) loadMarket(false);
  if (!$('tab-cockpit').hidden || !$('tab-maint').hidden) loadCockpit();
  if (!$('tab-system').hidden && (++stnTick % 3 === 1)) loadSysStn();
  const ct = crVisible();
  if (ct && (++crTick % 3 === 0)) loadCr(ct, false);
  try{
    const res = await fetch('/api/stats?window=' + win, {cache:'no-store'});
    const r = await res.json();
    if (r.error){ setStatus('off', r.error); $('conn').textContent = 'Fehler'; $('jdwarn').hidden = !r.jd; if (r.jd) $('jdwtxt').textContent = r.error; return; }
    $('jdwarn').hidden = true;
    render(r);
    try { SND.feed(r.feed || []); } catch(e) {}
    setStatus(r.live ? 'live' : 'idle', r.live ? 'Journal aktiv - Daten werden live gelesen' : 'Journal inaktiv - letzte Session wird angezeigt');
    $('conn').textContent = 'Online';
    $('upd').textContent = new Date().toLocaleTimeString('de-DE');
  }catch(e){
    setStatus('off', 'Keine Verbindung zum Skript - läuft edcj.py noch?');
    $('conn').textContent = 'Getrennt';
  }
}
let SET = {hidden: [], theme: 'startrek'};
try { const c0 = JSON.parse(localStorage.getItem('edl_set') || 'null'); if (c0 && Array.isArray(c0.hidden)) SET = {hidden: c0.hidden, theme: c0.theme || 'startrek'}; } catch(e) {}
const tabHidden = t => t !== 'settings' && SET.hidden.includes(t);
const firstVisible = () => TABS.find(n => !tabHidden(n)) || 'settings';
const TABS = ['cockpit','maint','stats','system','bodies','all','kampf','mining','missions','carrier','bgs','bio','gaps','shots','profil','replay','akte','lmis','lmil','rueck','kolo','kolm','karriere','sess','team','kana','sakte','bilanz','flotte','market','gear','ana','sana','ware','notes','map','hot','log','search','off','settings'];
const GROUPS = [
  {id:'cockpit', name:'Cockpit', c:'orange', subs:[{tab:'cockpit', label:'Live'}, {tab:'missions', label:'Missionen'}, {tab:'maint', label:'Wartung'}, {tab:'rueck', label:'Rückblick'}]},
  {id:'nav', name:'Navigation', c:'lilac', subs:[{tab:'system', label:'System'}, {tab:'sana', label:'Diplomatie'}, {tab:'bgs', label:'Fraktions-Verlauf'}, {tab:'bodies', label:'Planeten & Ringe'}, {tab:'hot', label:'Hotspots'}, {tab:'bio', label:'Bio-Atlas'}, {tab:'map', label:'Reisekarte'}]},
  {id:'market', name:'Markt', c:'tan', subs:[{tab:'market', label:'Lokaler Markt'}, {tab:'ware', sec:'sec-ware', label:'Warenfinder'}, {tab:'ware', sec:'sec-trades', label:'Beste Trades'},
    {tab:'ware', sec:'sec-loops', label:'Rundkurse'}, {tab:'ware', sec:'sec-cmp', label:'Marktvergleich'}, {tab:'sakte', label:'Stationsakte'}, {tab:'ana', label:'Analyse'}, {tab:'bilanz', cs:'wares', label:'Handelsbuch'}]},
  {id:'colony', name:'Kolonien', c:'sky', subs:[{tab:'kolo', label:'Im Bau'}, {tab:'kolm', label:'Meine Kolonien'}]},
  {id:'fleet', name:'Schiff', c:'peach', subs:[{tab:'gear', label:'Ausrüstung kaufen'}, {tab:'flotte', label:'Meine Flotte'}, {tab:'carrier', label:'Fleet Carrier'}]},
  {id:'career', name:'Karriere', c:'red', subs:[{tab:'karriere', label:'Laufbahn'}, {tab:'sess', label:'Sitzungen'}, {tab:'team', label:'Team'}, {tab:'kana', label:'Kampfanalyse'}, {tab:'kampf', label:'Kampf'}, {tab:'mining', label:'Mining'}, {tab:'profil', label:'Spielstil'}]},
  {id:'akte', name:'Dienstakte', c:'lilac', subs:[{tab:'akte', label:'Personalakte'}, {tab:'lmis', label:'Journey-Missionen'}, {tab:'lmil', label:'Meilensteine'}]},
  {id:'fin', name:'Finanzen', c:'orange', subs:[{tab:'stats', label:'Tempo'}, {tab:'bilanz', label:'Bilanz'}]},
  {id:'logb', name:'Logbuch', c:'sky', subs:[{tab:'log', label:'Captains Log'}, {tab:'search', label:'Suche'}, {tab:'notes', label:'Notizen'}, {tab:'gaps', label:'Lücken'}, {tab:'shots', label:'Galerie'}, {tab:'replay', label:'Flugschreiber'}, {tab:'all', label:'Alle Daten'}]},
  {id:'set', name:'Settings', c:'lilac', subs:[{tab:'settings', label:'Einstellungen'}, {tab:'off', label:'Offline'}]}
];
let SD = {days: '0', d: null};
try { SD.days = localStorage.getItem('edl_sdays') || '0'; } catch(e) {}
const VIEW = {tab:'', cs:'', sec:'', grp:''};
const SH = {rows: [], i: -1, fav: false, tm: 0};
const PF = {d: null, week: '', weeks: 12, mode: 'int'};
const subKey = u => u.tab + '|' + (u.cs || '') + '|' + (u.sec || '');
const subHidden = u => tabHidden(u.tab);
const grpVisible = g => g.subs.some(u => !subHidden(u));
function lastSubGet(){ try { return JSON.parse(localStorage.getItem('edl_sub') || '{}'); } catch(e) { return {}; } }
function lastSubSet(g, u){ try { const m = lastSubGet(); m[g] = subKey(u); localStorage.setItem('edl_sub', JSON.stringify(m)); } catch(e) {} }
function curSub(g){
  const sel = g.subs.filter(u => u.tab === VIEW.tab);
  return sel.find(u => (u.cs || '') === VIEW.cs && (u.sec || '') === VIEW.sec) || sel.find(u => (u.sec || '') === VIEW.sec && !u.cs) || sel[0] || null;
}
function curGroup(){
  const byId = GROUPS.find(g => g.id === VIEW.grp && g.subs.some(u => u.tab === VIEW.tab));
  return byId || GROUPS.find(g => g.subs.some(u => u.tab === VIEW.tab)) || GROUPS[0];
}
function renderNav(){
  const cg = curGroup();
  $('grpbtns').innerHTML = GROUPS.map((g, i) => grpVisible(g) ?
    '<button class="btn' + (g.id === cg.id ? ' on' : '') + '" data-grp="' + g.id + '" style="--c:var(--' + g.c + ')" title="Taste ' + (i + 1) + '">' + esc(g.name) + '</button>' : '').join('');
  const cu = curSub(cg), subs = cg.subs.filter(u => !subHidden(u));
  $('subnav').innerHTML = subs.length > 1 ? subs.map(u => '<button data-su="' + esc(subKey(u)) + '" class="' + (cu && subKey(u) === subKey(cu) ? 'on' : '') + '">' + esc(u.label) + '</button>').join('') : '';
}
function openSub(g, u){
  lastSubSet(g.id, u);
  showTab(u.tab, u.cs, u.sec, g.id);
}
$('grpbtns').addEventListener('click', e => {
  const b = e.target.closest('button[data-grp]'); if (!b) return;
  const g = GROUPS.find(x => x.id === b.dataset.grp); if (!g) return;
  const last = lastSubGet()[g.id];
  const u = g.subs.find(x => subKey(x) === last && !subHidden(x)) || g.subs.find(x => !subHidden(x));
  if (u) openSub(g, u);
});
$('subnav').addEventListener('click', e => {
  const b = e.target.closest('button[data-su]'); if (!b) return;
  const g = curGroup(), u = g.subs.find(x => subKey(x) === b.dataset.su);
  if (u) openSub(g, u);
});
document.addEventListener('keydown', e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const tg = (e.target && e.target.tagName) || '';
  if (/INPUT|TEXTAREA|SELECT/.test(tg) || (e.target && e.target.isContentEditable)) return;
  if (/^[1-9]$/.test(e.key)){
    const g = GROUPS[+e.key - 1]; if (g && grpVisible(g)){ const bt = document.querySelector('button[data-grp="' + g.id + '"]'); if (bt) bt.click(); }
  } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft'){
    const g = curGroup(), subs = g.subs.filter(u => !subHidden(u)), cu = curSub(g);
    const i = subs.findIndex(u => cu && subKey(u) === subKey(cu));
    const n = subs[i + (e.key === 'ArrowRight' ? 1 : -1)];
    if (n){ openSub(g, n); e.preventDefault(); }
  }
});
const SND = (function(){
  const KEY = 'edl_snd'; let cfg = {beep:false, voice:false, vol:40, ev:{ring:1, mapped:1, jump:1, dock:1, bio:1, mission:1}};
  try { Object.assign(cfg, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch(e) {}
  let ac = null, seen = null;
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(cfg)); } catch(e) {} };
  const ctx = () => { try { ac = ac || new (window.AudioContext || window.webkitAudioContext)(); if (ac.state === 'suspended') ac.resume(); } catch(e) { ac = null; } return ac; };
  function tone(f, t0, d, v){
    const a = ctx(); if (!a) return;
    const o = a.createOscillator(), g = a.createGain();
    o.type = 'sine'; o.frequency.value = f;
    const t = a.currentTime + t0, vol = Math.max(0.0001, (cfg.vol / 100) * 0.25 * (v || 1));
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + d);
    o.connect(g); g.connect(a.destination); o.start(t); o.stop(t + d + 0.02);
  }
  const beep = () => { if (!cfg.beep) return; tone(1400, 0, 0.07); tone(1900, 0.08, 0.09, 0.8); };
  function say(txt){
    if (!cfg.voice || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(window.tr(txt)); u.lang = window.EDCJ_LANG === 'en' ? 'en-US' : 'de-DE'; u.volume = Math.min(1, cfg.vol / 100 * 1.4);
    const v = speechSynthesis.getVoices().find(x => /^de/i.test(x.lang)); if (v) u.voice = v;
    speechSynthesis.speak(u);
  }
  function feed(list){
    if (seen === null){ seen = new Set(list.map(x => x.id)); return; }  // erster Abruf: alte Ereignisse nicht vorlesen
    list.forEach(x => { if (seen.has(x.id)) return; seen.add(x.id); if (cfg.ev[x.k]) { say(x.t); } });
  }
  const NAMES = {ring:'Ring gescannt', mapped:'Oberfläche kartiert', jump:'Sprung', dock:'Andocken', bio:'Bio-Analyse', mission:'Mission'};
  function init(){
    const b = $('sndbeep'); if (!b) return;
    b.checked = !!cfg.beep; $('sndvoice').checked = !!cfg.voice; $('sndvol').value = cfg.vol;
    $('sndev').innerHTML = Object.keys(NAMES).map(k => '<label style="margin-right:14px;white-space:nowrap"><input type="checkbox" data-ev="' + k + '"' + (cfg.ev[k] ? ' checked' : '') + '> ' + NAMES[k] + '</label>').join('');
    $('sndev').querySelectorAll('input').forEach(i => i.addEventListener('change', () => { cfg.ev[i.dataset.ev] = i.checked ? 1 : 0; save(); }));
    b.addEventListener('change', () => { cfg.beep = b.checked; save(); beep(); });
    $('sndvoice').addEventListener('change', e => { cfg.voice = e.target.checked; save(); say('Sprachausgabe aktiv'); });
    $('sndvol').addEventListener('input', e => { cfg.vol = +e.target.value; save(); });
    $('sndtest').addEventListener('click', () => { const was = cfg.beep; cfg.beep = true; beep(); cfg.beep = was; say('Ring gescannt'); });
    if (!window.speechSynthesis) $('sndinfo').textContent = 'Dieser Browser hat keine Sprachausgabe; Pieptöne gehen trotzdem.';
  }
  return {beep, feed, init};
})();
document.addEventListener('DOMContentLoaded', () => SND.init());
if (document.readyState !== 'loading') SND.init();
const LM = {inited:false, timer:null};
function lmLeft(ends){
  const ms = Date.parse(ends) - Date.now(); if (ms <= 0) return 'abgelaufen';
  const h = ms / 3600000; return h < 48 ? 'noch ' + Math.floor(h) + ' h ' + Math.floor((h % 1) * 60) + ' min' : 'noch ' + Math.floor(h / 24) + ' Tage';
}
function lmCard(m, arch){
  const tag = {daily:'TÄGLICH', weekly:'WÖCHENTLICH', chapter:'WOCHENKAPITEL', monthly:'MONATLICH', random:'ZUFALL'}[m.scope] || m.scope;
  const st = {done:'<b class="good">ERFÜLLT</b>', expired:'<b class="warn">ABGELAUFEN</b>', abandoned:'<span class="mut">AUFGEGEBEN</span>'}[m.status] || '';
  const ob = m.objs.map(o => { const pc = Math.min(100, o.target ? o.val / o.target * 100 : 0);
    return '<div style="margin:6px 0"><div>' + (pc >= 100 ? '✔ ' : '') + esc(o.label) + ' <span class="mut">(' + fmt(Math.min(o.val, o.target)) + ' / ' + fmt(o.target) + ')</span></div><div class="bar"><i style="width:' + pc.toFixed(0) + '%"></i></div></div>'; }).join('');
  return '<div style="border-left:6px solid var(--lilac);padding:6px 12px;margin:10px 0;background:#111"><div><b>' + esc(m.title) + '</b> <span class="mut">· ' + tag + (m.diff ? ' · ' + esc(m.diff) : '') + ' · ' + m.dp + ' DP</span> ' +
    (arch ? st + ' <span class="mut">' + new Date(m.done_ts || m.ends).toLocaleDateString('de-DE') + '</span>' : '<span class="mut" style="float:right">' + lmLeft(m.ends) + '</span>') + '</div>' +
    '<div class="mut" style="font-size:15px">' + esc(m.brief || '') + '</div>' + ob +
    (!arch && m.scope === 'random' ? '<button class="xbtn" data-lmab="' + esc(m.id) + '" style="background:var(--red);font-size:14px">Aufgeben</button>' : '') + '</div>';
}
async function lmLoad(post){
  try {
    const r = await (await fetch('/api/lm', post ? {method:'POST', headers:{'X-EDCJ':'1'}, body: JSON.stringify(post)} : {cache:'no-store'})).json();
    if (r.error){ $('lminfo').textContent = r.error; return; }
    $('lmmeta').textContent = r.dp + ' Dienstpunkte';
    $('lmact').innerHTML = r.active.map(m => lmCard(m, false)).join('') || '<div class="empty">Keine aktiven Aufträge</div>';
    $('lmarc').innerHTML = r.archive.map(m => lmCard(m, true)).join('') || '<div class="empty">Noch nichts im Archiv</div>';
  } catch(e) { $('lmmeta').textContent = 'Keine Verbindung'; }
}
function lmInit(){
  if (LM.inited) return; LM.inited = true;
  $('lmnew').onclick = () => lmLoad({op:'random', diff:$('lmdiff').value});
  $('lmact').addEventListener('click', e => { const b = e.target.closest('button[data-lmab]'); if (b && confirm('Zufallsmission aufgeben?')) lmLoad({op:'abandon', id:b.dataset.lmab}); });
  LM.timer = setInterval(() => { if (!$('tab-lmis').hidden) lmLoad(); }, 10000);
}
const RP = {sess:[], d:null, t0:0, t1:1, cur:0, timer:null, inited:false};
function rpTs(s){ return Date.parse(s); }
async function rpLoadList(){
  const sel = $('rpsel');
  const r = await (await fetch('/api/career?op=replay_list', {cache:'no-store'})).json();
  RP.sess = r.sessions || [];
  sel.innerHTML = RP.sess.map((x, i) => '<option value="' + i + '">' + new Date(x.first).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', year:'2-digit', hour:'2-digit', minute:'2-digit'}) +
    ' · ' + x.jumps + ' Sprünge, ' + x.kills + ' Abschüsse, ' + x.trades + ' Handel</option>').join('');
  if (RP.sess.length) rpLoad(0); else $('rpmeta').textContent = 'Keine Sessions';
}
async function rpLoad(i){
  rpStop();
  const x = RP.sess[i]; if (!x) return;
  const d = await (await fetch('/api/career?op=replay&file=' + encodeURIComponent(x.file), {cache:'no-store'})).json();
  if (d.error){ $('rpmeta').textContent = d.error; return; }
  RP.d = d; RP.t0 = rpTs(d.first); RP.t1 = Math.max(rpTs(d.last), RP.t0 + 1);
  d.events.forEach(e => e._t = rpTs(e.ts)); d.path.forEach(p => p._t = rpTs(p[0]));
  RP.cur = RP.t0; $('rpbar').value = 0; $('rpmeta').textContent = d.events.length + ' Ereignisse · ' + d.path.length + ' Positionen';
  rpMarks(); rpDraw(true);
}
function rpMarks(){
  const cv = $('rpmark'); if (!cv || !RP.d) return;
  const dpr = window.devicePixelRatio || 1, r = cv.getBoundingClientRect(); cv.width = Math.round(r.width * dpr); cv.height = Math.round(26 * dpr);
  const g = cv.getContext('2d'), css = getComputedStyle(document.documentElement);
  const C = {jump:'--sky', dock:'--orange', kill:'--red', sell:'--peach', buy:'--tan', land:'--lilac', bio:'--blue', map:'--blue', intd:'--red'};
  RP.d.events.forEach(e => {
    const x = (e._t - RP.t0) / (RP.t1 - RP.t0) * cv.width;
    g.fillStyle = (css.getPropertyValue(C[e.k] || '--lilac') || '#ccc').trim(); g.fillRect(x, 0, Math.max(2, dpr * 2), cv.height);
  });
}
function rpDraw(full){
  const d = RP.d; if (!d) return;
  const t = RP.cur, n = d.events.filter(e => e._t <= t);
  $('rptime').textContent = new Date(t).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit'});
  const cr = n.reduce((a, e) => a + (e.cr || 0) * (e.k === 'kill' ? 0 : 1), 0);
  $('rpkpi').textContent = n.filter(e => e.k === 'jump').length + ' Sprünge · ' + n.filter(e => e.k === 'dock').length + ' Stationen · ' + n.filter(e => e.k === 'kill').length + ' Abschüsse · Handel ' + fmt(cr) + ' Cr';
  const L = $('rplist');
  L.innerHTML = n.slice(-60).reverse().map(e => '<div style="padding:2px 0"><span class="mut">' + new Date(e._t).toLocaleTimeString('de-DE') + '</span> ' + esc(e.t) + '</div>').join('') || '<div class="empty">Noch nichts passiert</div>';
  // Karte (Draufsicht x/z), Pfad bis jetzt hell, Rest blass
  const cv = $('rpcv'), dpr = window.devicePixelRatio || 1, r = cv.getBoundingClientRect();
  cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
  const g = cv.getContext('2d'), css = getComputedStyle(document.documentElement);
  const P = d.path.filter(p => p[2] != null);
  if (!P.length){ g.fillStyle = '#888'; g.font = (15 * dpr) + 'px sans-serif'; g.fillText('Keine Koordinaten in dieser Session.', 14, 28); return; }
  let x0 = Math.min(...P.map(p => p[2])), x1 = Math.max(...P.map(p => p[2])), z0 = Math.min(...P.map(p => p[4])), z1 = Math.max(...P.map(p => p[4]));
  const pad = 24 * dpr, sw = Math.max(x1 - x0, 20), sz = Math.max(z1 - z0, 20), k = Math.min((cv.width - 2 * pad) / sw, (cv.height - 2 * pad) / sz);
  const ox = (cv.width - sw * k) / 2, oz = (cv.height - sz * k) / 2;
  const X = p => ox + (p[2] - x0) * k, Z = p => cv.height - (oz + (p[4] - z0) * k);
  const sky = (css.getPropertyValue('--sky') || '#8cf').trim(), hot = (css.getPropertyValue('--orange') || '#fa0').trim();
  g.lineWidth = 2 * dpr; g.strokeStyle = 'rgba(150,150,150,.35)'; g.beginPath(); P.forEach((p, i) => i ? g.lineTo(X(p), Z(p)) : g.moveTo(X(p), Z(p))); g.stroke();
  const done = P.filter(p => p._t <= t);
  g.strokeStyle = sky; g.beginPath(); done.forEach((p, i) => i ? g.lineTo(X(p), Z(p)) : g.moveTo(X(p), Z(p))); g.stroke();
  done.forEach(p => { g.fillStyle = sky; g.beginPath(); g.arc(X(p), Z(p), 3 * dpr, 0, 7); g.fill(); });
  const cur = done[done.length - 1] || P[0];
  g.strokeStyle = hot; g.lineWidth = 3 * dpr; g.beginPath(); g.arc(X(cur), Z(cur), 10 * dpr, 0, 7); g.stroke();
  g.fillStyle = '#fff'; g.font = (14 * dpr) + 'px sans-serif'; g.fillText(cur[1] || '', X(cur) + 14 * dpr, Z(cur) - 8 * dpr);
}
function rpStop(){ if (RP.timer){ clearInterval(RP.timer); RP.timer = null; } if ($('rpplay')) $('rpplay').textContent = '▶ Abspielen'; }
function rpInit(){
  if (RP.inited) return; RP.inited = true;
  $('rpsel').onchange = e => rpLoad(+e.target.value);
  $('rpbar').oninput = e => { RP.cur = RP.t0 + (RP.t1 - RP.t0) * (+e.target.value / 1000); rpDraw(); };
  $('rpplay').onclick = () => {
    if (RP.timer){ rpStop(); return; }
    if (RP.cur >= RP.t1) RP.cur = RP.t0;
    $('rpplay').textContent = '⏸ Pause';
    RP.timer = setInterval(() => {
      RP.cur += (+$('rpspd').value) * 60000 / 10;
      if (RP.cur >= RP.t1){ RP.cur = RP.t1; rpStop(); }
      $('rpbar').value = Math.round((RP.cur - RP.t0) / (RP.t1 - RP.t0) * 1000); rpDraw();
    }, 100);
  };
  window.addEventListener('resize', () => { if (!$('tab-replay').hidden){ rpMarks(); rpDraw(); } });
  rpLoadList();
}
function showTab(t, cs, sec, grp){
  if (VIEW.tab && VIEW.tab !== t) SND.beep();
  if (t === 'lmis') setTimeout(() => { lmInit(); lmLoad(); }, 0);
  if (t === 'replay') setTimeout(() => { rpInit(); if (RP.d){ rpMarks(); rpDraw(); } }, 0);
  if (!TABS.includes(t) || tabHidden(t)) t = firstVisible();
  TABS.forEach(n => { $('tab-' + n).hidden = n !== t; });
  document.querySelectorAll('button[data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === t));
  VIEW.tab = t; VIEW.cs = cs || ''; VIEW.sec = sec || ''; VIEW.grp = grp || '';
  if (t === 'ware') ['sec-ware', 'sec-trades', 'sec-loops', 'sec-cmp'].forEach(id => { $(id).hidden = !!sec && id !== sec; });
  if (cs && window.__cr && CR[t] && crSub[t] !== cs){ crSub[t] = cs; if ($('crch-' + t)) crChips(t); }
  renderNav();
  try { history.replaceState(null, '', '#' + t + (cs ? '/' + cs : sec ? '/' + sec : '')); } catch(e) {}
  if (t === 'log') loadLog();
  if (window.__cr && CR[t]) loadCr(t, true);
  if ((t === 'cockpit' || t === 'maint') && window.__cr) loadCockpit();
  if (t === 'system' && window.__cr) loadSysStn();
  if (t === 'search') setTimeout(() => $('sq').focus(), 50);
  if (t === 'market') loadMarket(true);
  if (t === 'map') loadMap();
  if (t === 'hot') loadHot();
  if (t === 'gear') loadGear();
  if (t === 'ana') loadAna();
  if (t === 'sana') loadSa();
  if (t === 'ware'){ loadWare(); loadTrades(); loadLoops(); loadCmpSt(); }
  if (t === 'notes') loadNotes();
  if (t === 'shots') loadShots();
  if (t === 'profil') loadProfil();
  if (t === 'sess' || t === 'team' || t === 'kana') loadSess();
  if (t === 'sakte') loadSakte();
}
document.querySelectorAll('button[data-tab]').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
(function(){
  const h = (location.hash || '').slice(1).split('/'), t = h[0], x = h[1] || '';
  const g = GROUPS.find(gr => gr.subs.some(u => u.tab === t && (!x || u.cs === x || u.sec === x)));
  const u = g && g.subs.find(u => u.tab === t && (!x || u.cs === x || u.sec === x));
  showTab(t, u && u.cs, u && u.sec, g && g.id);
})();

function ringLabel(x, r){
  const kind = /Belt$/.test(r.n || '') ? 'Gürtel' : 'Ring', letter = String(r.n || '').replace(/\s*(Ring|Belt)$/, '');
  return (x.full || x.name) + ' \u00b7 ' + kind + ' ' + letter;
}
function ringRow(r, label){
  const hot = Object.entries(r.hot || {});
  return '<div class="bod rr"><div class="bn">' + esc(label) + '</div>' +
    '<div class="bt">' + esc(r.cls ? 'Ring: ' + r.cls : 'Ring') + '</div>' +
    '<div>' + esc(r.reserve ? 'Reserven: ' + r.reserve : '-') + '</div>' +
    '<div>' + (hot.length ? '<span class="good">Hotspots: ' + esc(hot.map(([k, v]) => k + ' ' + v).join(', ')) + '</span>' : '<span class="mut">keine Hotspots bekannt</span>') + '</div>' +
    '<div>' + (r.scanned ? (r.mapped ? '<span class="good">Mit DSS gescannt</span>' : 'Gescannt') : '<span class="mut">' + (r.orphan ? 'Planet nicht gescannt' : 'Nur aus Elternscan') + '</span>') + '</div></div>';
}
function renderRings(b){
  const rows = []; let hs = 0;
  ((b && b.list) || []).forEach(x => (x.rings || []).forEach(r => {
    rows.push(ringRow(r, ringLabel(x, r)));
    hs += Object.values(r.hot || {}).reduce((a, v) => a + v, 0);
  }));
  $('ringsum').textContent = rows.length + ' Ringe | Hotspots: ' + hs;
  $('ringlist').innerHTML = rows.length
    ? '<div class="bhead"><span>Ring</span><span>Typ</span><span>Reserven</span><span>Hotspots</span><span>Status</span></div>' + rows.join('')
    : '<div class="empty">Noch keine Ringe gescannt</div>';
}

function renderBodies(b){
  if (!b || !b.list.length){
    $('bsum').textContent = '-';
    $('bodies').innerHTML = '<div class="empty">Noch keine Körper gescannt. Nutze den Systemscanner (FSS), dann erscheinen sie hier.</div>';
    return;
  }
  const bio = b.list.reduce((a, x) => a + x.bio, 0);
  $('bsum').textContent = b.scanned + (b.total ? ' von ' + b.total : '') + ' gescannt' + (b.all ? ' (vollständig)' : '') + ' | Biosignale: ' + bio + (b.prior ? ' | schon ' + b.prior + 'x hier, zuletzt ' + new Date(b.last).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'}) : '') + (b.from_log ? ' | ' + b.from_log + ' aus Logbuch' : '');
  const yes = (t) => '<span class="good">' + t + '</span>', no = (t) => '<span class="mut">' + t + '</span>';
  let h = '<div class="bhead"><span>Körper</span><span>Art</span><span>Eigenschaften</span><span>Signale</span><span>Besucht</span></div>';
  h += b.list.map(x => {
    const props = [];
    if (x.landable) props.push('landbar');
    if (x.terra) props.push('terraformbar');
    if (x.atmo && !/no atmosphere|keine/i.test(x.atmo)) props.push(x.atmo);
    if (x.grav != null) props.push(x.grav.toLocaleString('de-DE') + ' g');
    const sig = [];
    if (x.bio) sig.push('<span class="good">Bio ' + x.bio + '</span>');
    if (x.geo) sig.push('Geologisch ' + x.geo);
    if (x.mining) sig.push('Abbaustandorte ' + x.mining);
    if (x.human) sig.push('Mensch ' + x.human);
    if (x.other) sig.push('Andere ' + x.other);
    const vis = x.disc === false ? yes('Erstentdeckung') : x.disc === true ? '<span class="warn">Schon entdeckt</span>' : no('Unbekannt');
    const map = x.mine ? yes('Von dir kartiert') : x.mapped_before === true ? 'Bereits kartiert' : x.mapped_before === false ? no('Unkartiert') : '';
    const foot = !x.landable ? '' : x.foot === false ? yes('Footfall frei') : x.foot === true ? 'Footfall vergeben' : '';
    const extra = '';
    return '<div class="bod"><div class="bn">' + esc(x.name) + (x.dist != null ? '<small>' + Math.round(x.dist).toLocaleString('de-DE') + ' Ls</small>' : '') + (x.old ? '<small>aus Logbuch (früherer Besuch)</small>' : '') + '</div>' +
      '<div class="bt">' + esc(x.cls || (x.placeholder ? 'Nicht gescannt (nur Ring bekannt)' : 'Nur Signale, nicht gescannt')) + '</div>' +
      '<div>' + esc(props.join(', ') || '-') + extra + '</div>' +
      '<div>' + (sig.join(' | ') || '<span class="mut">-</span>') + (x.organics ? '<small>' + x.organics + ' Probe(n) analysiert</small>' : '') + '</div>' +
      '<div>' + vis + '<small>' + [map, foot].filter(Boolean).join(' | ') + '</small></div></div>' + (x.rings || []).map(r => ringRow(r, '↳ ' + ringLabel({name: ''}, r).replace(/^\s*\u00b7\s*/, ''))).join('');
  }).join('');
  $('bodies').innerHTML = h;
}

function renderAll(secs){
  const cols = ['var(--orange)','var(--lilac)','var(--blue)','var(--sky)','var(--tan)','var(--peach)','var(--red)'];
  $('tab-all').innerHTML = secs.map((sec, i) =>
    '<section class="panel" style="--c:' + cols[i % cols.length] + '"><div class="ph"><span>' + esc(sec.title) + '</span><span>&nbsp;</span></div>' +
    '<div class="pb"><div class="rows">' + sec.rows.map(r => '<div class="row"><span>' + esc(r[0]) + '</span><span>' + esc(r[1]) + '</span></div>').join('') +
    '</div></div></section>').join('');
}

const logOpen = new Set(); let logLast = '';
async function loadLog(){
  try{
    const d = await (await fetch('/api/log', {cache:'no-store'})).json();
    const blocks = []; let cur = null;
    d.text.split('\n').forEach(l => {
      if (l.startsWith('## ')) { cur = {t: l.slice(3), rows: []}; blocks.push(cur); }
      else if (cur && l.trim()) cur.rows.push(l);
    });
    $('logmeta').textContent = blocks.length + ' Sessions | ' + d.path.split('/').pop() + (d.error ? ' | Fehler: ' + d.error : '');
    if (!blocks.length){
      $('logbody').innerHTML = '<div class="empty">Noch keine Einträge. Das Log füllt sich, sobald im Journal ein Spiel geladen wird.</div>';
      return;
    }
    if (d.text === logLast) return;
    logLast = d.text;
    $('logbody').innerHTML = blocks.reverse().map(b => '<details class="ls" data-k="' + esc(b.t) + '"' + (logOpen.has(b.t) ? ' open' : '') +
      '><summary><span class="st">' + esc(b.t) + '</span><span class="cnt">' + b.rows.filter(l => /^- \d\d:\d\d /.test(l)).length + ' Einträge</span></summary>' + b.rows.map(l => {
      if (l.startsWith('### ')) return '<div class="lh">' + esc(l.slice(4)) + '</div>';
      const m = l.match(/^- (\d\d:\d\d) (.*)$/), txt = m ? m[2] : l.replace(/^- /, '');
      const cls = /abgeschlossen|Einnahme/.test(txt) ? ' good' : /gescheitert|zerstört/.test(txt) ? ' bad' : '';
      return '<div class="le' + cls + (m ? '' : ' sm') + '"><span class="t">' + (m ? m[1] : '') + '</span><span>' + esc(txt) + '</span></div>';
    }).join('') + '</details>').join('');
  }catch(e){}
}
$('logbody').addEventListener('toggle', ev => {
  const k = ev.target.dataset && ev.target.dataset.k;
  if (k) { ev.target.open ? logOpen.add(k) : logOpen.delete(k); }
}, true);

function dts(iso){ return iso ? new Date(iso).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', year:'2-digit', hour:'2-digit', minute:'2-digit'}) : '-'; }
const nfm = v => (v > 0 ? fmt(v) : '-');
async function mapi(p){ return (await fetch('/api/market?' + new URLSearchParams(p), {cache:'no-store'})).json(); }
function delta(v, mean, sell){
  if (!(v > 0 && mean > 0)) return '';
  const d = (v - mean) / mean * 100, good = sell ? d > 0 : d < 0;
  return '<small class="' + (good ? 'good' : 'mut') + '">' + (d > 0 ? '+' : '') + d.toFixed(1).replace('.', ',') + ' % zum Ø</small>';
}
function padTxt(s){
  if (!s || s.pad_s == null) return 'Landeplattform unbekannt';
  const L = s.pad_l > 0 ? 'Groß' : s.pad_m > 0 ? 'Mittel' : s.pad_s > 0 ? 'Klein' : 'keine';
  return 'Größte Plattform: ' + L + ' (S ' + s.pad_s + ' · M ' + s.pad_m + ' · L ' + s.pad_l + ')';
}
const padShort = s => !s || s.pad_s == null ? '' : ' [' + (s.pad_l > 0 ? 'L' : s.pad_m > 0 ? 'M' : s.pad_s > 0 ? 'S' : '-') + ']';
const stOpts = st => st.map(s => '<option value="' + s.market_id + '">' + esc(s.name + ' (' + s.system + ')' + padShort(s)) + '</option>').join('');

let RANGE = '0';
try { RANGE = localStorage.getItem('edl_range') || '0'; } catch(e) {}
if (!['20', '50', '100', '0'].includes(RANGE)) RANGE = '0';
const distTxt = o => o && o.dist != null ? ' · ' + o.dist.toFixed(1).replace('.', ',') + ' Ly' : ' · Entfernung unbekannt';
function setRange(v){
  RANGE = v;
  try { localStorage.setItem('edl_range', v); } catch(e) {}
  $('ckrange').value = v; $('mkrange').value = v;
  ckLast = '';
  $('mdrange').value = v; $('trrange').value = v;
  if (!$('tab-ware').hidden){ loadTrades(); loadLoops(); }
  loadCockpit(); if (!$('tab-market').hidden) loadSnap($('mksnap').value);
  if (!$('tab-gear').hidden) loadMods();
}
let QTY = '';
try { QTY = localStorage.getItem('edl_qty') || ''; } catch(e) {}
const qtyP = () => QTY && +QTY > 0 ? {qty: String(Math.floor(+QTY))} : {};
function setQty(v){
  QTY = String(v || '').replace(/[^0-9]/g, '');
  try { localStorage.setItem('edl_qty', QTY); } catch(e) {}
  ['trqty', 'mkqty'].forEach(id => { const el = $(id); if (el && el.value !== QTY) el.value = QTY; });
  if (!$('tab-ware').hidden){ loadTrades(); loadLoops(); }
  if (!$('tab-market').hidden) loadSnap($('mksnap').value);
}
const ageCls = iso => iso && (Date.now() - new Date(iso).getTime()) > 72 * 36e5 ? 'warn' : 'mut';
const stand = iso => '<small class="' + ageCls(iso) + '">Stand ' + esc(dts(iso)) + '</small>';
function counter(i){
  const b = mk.best[i.name] || {}, out = [];
  const line = (lbl, o, pr, lim) => {
    const q = mk.cap > 0 ? Math.min(mk.cap, lim, o.qty || 0) : 0;
    return '<div><span class="' + (pr > 0 ? 'good' : 'mut') + '">' + lbl + ': ' + esc(o.station) + ' (' + SYS(o.system) + ')' + distTxt(o) + ' · ' + fmt(o.price) + ' Cr &rarr; ' +
      (pr > 0 ? '+' : '') + fmt(pr) + ' / t' + (q > 0 && pr > 0 ? ' · bei ' + fmt(q) + ' t: +' + fmt(pr * q) + ' Cr' : '') + '</span>' + stand(o.seen) + '</div>';
  };
  // Menge: begrenzt durch Frachtraum bzw. eigene Menge sowie Bestand/Nachfrage auf beiden Seiten
  if (i.sell > 0) out.push(b.buy ? line('Günstigster Einkauf', b.buy, i.sell - b.buy.price, i.demand > 0 ? i.demand : 0) : '<div class="mut">Kein Einkauf anderswo bekannt</div>');
  if (i.buy > 0) out.push(b.sell ? line('Bester Verkauf', b.sell, b.sell.price - i.buy, i.stock > 0 ? i.stock : 0) : '<div class="mut">Kein Verkauf anderswo bekannt</div>');
  return out.join('');
}

/* ---- Lokaler Markt ---- */
const mk = {sig: '', items: [], best: {}, key: 'name', dir: 1, cap: 0};
function marketRows(){
  const q = ($('mkq').value || '').toLowerCase();
  const rows = mk.items.filter(i => (i.buy > 0 || i.sell > 0) && (!q || (i.name + ' ' + i.cat).toLowerCase().includes(q)));
  $('mkwl').innerHTML = [...new Set(mk.items.filter(i => i.buy > 0 || i.sell > 0).map(i => i.name))].sort((a, b) => a.localeCompare(b)).map(n => '<option value="' + esc(n) + '"></option>').join('');
  rows.forEach(i => {
    const b = mk.best[i.name] || {}, a1 = i.sell > 0 && b.buy ? i.sell - b.buy.price : -1e12, a2 = i.buy > 0 && b.sell ? b.sell.price - i.buy : -1e12;
    i.p = Math.max(a1, a2);
  });
  rows.sort((a, b) => (typeof a[mk.key] === 'string' ? a[mk.key].localeCompare(b[mk.key]) : a[mk.key] - b[mk.key]) * mk.dir);
  const cols = [['name','Ware'],['cat','Kategorie'],['buy','Einkauf (du zahlst)'],['stock','Bestand'],['sell','Verkauf (du erhältst)'],['demand','Nachfrage'],['mean','Ø-Preis'],['p','Beste Gegenstelle anderswo (Gewinn / t)']];
  $('mkbody').innerHTML = rows.length ? '<table class="mt"><thead><tr>' +
    cols.map(([k, t]) => '<th data-k="' + k + '">' + t + (mk.key === k ? (mk.dir > 0 ? ' ▲' : ' ▼') : '') + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map(i => '<tr><td class="bn">' + esc(i.name) + '</td><td class="mut">' + esc(i.cat) + '</td><td>' + nfm(i.buy) + delta(i.buy, i.mean, false) +
      '</td><td>' + (i.buy > 0 ? fmt(i.stock) : '-') + '</td><td>' + nfm(i.sell) + delta(i.sell, i.mean, true) + '</td><td>' +
      (i.sell > 0 ? (i.demand > 0 ? fmt(i.demand) : '<span class="mut">keine</span>') : '-') + '</td><td class="mut">' + nfm(i.mean) + '</td><td>' + counter(i) + '</td></tr>').join('') +
    '</tbody></table>' : '<div class="empty">Keine Treffer</div>';
}
async function loadSnap(id){
  const d = await mapi(Object.assign({op: 'snapshot', market_id: $('mkst').value, snap: id, range: RANGE}, qtyP()));
  mk.cap = d.cap || 0;
  mk.items = d.items || [];
  mk.best = d.best || {};
  $('mksnap').innerHTML = (d.snaps || []).map(s => '<option value="' + s.id + '">Stand ' + esc(dts(s.seen)) + '</option>').join('');
  if (d.snap) $('mksnap').value = d.snap.id;
  $('mkmeta').textContent = d.station ? d.station.name + ' | ' + d.station.system + (d.station.type ? ' | ' + d.station.type : '') + ' | ' + padTxt(d.station) + ' | Stand ' + dts(d.snap && d.snap.seen) + (d.station && noteOf('station', d.station.name) ? ' | Notiz: ' + noteOf('station', d.station.name) : '') : '-';
  marketRows();
}
async function loadMarket(force){
  try{
    const all = $('mkall').checked, sys = window.__sys || '';
    const st = (await mapi({op: 'stations', system: all ? '' : sys})).stations || [];
    const sig = JSON.stringify([all, sys, st.map(s => [s.market_id, s.seen, s.n])]);
    if (!force && sig === mk.sig) return;
    mk.sig = sig;
    const sel = $('mkst'), keep = sel.value;
    sel.innerHTML = stOpts(st);
    if (!st.length){
      $('mkmeta').textContent = sys || '-'; $('mksnap').innerHTML = ''; mk.items = [];
      $('mkbody').innerHTML = '<div class="empty">' + (all ? 'In der Datenbank' : 'Für dieses System') + ' ist noch kein Markt gespeichert. Öffne in einer Station den Markt: Das Spiel schreibt dann Market.json, und es wird automatisch übernommen.</div>';
      return;
    }
    if (!force && keep && st.some(s => String(s.market_id) === keep)) sel.value = keep;
    await loadSnap('');
  }catch(e){}
}
$('mkst').addEventListener('change', () => loadSnap(''));
$('mksnap').addEventListener('change', () => loadSnap($('mksnap').value));
$('mkall').addEventListener('change', () => loadMarket(true));
$('ckrange').addEventListener('change', e => setRange(e.target.value));
$('mkrange').addEventListener('change', e => setRange(e.target.value));
$('ckrange').value = RANGE; $('mkrange').value = RANGE; $('trrange').value = RANGE;
$('trrange').addEventListener('change', e => setRange(e.target.value));
$('mkq').addEventListener('input', marketRows);
$('mkbody').addEventListener('click', e => {
  const th = e.target.closest('th[data-k]'); if (!th) return;
  const k = th.dataset.k; mk.dir = mk.key === k ? -mk.dir : (k === 'name' || k === 'cat' ? 1 : -1); mk.key = k; marketRows();
});

/* ---- Module & Schiffe ---- */
const md = {sig: ''};
async function loadMods(){
  const scope = $('mdscope').value;
  $('mdst').style.display = scope === 'all' ? 'none' : '';
  const d = await mapi({op: 'mods', scope, market_id: $('mdst').value, kind: $('mdkind').value, q: $('mdq').value, range: RANGE});
  const rows = d.rows || [];
  const dl = (d.labels || []).map(n => '<option value="' + esc(n) + '"></option>').join('');
  if ($('mdwl').dataset.sig !== dl){ $('mdwl').innerHTML = dl; $('mdwl').dataset.sig = dl; }
  $('mdmeta').textContent = (d.total || 0) + ' Treffer' + ((d.total || 0) > rows.length ? ' (erste ' + rows.length + ')' : '');
  const all = scope === 'all';
  const pad = r => r.pad_s == null ? '<span class="mut">unbekannt</span>' : (r.pad_l > 0 ? 'Groß' : r.pad_m > 0 ? 'Mittel' : r.pad_s > 0 ? 'Klein' : '-');
  $('mdbody').innerHTML = rows.length ? '<table class="mt"><thead><tr><th>Bezeichnung</th><th>Kategorie</th><th>Klasse</th><th class="num">Preis</th><th class="num">Ø bei ' + 'allen Stationen</th>' +
    (all ? '<th>Station</th><th>System</th><th class="num">Entfernung</th><th>Plattform</th>' : '') + '<th>Stand</th></tr></thead><tbody>' +
    rows.map(r => '<tr><td class="bn" title="' + esc(r.code) + '">' + esc(r.label) + '</td><td class="mut">' + esc(r.cat) + '</td><td>' + esc(r.cls) + '</td><td class="num">' + (r.merc > 0 ? fmt(r.merc) + ' MercCoins' : r.price > 0 ? fmt(r.price) + ' Cr' : 'kostenlos') + (r.cheapest ? ' <small class="iu">günstigster Preis</small>' : '') + '</td>' +
      '<td class="num">' + (r.avg != null ? fmt(Math.round(r.avg)) + (r.dpct != null ? '<small class="' + (r.dpct < -0.5 ? 'iu' : r.dpct > 0.5 ? 'id' : 'mut') + '">' + sgnf(r.dpct, 1) + ' % zum Ø (' + r.n_all + ' Stationen)</small>' : '') : '<span class="mut">nur 1 Station</span>') + '</td>' +
      (all ? '<td>' + esc(r.station) + '</td><td>' + SYS(r.system) + '</td><td class="num">' + (r.dist != null ? r.dist.toFixed(1).replace('.', ',') + ' Ly' : '<span class="mut">unbekannt</span>') + '</td><td>' + pad(r) + '</td>' : '') +
      '<td class="mut">' + esc(dts(r.ts)) + '</td></tr>').join('') + '</tbody></table>' :
    '<div class="empty">' + (all ? 'Keine Treffer in dieser Reichweite.' : 'Für diese Station liegen keine Modul-/Schiffsdaten vor. Öffne dort das Outfitting bzw. die Werft: Das Spiel schreibt dann die Liste.') + '</div>';
}
['mdscope', 'mdkind'].forEach(id => $(id).addEventListener('change', loadMods));
$('mdq').addEventListener('input', () => { clearTimeout(md.t); md.t = setTimeout(loadMods, 250); });
$('mdst').addEventListener('change', loadMods);
$('mdrange').addEventListener('change', e => setRange(e.target.value));
async function loadGear(){
  try{
    const st = (await mapi({op: 'modstations'})).stations || [];
    const sel = $('mdst'), keep = sel.value;
    sel.innerHTML = st.map(x => '<option value="' + x.market_id + '">' + esc(x.name + ' (' + x.system + ')') + '</option>').join('');
    if (keep && st.some(x => String(x.market_id) === keep)) sel.value = keep;
    else { const here = st.find(x => x.system === window.__sys); if (here) sel.value = here.market_id; }
    $('mdrange').value = RANGE;
    $('mdst').disabled = !st.length;
    if (!st.length && $('mdscope').value === 'station'){
      $('mdmeta').textContent = '\u00a0';
      $('mdbody').innerHTML = '<div class="empty">Noch keine Ausrüstung gespeichert. Öffne in einer Station das Outfitting oder die Werft: Das Spiel schreibt dann die Liste.</div>';
      return;
    }
    await loadMods();
  }catch(e){}
}

/* ---- Detailauswertungen (Tabellen) ---- */
const dstat = {ana: '', fac: '', sys: ''};
const sgnf = (v, d) => (v > 0 ? '+' : '') + v.toLocaleString('de-DE', {minimumFractionDigits: d, maximumFractionDigits: d});
const pctf = (a, b) => b > 0 ? (a - b) / b * 100 : null;
function span(ms){ const h = ms / 36e5; return h >= 48 ? (h / 24).toFixed(1).replace('.', ',') + ' Tage' : h >= 1 ? h.toFixed(1).replace('.', ',') + ' Std.' : Math.round(ms / 6e4) + ' Min.'; }
function arrow(delta, pct, d){
  if (!delta) return '<small class="mut">unverändert</small>';
  return '<small class="' + (delta > 0 ? 'iu' : 'id') + '">' + (delta > 0 ? '▲ ' : '▼ ') + sgnf(delta, d) + (pct == null ? '' : ' (' + sgnf(pct, 1) + ' %)') + '</small>';
}
const MF = [['buy', 'Einkauf (Preis)', true], ['sell', 'Verkauf (Preis)', true], ['stock', 'Bestand', false], ['demand', 'Nachfrage', false]];
function trendTxt(pts, key, price){
  const v = pts.map(p => ({t: new Date(p.ts).getTime(), v: p[key]})).filter(x => !price || x.v > 0);
  if (v.length < 3) return '<small class="mut">zu wenige Messpunkte</small>';
  let k = 0, dir = 0;
  for (let i = v.length - 1; i > 0; i--){
    const d = Math.sign(v[i].v - v[i - 1].v);
    if (!d) continue;
    if (!dir) dir = d;
    if (d !== dir) break;
    k++;
  }
  const tail = v.slice(-10), mx = Math.max(...tail.map(x => x.v)), mn = Math.min(...tail.map(x => x.v)), av = tail.reduce((a, x) => a + x.v, 0) / tail.length;
  const vol = av > 0 ? (mx - mn) / av * 100 : 0;
  const last = v[v.length - 1], start = v[Math.max(0, v.length - 1 - k)];
  const since = last.t - start.t, pc = start.v > 0 ? (last.v - start.v) / start.v * 100 : 0;
  if (vol > 20 && k < 3) return '<small class="id">schwankt stark (Spanne ' + vol.toFixed(0) + ' %)</small>';
  if (!dir || k < 2) return '<small class="mut">seitwärts (Spanne ' + vol.toFixed(0) + ' %)</small>';
  return '<small class="' + (dir > 0 ? 'iu' : 'id') + '">' + (dir > 0 ? '▲ steigt' : '▼ fällt') + ' seit ' + span(since) + ' (' + k + ' Messungen, ' + sgnf(pc, 1) + ' %)</small>';
}
function fstats(pts, key, price){
  const v = pts.map(p => ({t: p.ts, v: p[key]})).filter(x => !price || x.v > 0);
  if (!v.length) return null;
  return {n: v.length, first: v[0], last: v[v.length - 1], avg: v.reduce((a, b) => a + b.v, 0) / v.length,
          min: v.reduce((a, b) => b.v < a.v ? b : a), max: v.reduce((a, b) => b.v > a.v ? b : a)};
}
async function anaDetail(name){
  const box = $('anadetail');
  if (!name || !$('anast').value){ dstat.ana = ''; box.innerHTML = ''; return; }
  dstat.ana = name;
  const st = $('anast'), stName = st.options && st.selectedIndex >= 0 && st.options[st.selectedIndex] ? st.options[st.selectedIndex].text : '';
  const pts = (await mapi({op: 'history', market_id: st.value, commodity: name, days: $('anarange').value})).points || [];
  const head = '<div class="dh"><div><div class="dt">' + esc(name) + '</div><div class="dn2">' + esc(stName) + ' | ' + pts.length + ' Messpunkte im gewählten Zeitraum | ▲ gestiegen, ▼ gefallen</div></div>' +
    '<button class="xbtn" data-close="1">Schließen</button></div>';
  if (!pts.length){ box.innerHTML = '<div class="detail">' + head + '<div class="empty">Keine Messwerte im gewählten Zeitraum.</div></div>'; return; }
  const num = (k, price, v) => price ? fmt(v) : fmt(v);
  const sumRows = MF.map(([k, lbl, price]) => {
    const f = fstats(pts, k, price);
    if (!f) return '<tr><td class="bn">' + lbl + '</td><td colspan="10" class="mut">Nie handelbar im Zeitraum</td></tr>';
    const dl = f.last.v - f.first.v, pc = pctf(f.last.v, f.first.v);
    const lastPt = pts[pts.length - 1];
    let pv = null;
    for (let i = pts.length - 1; i >= 0; i--){ const x = pts[i][k]; if (price && !(x > 0)) continue; if (x !== f.last.v){ pv = {v: x, t: pts[i].seen || pts[i].ts}; break; } }
    const prevCell = pv == null ? '<small class="mut">keine frühere Abweichung</small>' :
      (price && !(f.last.v > 0) ? '' : arrow(f.last.v - pv.v, pctf(f.last.v, pv.v), 0)) + '<small class="mut">vorher ' + num(k, price, pv.v) + ' (' + esc(dts(pv.t)) + ')</small>';
    return '<tr><td class="bn">' + lbl + '</td><td>' + f.n + '</td><td>' + num(k, price, f.first.v) + '<small class="mut">' + esc(dts(f.first.t)) + '</small></td><td>' + num(k, price, f.last.v) + '<small class="mut">aktuell bestätigt ' + esc(dts(lastPt.seen || f.last.t)) + (lastPt.seen && lastPt.seen !== f.last.t ? ' · Wert seit ' + esc(dts(f.last.t)) : '') + '</small></td><td>' + prevCell + '</td><td>' +
      (f.n > 1 ? arrow(dl, pc, 0) : '<small class="mut">nur 1 Wert</small>') + '</td><td>' + num(k, price, f.min.v) + '<small class="mut">' + esc(dts(f.min.t)) + '</small></td><td>' + num(k, price, f.max.v) + '<small class="mut">' + esc(dts(f.max.t)) +
      '</small></td><td>' + num(k, price, Math.round(f.avg)) + '</td><td>' + trendTxt(pts, k, price) + '</td></tr>';
  }).join('');
  const cell = (cur, prev, price) => {
    const t = price ? nfm(cur) : fmt(cur);
    if (prev == null) return t;
    if (price && !(prev > 0 && cur > 0)) return t + (cur > 0 ? '<small class="iu">neu handelbar</small>' : prev > 0 ? '<small class="id">nicht mehr handelbar</small>' : '');
    return t + arrow(cur - prev, pctf(cur, prev), 0);
  };
  const dev = pts.map((p, i) => {
    const q = i ? pts[i - 1] : null;
    return '<tr><td>' + esc(dts(p.ts)) + (p.seen !== p.ts ? '<small class="mut">bestätigt bis ' + esc(dts(p.seen)) + '</small>' : '') + (q ? '<small class="mut">+' + span(new Date(p.ts) - new Date(q.ts)) + '</small>' : '') + '</td>' +
      MF.map(([k, , price]) => '<td>' + cell(p[k], q ? q[k] : null, price) + '</td>').join('') + '<td class="mut">' + nfm(p.mean) + '</td></tr>';
  }).reverse().join('');
  box.innerHTML = '<div class="detail">' + head + '<h4 class="ct">Kennzahlen</h4><table class="mt"><thead><tr><th>Wert</th><th>Messpunkte</th><th>Erster Wert</th><th>Aktuell</th><th>Abweichung zum vorherigen Wert</th><th>Veränderung gesamt</th><th>Minimum</th><th>Maximum</th><th>Ø</th><th>Trend</th></tr></thead><tbody>' + sumRows + '</tbody></table>' +
    '<h4 class="ct">Entwicklungsverlauf (neueste zuerst, Veränderung zur Messung davor)</h4><div class="tscroll" style="max-height:340px"><table class="mt"><thead><tr><th>Datum</th><th>Einkauf (Preis)</th><th>Verkauf (Preis)</th><th>Bestand</th><th>Nachfrage</th><th>Ø-Preis</th></tr></thead><tbody>' + dev + '</tbody></table></div></div>';
}
async function faDetail(name){
  const box = $('sadetail'), sys = $('sasys').value.trim();
  if (!name || !sys){ dstat.fac = ''; box.innerHTML = ''; return; }
  dstat.fac = name;
  const pts = (await mapi({op: 'fdetail', system: sys, name, days: $('sarange').value})).points || [];
  const head = '<div class="dh"><div><div class="dt">' + esc(name) + '</div><div class="dn2">' + SYS(sys) + ' | ' + pts.length + ' Messungen im gewählten Zeitraum</div></div><button class="xbtn" data-close="1">Schließen</button></div>';
  if (!pts.length){ box.innerHTML = '<div class="detail">' + head + '<div class="empty">Keine Messwerte im gewählten Zeitraum.</div></div>'; return; }
  const f = pts[0], l = pts[pts.length - 1];
  let mn = f, mx = f, up = null, dn = null, sum = 0;
  pts.forEach((p, i) => {
    if (p.inf < mn.inf) mn = p; if (p.inf > mx.inf) mx = p; sum += p.inf;
    if (i){ const dd = p.inf - pts[i - 1].inf; if (!up || dd > up.dd) up = {dd, t: p.ts}; if (!dn || dd < dn.dd) dn = {dd, t: p.ts}; }
  });
  const days = (new Date(l.ts) - new Date(f.ts)) / 864e5, tot = l.inf - f.inf, pc = pctf(l.inf, f.inf);
  const trend = pts.length < 2 ? 'Zu wenige Messungen' : Math.abs(tot) < 0.05 ? 'Stabil' : tot > 0 ? 'Steigend' : 'Fallend';
  const kv = (a, b) => '<tr><td class="bn">' + a + '</td><td>' + b + '</td></tr>';
  const when = o => '<small class="mut">' + esc(dts(o)) + '</small>';
  const kpi = '<table class="mt"><tbody>' + kv('Aktueller Einfluss', infp(l.inf) + when(l.ts)) + kv('Erste Messung im Zeitraum', infp(f.inf) + when(f.ts)) +
    kv('Veränderung gesamt', pts.length > 1 ? chg(tot, ppf) + ' / ' + chg(pc, pcf) : '<span class="mut">nur 1 Messung</span>') + kv('Trend', esc(trend)) +
    kv('Ø pro Tag', pts.length > 1 && days > 0 ? chg(tot / days, ppf) : '<span class="mut">-</span>') + kv('Minimum', infp(mn.inf) + when(mn.ts)) + kv('Maximum', infp(mx.inf) + when(mx.ts)) +
    kv('Durchschnitt', infp(sum / pts.length)) + (up && up.dd > 0 ? kv('Größter Anstieg zwischen zwei Messungen', chg(up.dd, ppf) + when(up.t)) : '') +
    (dn && dn.dd < 0 ? kv('Größter Rückgang zwischen zwei Messungen', chg(dn.dd, ppf) + when(dn.t)) : '') + kv('Aktueller Status', esc(l.active || l.state || '-') + (l.ctrl ? '<small class="good">Kontrolle</small>' : '')) +
    (l.rep != null ? kv('Dein Ruf', fmt(l.rep)) : '') + '</tbody></table>';
  const dev = pts.map((p, i) => {
    const q = i ? pts[i - 1] : null, dp = q ? p.inf - q.inf : null, ds = p.inf - f.inf;
    return '<tr><td>' + esc(dts(p.ts)) + '</td><td>' + esc(p.active || p.state || '-') + '</td><td class="bn">' + infp(p.inf) + '</td><td>' + chg(dp, ppf) + '</td><td>' + chg(q ? pctf(p.inf, q.inf) : null, pcf) +
      '</td><td>' + (i ? chg(ds, ppf) : '<span class="mut">-</span>') + '</td><td>' + (i ? chg(pctf(p.inf, f.inf), pcf) : '<span class="mut">-</span>') + '</td><td class="mut">' + (q ? span(new Date(p.ts) - new Date(q.ts)) : '-') + '</td><td class="mut">' + (p.rep == null ? '-' : fmt(p.rep)) + '</td></tr>';
  }).reverse().join('');
  box.innerHTML = '<div class="detail">' + head + '<h4 class="ct">Kennzahlen</h4>' + kpi +
    '<h4 class="ct">Entwicklungsverlauf (neueste zuerst)</h4><div class="tscroll" style="max-height:340px"><table class="mt"><thead><tr><th>Datum</th><th>Status</th><th>Einfluss</th><th>Δ zur Messung davor</th><th>Δ %</th><th>Δ seit erster Messung</th><th>Δ %</th><th>Abstand</th><th>Ruf</th></tr></thead><tbody>' + dev + '</tbody></table></div></div>';
}
$('anadetail').addEventListener('click', e => { if (e.target.closest('[data-close]')){ dstat.ana = ''; $('anadetail').innerHTML = ''; } });
$('sadetail').addEventListener('click', e => { if (e.target.closest('[data-close]')){ dstat.fac = ''; $('sadetail').innerHTML = ''; } });
$('anatab').addEventListener('click', e => { const tr = e.target.closest('tr[data-c]'); if (tr) anaDetail(tr.dataset.c); });
$('anatab').addEventListener('keydown', e => { if (e.key === 'Enter'){ const tr = e.target.closest('tr[data-c]'); if (tr) anaDetail(tr.dataset.c); } });
['sasum', 'sahist'].forEach(id => {
  $(id).addEventListener('click', e => { const tr = e.target.closest('tr[data-f]'); if (tr) faDetail(tr.dataset.f); });
  $(id).addEventListener('keydown', e => { if (e.key === 'Enter'){ const tr = e.target.closest('tr[data-f]'); if (tr) faDetail(tr.dataset.f); } });
});

/* ---- Stationsanalyse: Tabelle mit Datum, Menge, Preis ---- */
const sa = {rows: [], total: 0, key: 'ts', dir: -1};
async function anaLoad(){
  if (!$('anast').value){ dstat.ana = ''; $('anadetail').innerHTML = ''; sa.rows = []; $('anameta').textContent = '\u00a0'; $('anatab').innerHTML = '<div class="empty">Noch keine Marktdaten gespeichert.</div>'; return; }
  const d = await mapi({op: 'station_table', market_id: $('anast').value, days: $('anarange').value});
  sa.rows = d.rows || []; sa.total = d.total || 0; anaRender();
  if (dstat.ana) await anaDetail(dstat.ana);
}
function anaRender(){
  const q = ($('anaf').value || '').toLowerCase();
  $('anawl').innerHTML = [...new Set(sa.rows.map(r => r.name))].sort((a, b) => a.localeCompare(b)).map(n => '<option value="' + esc(n) + '"></option>').join('');
  const rows = sa.rows.filter(r => !q || (r.name + ' ' + r.cat).toLowerCase().includes(q));
  rows.sort((a, b) => { const x = a[sa.key], y = b[sa.key]; return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sa.dir; });
  $('anameta').textContent = rows.length + ' Zeilen' + (sa.total > sa.rows.length ? ' (gekürzt: Zeitraum oder Filter nutzen)' : '');
  const cols = [['ts','Datum'],['name','Ware'],['cat','Kategorie'],['buy','Einkauf (Preis)'],['stock','Bestand'],['sell','Verkauf (Preis)'],['demand','Nachfrage'],['mean','Ø-Preis']];
  $('anatab').innerHTML = rows.length ? '<table class="mt"><thead><tr>' +
    cols.map(([k, t]) => '<th data-k="' + k + '">' + t + (sa.key === k ? (sa.dir > 0 ? ' ▲' : ' ▼') : '') + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr data-c="' + esc(r.name) + '" tabindex="0"><td>' + esc(dts(r.ts)) + (r.seen !== r.ts ? '<small class="mut">bestätigt bis ' + esc(dts(r.seen)) + '</small>' : '') +
      '</td><td class="bn">' + esc(r.name) + '</td><td class="mut">' + esc(r.cat) + '</td><td>' + nfm(r.buy) + '</td><td>' + fmt(r.stock) + '</td><td>' + nfm(r.sell) +
      '</td><td>' + fmt(r.demand) + '</td><td class="mut">' + nfm(r.mean) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Keine Daten im gewählten Zeitraum.</div>';
}
async function loadAna(){
  try{
    const st = (await mapi({op: 'stations', system: ''})).stations || [], sel = $('anast'), keep = sel.value;
    sel.innerHTML = stOpts(st);
    if (keep && st.some(s => String(s.market_id) === keep)) sel.value = keep;
    await anaLoad();
  }catch(e){}
}
async function anaPick(m, c){
  if ($('anast').value !== m){ $('anast').value = m; if ($('anast').value !== m) await loadAna(); $('anast').value = m; }
  $('anaf').value = c || '';
  dstat.ana = '';
  await anaLoad();
  if (c) await anaDetail(c);
  if ($('anatab').scrollIntoView) $('anatab').scrollIntoView({behavior: 'smooth', block: 'start'});
}
$('anast').addEventListener('change', () => { dstat.ana = ''; $('anadetail').innerHTML = ''; anaLoad(); });
$('anarange').addEventListener('change', anaLoad);
$('anaf').addEventListener('input', anaRender);
$('anatab').addEventListener('click', e => {
  const th = e.target.closest('th[data-k]'); if (!th) return;
  const k = th.dataset.k; sa.dir = sa.key === k ? -sa.dir : (k === 'name' || k === 'cat' ? 1 : -1); sa.key = k; anaRender();
});

/* ---- Systemanalyse: Fraktionen ---- */
const sa2 = {data: null};
let saNames = new Set();
const infp = v => v.toFixed(2).replace('.', ',') + ' %';
const ppf = v => (v > 0 ? '+' : '') + v.toFixed(2).replace('.', ',') + ' P.';
const pcf = v => (v > 0 ? '+' : '') + v.toFixed(1).replace('.', ',') + ' %';
const chg = (v, f) => v == null ? '<span class="mut">-</span>' : '<span class="' + (v > 0 ? 'up' : v < 0 ? 'dn' : 'mut') + '">' + f(v) + '</span>';
async function loadSa(){
  try{
    const syss = (await mapi({op: 'fsystems'})).systems || [];
    saNames = new Set(syss.map(x => x.system));
    $('sasyslist').innerHTML = syss.map(x => '<option value="' + esc(x.system) + '"></option>').join('');
    const w = $('sasys');
    if (!window.__saManual && window.__sys) w.value = window.__sys;
    else if (!w.value) w.value = window.__sys || (syss[0] ? syss[0].system : '');
    await saLoad();
  }catch(e){}
}
async function saLoad(){
  const sys = $('sasys').value.trim();
  if (!sys){ sa2.data = null; saRender(); return; }
  if (dstat.sys !== sys){ dstat.sys = sys; dstat.fac = ''; $('sadetail').innerHTML = ''; }
  sa2.data = await mapi({op: 'fhistory', system: sys, days: $('sarange').value});
  saRender();
  if (dstat.fac) await faDetail(dstat.fac);
}
function saRender(){
  const d = sa2.data, q = ($('saf').value || '').toLowerCase();
  if (!d || !d.latest){
    $('sanameta').textContent = '\u00a0'; $('sahist').innerHTML = '';
    $('sasum').innerHTML = '<div class="empty">Für dieses System sind noch keine Fraktionsdaten gespeichert. Sie werden aus den Journalen übernommen, sobald du ein bewohntes System besuchst.</div>';
    return;
  }
  $('sanameta').textContent = d.system + ' | Stand ' + dts(d.latest) + ' | ' + d.n_measure + ' Messungen im Zeitraum';
  const sm = d.summary.filter(x => !q || x.name.toLowerCase().includes(q));
  const ref = (o) => o ? infp(o.inf) + '<small class="mut">' + esc(dts(o.ts)) + '</small>' : '<span class="mut">-</span>';
  $('sasum').innerHTML = sm.length ? '<table class="mt"><thead><tr><th>Fraktion</th><th>Status</th><th>Einfluss jetzt</th><th>Vorherige Messung</th><th>Δ Punkte</th><th>Δ %</th>' +
    '<th>Älteste im Zeitraum</th><th>Δ Punkte</th><th>Δ %</th><th>Messungen</th></tr></thead><tbody>' +
    sm.map(x => '<tr data-f="' + esc(x.name) + '" tabindex="0"><td class="bn">' + esc(x.name) + (x.ctrl ? '<small class="good">Kontrolle</small>' : '') + '</td><td>' + esc(x.active || x.state || '-') + '</td><td class="bn">' + infp(x.now) +
      '</td><td>' + ref(x.prev) + '</td><td>' + chg(x.prev && x.prev.d_pp, ppf) + '</td><td>' + chg(x.prev && x.prev.d_pct, pcf) +
      '</td><td>' + ref(x.first) + '</td><td>' + chg(x.first && x.first.d_pp, ppf) + '</td><td>' + chg(x.first && x.first.d_pct, pcf) + '</td><td>' + x.n + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Keine Fraktion gefunden.</div>';
  const rows = d.rows.filter(r => !q || r.name.toLowerCase().includes(q));
  $('sahist').innerHTML = rows.length ? '<table class="mt"><thead><tr><th>Datum</th><th>Fraktion</th><th>Status</th><th>Einfluss</th><th>Δ zur Messung davor</th><th>Jetzt vs. Wert (Punkte)</th><th>Jetzt vs. Wert (%)</th></tr></thead><tbody>' +
    rows.map(r => '<tr data-f="' + esc(r.name) + '" tabindex="0"><td>' + esc(dts(r.ts)) + '</td><td class="bn">' + esc(r.name) + '</td><td>' + esc(r.active || r.state || '-') + '</td><td>' + infp(r.inf) + '</td><td>' + chg(r.d_prev, ppf) +
      '</td><td>' + chg(r.d_now, ppf) + '</td><td>' + chg(r.d_now_pct, pcf) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Keine Messwerte im gewählten Zeitraum.</div>';
}
window.__saFollow = true;
function saGoCurrent(){
  const w = $('sasys');
  if (!window.__sys || window.__saManual) return;
  w.value = window.__sys; w.dataset.prev = '';
  if (!$('tab-sana').hidden) saLoad();
}
function saPick(){ const w = $('sasys'); w.dataset.prev = ''; w.placeholder = 'System wählen oder tippen'; }
function saClear(){ const w = $('sasys'); if (w.value){ w.dataset.prev = w.value; w.placeholder = 'Aktuell: ' + w.value + ' (neues System wählen oder tippen)'; w.value = ''; } }
$('sasys').addEventListener('mousedown', saClear);
$('sasys').addEventListener('focus', () => { const w = $('sasys'); if (w.value){ w.dataset.prev = w.value; w.placeholder = 'Aktuell: ' + w.value + ' (neues System wählen oder tippen)'; w.value = ''; } });
$('sasys').addEventListener('blur', () => { const w = $('sasys'); if (!w.value && w.dataset.prev) w.value = w.dataset.prev; w.dataset.prev = ''; });
$('sasys').addEventListener('input', ev => {
  const w = $('sasys');
  if (saNames.has(w.value)){
    const typed = ev && (ev.inputType === 'insertText' || ev.inputType === 'deleteContentBackward');
    window.__saManual = w.value !== window.__sys;  // eigene Wahl bleibt, bis ein Sprung ein neues System bringt
    saPick(); saLoad();
    if (!typed) setTimeout(() => w.blur(), 0);      // Auswahl aus der Liste: Feld verlassen, naechster Klick oeffnet wieder die ganze Liste
  }
});
$('sasys').addEventListener('keydown', e => { if (e.key === 'Enter'){ window.__saManual = $('sasys').value.trim() !== window.__sys; saPick(); saLoad(); $('sasys').blur(); } });
$('sarange').addEventListener('change', saLoad);
$('saf').addEventListener('input', saRender);

let anaTimer = null;
async function anaSearch(){
  const q = $('anaq').value.trim();
  if (!q){ $('anasmeta').textContent = '\u00a0'; $('anares').innerHTML = '<div class="empty">Suchbegriff eingeben.</div>'; return; }
  try{
    const d = await mapi({op: 'search', q});
    $('anasmeta').textContent = d.total + ' Treffer' + (d.more ? ' (erste 300)' : '');
    $('anares').innerHTML = d.results.length ? '<table class="mt"><thead><tr><th>Ware</th><th>Station</th><th>System</th><th>Einkauf</th><th>Bestand</th><th>Verkauf</th><th>Nachfrage</th><th>Stand</th></tr></thead><tbody>' +
      d.results.map(r => '<tr data-m="' + r.market_id + '" data-c="' + esc(r.name) + '" tabindex="0"><td class="bn">' + hl(r.name, d.terms) + '</td><td>' + hl(r.station, d.terms) +
        '</td><td>' + SYSH(r.system, hl(r.system, d.terms)) + '</td><td>' + nfm(r.buy) + '</td><td>' + fmt(r.stock) + '</td><td>' + nfm(r.sell) + '</td><td>' + fmt(r.demand) + '</td><td class="mut">' + esc(dts(r.seen)) + '</td></tr>').join('') + '</tbody></table>'
      : '<div class="empty">Keine gespeicherten Preise gefunden.</div>';
  }catch(e){}
}
$('anaq').addEventListener('input', () => { clearTimeout(anaTimer); anaTimer = setTimeout(anaSearch, 300); });
$('anares').addEventListener('click', e => { const tr = e.target.closest('tr[data-m]'); if (tr) anaPick(tr.dataset.m, tr.dataset.c); });

/* ---- Warenfinder ---- */
const ware = {rows: [], sort: 'sell'};
let wareNames = new Set();
async function loadWare(){
  try{
    const items = (await mapi({op: 'commodities', market_id: ''})).items || [];
    wareNames = new Set(items.map(c => c.name));
    $('warelist').innerHTML = items.map(c => '<option value="' + esc(c.name) + '"></option>').join('');
    const sel = $('wsel'), cur = $('wq').value.trim();
    sel.innerHTML = '<option value="">Ware aus Liste wählen</option>' + items.slice().sort((x, y) => x.name.localeCompare(y.name, 'de')).map(c => '<option value="' + esc(c.name) + '">' + esc(c.name) + '</option>').join('');
    if (wareNames.has(cur)) sel.value = cur;
  }catch(e){}
}
function renderWare(name){
  const r = ware.rows.slice();
  r.sort({sell: (a, b) => b.sell - a.sell, buy: (a, b) => (a.buy > 0 && a.stock > 0 ? a.buy : 1e12) - (b.buy > 0 && b.stock > 0 ? b.buy : 1e12), new: (a, b) => b.seen.localeCompare(a.seen), dist: (a, b) => (a.dist == null ? 1e12 : a.dist) - (b.dist == null ? 1e12 : b.dist)}[ware.sort]);
  const sells = r.filter(x => x.sell > 0).map(x => x.sell), buys = r.filter(x => x.buy > 0 && x.stock > 0).map(x => x.buy);
  const bs = sells.length ? Math.max(...sells) : -1, bb = buys.length ? Math.min(...buys) : -1;
  $('waremeta').textContent = r.length + ' Stationen' + (r.length && r[0].mean ? ' | Ø-Preis ' + fmt(r[0].mean) + ' Cr' : '');
  $('wareres').innerHTML = r.length ? '<table class="mt"><thead><tr><th>Station</th><th>System</th><th>Entfernung</th><th>Einkauf (du zahlst)</th><th>Bestand</th><th>Verkauf (du erhältst)</th><th>Nachfrage</th><th>Stand</th></tr></thead><tbody>' +
    r.map(x => '<tr data-m="' + x.market_id + '" data-c="' + esc(x.name) + '" tabindex="0"><td class="bn">' + esc(x.station) + '<small class="mut">' + esc(x.type || '') + '</small></td><td>' + SYS(x.system) + '</td><td class="num">' + (x.dist == null ? '<span class="mut">unbekannt</span>' : x.dist < 0.05 ? 'hier' : x.dist.toFixed(1).replace('.', ',') + ' Ly') + '</td><td class="' + (x.buy > 0 && x.stock > 0 && x.buy === bb ? 'best' : '') + '">' + nfm(x.buy) +
      delta(x.buy, x.mean, false) + '</td><td>' + fmt(x.stock) + '</td><td class="' + (x.sell > 0 && x.sell === bs ? 'best' : '') + '">' + nfm(x.sell) + delta(x.sell, x.mean, true) +
      '</td><td>' + fmt(x.demand) + '</td><td class="mut">' + esc(dts(x.seen)) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Keine gespeicherten Preise für &bdquo;' + esc(name) + '&ldquo;.</div>';
}
async function doWare(){
  const name = $('wq').value.trim(); if (!name) return;
  try{ ware.rows = (await mapi({op: 'commodity', name})).rows || []; renderWare(name); }catch(e){}
}
$('wsel').addEventListener('change', () => { const v = $('wsel').value; if (!v) return; $('wq').value = v; $('wq').dataset.prev = ''; doWare(); });
$('wq').addEventListener('change', doWare);
$('wq').addEventListener('keydown', e => { if (e.key === 'Enter') doWare(); });
// Feld beim Anklicken leeren, damit die Auswahlliste wieder alle Waren zeigt; ohne neue Wahl kommt der alte Wert zurück
$('wq').addEventListener('focus', () => {
  const w = $('wq');
  if (w.value){ w.dataset.prev = w.value; w.placeholder = 'Aktuell: ' + w.value + ' (neue Ware wählen oder tippen)'; w.value = ''; }
});
$('wq').addEventListener('blur', () => { const w = $('wq'); if (!w.value && w.dataset.prev) w.value = w.dataset.prev; w.dataset.prev = ''; });
$('wq').addEventListener('input', () => { if (wareNames.has($('wq').value)) doWare(); });
document.querySelectorAll('.chips button[data-ws]').forEach(b => b.addEventListener('click', () => { ware.sort = b.dataset.ws; if ($('wq').value.trim()) renderWare($('wq').value.trim()); }));
$('wareres').addEventListener('click', e => { const tr = e.target.closest('tr[data-m]'); if (!tr) return; showTab('ana'); anaPick(tr.dataset.m, tr.dataset.c); });

/* ---- Beste Trades ---- */
const trd = {rows: [], sort: 'total', ctx: {}, key: '', dir: -1};
let TRS = {leg: '0', pad: 'loose', age: '0'};
try { Object.assign(TRS, JSON.parse(localStorage.getItem('edl_trd') || '{}')); } catch(e) {}
['leg', 'pad', 'age'].forEach(k => { const el = $('tr' + k); if (el) el.value = TRS[k]; });
async function loadTrades(){
  try{
    const d = await mapi(Object.assign({op: 'trades', range: RANGE, leg: TRS.leg, pad: TRS.pad, age: TRS.age}, qtyP()));
    trd.rows = d.trades || []; trd.ctx = d.ctx || {}; renderTrades();
  }catch(e){}
}
const padLbl = pd => !pd ? '<span class="mut" title="Plattform unbekannt (nie dort angedockt)">?</span>' : (pd[2] > 0 ? 'L' : pd[1] > 0 ? 'M' : pd[0] > 0 ? 'S' : '-');
const dTxt = d => d == null ? 'Entfernung unbekannt' : d.toFixed(1).replace('.', ',') + ' Ly';
const ageTxt = h => h > 1e8 ? '?' : h < 48 ? Math.round(h) + ' Std.' : (h / 24).toFixed(1).replace('.', ',') + ' Tage';
const lyTxt = (t, cp) => {
  if (t.leg == null || t.leg < 0.05) return '<span class="mut">-</span>';
  return cp && t.ly != null ? fmt(Math.round(t.ly)) + ' Cr' + '<small class="mut">' + fmt(Math.round(t.ly_t)) + ' Cr / t</small>' : fmt(Math.round(t.ly_t)) + ' Cr / t';
};
const TR_COLS = [['ware', 'Ware', t => t.name.toLowerCase(), 1], ['kauf', 'Kaufen bei', t => (t.buy.station || '').toLowerCase(), 1],
  ['ek', 'Einkauf', t => t.buy.price, 1], ['verk', 'Verkaufen bei', t => (t.sell.station || '').toLowerCase(), 1],
  ['vk', 'Verkauf', t => t.sell.price, -1], ['profit', 'Gewinn / t', t => t.profit, -1], ['qty', 'Menge', t => t.qty, -1],
  ['total', 'Gewinn / Ladung', t => t.total, -1], ['leg', 'Strecke', t => t.leg, 1],
  ['ly', 'Gewinn / Ly', (t, cp) => cp && t.ly != null ? t.ly : t.ly_t, -1], ['age', 'Älteste Preise', t => t.age, 1]];
const trHead = () => TR_COLS.map(c => '<th class="srt" data-tr="' + c[0] + '">' + c[1] + (trd.key === c[0] ? (trd.dir > 0 ? ' ▲' : ' ▼') : '') + '</th>').join('');
function renderTrades(){
  const cx = trd.ctx || {};
  const cp = !!cx.cap;
  const hc = TR_COLS.find(x => x[0] === trd.key);
  const r = trd.rows.slice().sort(hc ? (x, y) => {
    const a = hc[2](x, cp), b = hc[2](y, cp);
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    return (typeof a === 'string' ? a.localeCompare(b, 'de') : a - b) * trd.dir;
  } : (a, b) => trd.sort === 'ly' ? ((cp ? b.ly : b.ly_t) == null ? -1e18 : (cp ? b.ly : b.ly_t)) - ((cp ? a.ly : a.ly_t) == null ? -1e18 : (cp ? a.ly : a.ly_t)) : trd.sort === 'profit' || !cp ? b.profit - a.profit : b.total - a.total);
  $('trmeta').textContent = r.length + ' Trades';
  $('trctx').textContent = (cx.ship ? 'Schiff: ' + cx.ship : 'Kein Schiff bekannt') + (cx.own ? ' · Eigene Menge ' + cx.own + ' t' + (cx.ship_cap ? ' (Frachtraum des Schiffs: ' + cx.ship_cap + ' t)' : '') : cx.cap ? ' · Frachtraum ' + cx.cap + ' t' : ' · Das Schiff hat keinen Frachtraum (0 t): oben eine eigene Menge eingeben, dann wird der Gewinn pro Ladung berechnet') +
    (cx.need ? ' · Landeplatz ' + cx.need : ' · Landeplatz-Bedarf unbekannt: keine Prüfung') + (cx.pos ? '' : ' · aktuelle Position unbekannt: Entfernung zu dir nicht berechenbar');
  const side = (o, lbl) => esc(o.station) + ' <small class="mut">[' + padLbl(o.pad) + ']</small><small class="mut">' + SYS(o.system) + ' · ' + lbl + ' ' + dTxt(o.dist) + '</small>' + stand(o.seen);
  $('trres').innerHTML = r.length ? '<table class="mt"><thead><tr>' + trHead() + '</tr></thead><tbody>' +
    r.map(t => '<tr data-m="' + t.buy.market_id + '" data-c="' + esc(t.name) + '" tabindex="0"><td class="bn">' + esc(t.name) + '<small class="mut">' + esc(t.cat) + '</small></td><td>' + side(t.buy, 'von dir') +
      '</td><td>' + fmt(t.buy.price) + '<small class="mut">Bestand ' + fmt(t.buy.qty) + '</small></td><td>' + side(t.sell, 'vom Kaufort') + '</td><td>' + fmt(t.sell.price) +
      '<small class="mut">Nachfrage ' + fmt(t.sell.qty) + '</small></td><td class="best">+' + fmt(t.profit) + '</td><td>' + (t.qty == null ? '<span class="mut">-</span>' : fmt(t.qty) + ' t') + '</td><td class="best">' + (t.total == null ? '<span class="mut">-</span>' : fmt(t.total) + ' Cr') + '</td><td>' +
      (t.leg == null ? '<span class="mut">unbekannt</span>' : t.leg < 0.05 ? 'gleiches System' : t.leg.toFixed(1).replace('.', ',') + ' Ly') + '</td><td>' + lyTxt(t, cp) + '</td><td class="' +
      (t.age > 72 ? 'warn' : 'mut') + '">' + ageTxt(t.age) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Keine Trades mit diesen Einstellungen. Lockere Reichweite, Plattform oder Preisalter, oder speichere Preise von mehr Stationen.</div>';
}
const LP = {rows: [], cx: {}, key: '', dir: -1};
const LP_COLS = [['start', 'Start', t => (t.a.station || '').toLowerCase(), 1], ['ziel', 'Ziel', t => (t.b.station || '').toLowerCase(), 1],
  ['hin', 'Hin', t => t.out.profit, -1], ['back', 'Zurück', t => t.back.profit, -1],
  ['total', 'Gewinn gesamt', (t, cx) => cx.cap ? t.total : t.sum_t, -1], ['ly', 'Pro Ly (Hin + Zurück)', (t, cx) => cx.cap && t.per_ly != null ? t.per_ly : t.ly_t, -1],
  ['lyin', 'Pro Ly inkl. Anreise', (t, cx) => cx.cap && t.in_ly != null ? t.in_ly : t.in_ly_t, -1],
  ['leg', 'Strecke einfach', t => t.leg, 1], ['trip', 'Hin + Zurück', t => t.trip, 1], ['age', 'Älteste Preise', t => t.age, 1]];
const lpHead = cx => LP_COLS.map(c => '<th class="srt" data-lp="' + c[0] + '">' + c[1] + (LP.key === c[0] ? (LP.dir > 0 ? ' ▲' : ' ▼') : '') + '</th>').join('');
function lpSorted(){
  const c = LP_COLS.find(x => x[0] === LP.key), cx = LP.cx;
  if (!c) return LP.rows.slice();
  return LP.rows.slice().sort((x, y) => {
    const a = c[2](x, cx), b = c[2](y, cx);
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;
    return (typeof a === 'string' ? a.localeCompare(b, 'de') : a - b) * LP.dir;
  });
}
function renderLoops(){
  const r = lpSorted(), cx = LP.cx;
    $('lpmeta').textContent = r.length + ' Rundkurse';
    $('lpctx').textContent = (cx.ship ? 'Schiff: ' + cx.ship : 'Kein Schiff bekannt') + (cx.own ? ' · Eigene Menge ' + cx.own + ' t' : cx.cap ? ' · Frachtraum ' + cx.cap + ' t' : ' · Das Schiff hat keinen Frachtraum (0 t): im Trades-Bereich oder im Lokalen Markt eine eigene Menge eingeben') +
      ' · ' + (cx.n || 0) + ' Stationen berücksichtigt';
    const st = (o, key) => esc(o.station) + ' <small class="mut">[' + padLbl(o.pad) + ']</small><small class="mut">' + SYS(o.system) + ' · ' + dTxt(o.dist) + '</small>';
    const lg = (l, from, to) => esc(l.name) + '<small class="mut">' + fmt(l.buy) + ' → ' + fmt(l.sell) + ' · +' + fmt(l.profit) + '/t · ' + fmt(l.qty) + ' t</small>';
    $('lpres').innerHTML = r.length ? '<table class="mt"><thead><tr>' + lpHead(cx) + '</tr></thead><tbody>' +
      r.map(t => '<tr><td>' + st(t.a) + '</td><td>' + st(t.b) + '</td><td>' + lg(t.out) + '</td><td>' + lg(t.back) + '</td><td class="best">' + (cx.cap ? fmt(t.total) + ' Cr<small class="mut">+' + fmt(t.sum_t) + ' / t</small>' : '+' + fmt(t.sum_t) + ' / t') +
        '</td><td>' + (t.leg == null || t.leg < 0.05 ? '-' : (cx.cap && t.per_ly != null ? fmt(Math.round(t.per_ly)) + ' Cr<small class="mut">' + fmt(Math.round(t.ly_t)) + ' Cr / t</small>' : fmt(Math.round(t.ly_t)) + ' Cr / t')) + '</td><td>' + (t.in_ly_t == null ? '<span class="mut" title="Entfernung zu deinem Standort unbekannt">-</span>' : (cx.cap && t.in_ly != null ? fmt(Math.round(t.in_ly)) + ' Cr<small class="mut">' + fmt(Math.round(t.in_ly_t)) + ' Cr / t</small>' : fmt(Math.round(t.in_ly_t)) + ' Cr / t')) +
        '</td><td>' + (t.leg == null ? 'unbekannt' : t.leg.toFixed(1).replace('.', ',') + ' Ly') + '</td><td>' + (t.leg == null ? 'unbekannt' : t.trip.toFixed(1).replace('.', ',') + ' Ly' + (t.a.dist != null ? '<small class="mut">+ Anreise ' + t.a.dist.toFixed(1).replace('.', ',') + ' Ly</small>' : '')) + '</td><td class="' + (t.age > 72 ? 'warn' : 'mut') + '">' + ageTxt(t.age) + '</td></tr>').join('') + '</tbody></table>'
      : '<div class="empty">Keine Rundkurse mit diesen Einstellungen. Es braucht zwei Stationen mit Markt-Daten, die sich gegenseitig beliefern lassen. Lockere die Filter oder speichere mehr Märkte.</div>';
}
async function loadLoops(){
  try{
    const d = await mapi(Object.assign({op: 'loops', range: RANGE, leg: TRS.leg, pad: TRS.pad, age: TRS.age}, qtyP()));
    LP.rows = d.loops || []; LP.cx = d.ctx || {}; renderLoops();
  }catch(e){}
}
$('lpres').addEventListener('click', e => {
  const th = e.target.closest('th[data-lp]'); if (!th) return;
  const k = th.dataset.lp, c = LP_COLS.find(x => x[0] === k);
  if (LP.key === k) LP.dir = -LP.dir; else { LP.key = k; LP.dir = c[3]; }
  renderLoops();
});
/* ---- Marktvergleich ---- */
let CMP = {a: '', b: '', free: '', st: []};
try { Object.assign(CMP, JSON.parse(localStorage.getItem('edl_cmp') || '{}')); } catch(e) {}
const cmpSave = () => { try { localStorage.setItem('edl_cmp', JSON.stringify({a: CMP.a, b: CMP.b, free: CMP.free})); } catch(e) {} };
async function loadCmpSt(){
  try{
    const d = await mapi({op: 'stations', system: ''});
    CMP.st = (d.stations || []).filter(s => s.n > 0).sort((x, y) => (x.system || '').localeCompare(y.system || '', 'de') || (x.name || '').localeCompare(y.name || '', 'de'));
    const opts = '<option value="">Station wählen</option>' + CMP.st.map(s => '<option value="' + s.market_id + '">' + esc(s.system) + ' · ' + esc(s.name) + '</option>').join('');
    ['a', 'b'].forEach(k => { const el = $('cmp' + k); el.innerHTML = opts; if (CMP[k] && CMP.st.some(s => String(s.market_id) === String(CMP[k]))) el.value = CMP[k]; else CMP[k] = ''; });
    $('cmpfree').value = CMP.free;
    loadCmp();
  }catch(e){}
}
const cmpTable = (L, from, to, room) => {
  if (!L.items.length) return '<div class="empty">Keine Ware, die bei ' + esc(from) + ' mit Gewinn gekauft und bei ' + esc(to) + ' verkauft werden kann.</div>';
  return '<table class="mt"><thead><tr><th>Ware</th><th>Einkauf</th><th>Bestand</th><th>Verkauf</th><th>Nachfrage</th><th>Gewinn / t</th>' + (room ? '<th>Menge</th><th>Gewinn gesamt</th>' : '') + '</tr></thead><tbody>' +
    L.items.map(t => '<tr' + (room && !t.qty ? ' class="mut"' : '') + '><td class="bn">' + esc(t.name) + '<small class="mut">' + esc(t.cat) + '</small></td><td>' + fmt(t.buy) + '</td><td>' + fmt(t.stock) + '</td><td>' + fmt(t.sell) + '</td><td>' + fmt(t.demand) +
      '</td><td class="best">+' + fmt(t.profit) + '</td>' + (room ? '<td>' + (t.qty ? fmt(t.qty) + ' t' : '<span class="mut">-</span>') + '</td><td class="best">' + (t.qty ? fmt(t.total) + ' Cr' : '<span class="mut">-</span>') + '</td>' : '') + '</tr>').join('') + '</tbody></table>' +
    (room ? '<div class="mut" style="margin:6px 0 14px">Summe: <b>' + fmt(L.total) + ' Cr</b> Gewinn mit ' + fmt(L.used) + ' von ' + fmt(room) + ' t · Einkaufskosten ' + fmt(L.cost) + ' Cr</div>' : '');
};
async function loadCmp(){
  const out = $('cmpres');
  if (!CMP.a || !CMP.b){ $('cmpmeta').textContent = '\u00a0'; $('cmpctx').textContent = '\u00a0'; out.innerHTML = '<div class="empty">Zwei Märkte wählen.</div>'; return; }
  if (CMP.a === CMP.b){ out.innerHTML = '<div class="empty">Bitte zwei verschiedene Stationen wählen.</div>'; return; }
  try{
    const d = await mapi(Object.assign({op: 'compare', a: CMP.a, b: CMP.b, free: CMP.free}, qtyP()));
    if (!d.ok){ out.innerHTML = '<div class="empty">Station nicht gefunden.</div>'; return; }
    const A = d.stations.a, B = d.stations.b, cx = d.ctx;
    $('cmpmeta').textContent = d.dist == null ? 'Entfernung unbekannt' : d.dist < 0.05 ? 'gleiches System' : d.dist.toFixed(1).replace('.', ',') + ' Ly';
    $('cmpctx').textContent = (cx.room ? 'Laderaum für die Berechnung: ' + cx.room + ' t' + (cx.free ? ' (freier Platz)' : cx.own ? ' (eigene Menge)' : ' (Frachtraum von ' + cx.ship + ')') : 'Kein Frachtraum bekannt: nur Gewinn pro t. Trage oben einen freien Platz ein.') +
      ' · Preise A: ' + dts(d.ages.a.seen) + ' · Preise B: ' + dts(d.ages.b.seen);
    const nm = s => esc(s.name) + ' <small class="mut">' + esc(s.system) + '</small>';
    out.innerHTML = '<h4 style="margin:6px 0">Kaufen bei ' + nm(A) + ', verkaufen bei ' + nm(B) + '</h4>' + cmpTable(d.ab, A.name, B.name, cx.room) +
      '<h4 style="margin:6px 0">Kaufen bei ' + nm(B) + ', verkaufen bei ' + nm(A) + '</h4>' + cmpTable(d.ba, B.name, A.name, cx.room);
  }catch(e){}
}
$('cmpa').addEventListener('change', () => { CMP.a = $('cmpa').value; cmpSave(); loadCmp(); });
$('cmpb').addEventListener('change', () => { CMP.b = $('cmpb').value; cmpSave(); loadCmp(); });
$('cmpswap').addEventListener('click', () => { [CMP.a, CMP.b] = [CMP.b, CMP.a]; $('cmpa').value = CMP.a; $('cmpb').value = CMP.b; cmpSave(); loadCmp(); });
$('cmpfree').addEventListener('input', () => { CMP.free = $('cmpfree').value.replace(/[^0-9]/g, ''); cmpSave(); clearTimeout(CMP.tm); CMP.tm = setTimeout(loadCmp, 300); });
/* ---- Sitzungen, Team, Kampfanalyse ---- */
const sdur = m => m >= 60 ? Math.floor(m / 60) + ' Std. ' + String(Math.round(m % 60)).padStart(2, '0') + ' Min.' : Math.round(m) + ' Min.';
const sph = (n, m) => m >= 5 ? (n / (m / 60)).toLocaleString('de-DE', {maximumFractionDigits: 1}) : '-';
const scr = n => (n < 0 ? '-' : '') + fmt(Math.abs(n)) + ' Cr';
const sdt = iso => iso ? new Date(iso).toLocaleString('de-DE', {weekday:'short', day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'}) : '-';
const stm = iso => iso ? new Date(iso).toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'}) : '-';
async function loadSess(){
  document.querySelectorAll('.sdsel').forEach(e => { e.value = SD.days; });
  try{
    SD.d = await (await fetch('/api/sessions?days=' + SD.days, {cache: 'no-store'})).json();
    if (SD.d.error){ $('ssres').innerHTML = '<div class="empty">' + esc(SD.d.error) + '</div>'; return; }
    renderSess(); renderTeam(); renderKana();
  }catch(e){}
}
document.querySelectorAll('.sdsel').forEach(e => e.addEventListener('change', () => { SD.days = e.value; try { localStorage.setItem('edl_sdays', SD.days); } catch(x) {} loadSess(); }));
function ssDetail(s){
  const li = o => Object.keys(o).sort((a, b) => o[b] - o[a]).map(k => '<tr><td>' + esc(k) + '</td><td class="num">' + scr(o[k]) + '</td></tr>').join('') || '<tr><td class="mut">keine</td><td></td></tr>';
  const ms = s.missions.length ? '<table class="mt"><tbody>' + s.missions.map(m => '<tr><td class="mut">' + stm(m.ts) + '</td><td>' + esc(m.name) + '</td><td class="num">' + (m.reward ? scr(m.reward) : '-') + '</td></tr>').join('') + '</tbody></table>' : '<span class="mut">keine abgeschlossen</span>';
  const wg = s.wing.length ? s.wing.map(w => stm(w.start) + '–' + stm(w.end) + ' <span>mit</span> ' + esc(w.members.join(', ') || 'unbekannt') + ' (' + sdur(w.mins) + ')').join('<br>') : '<span class="mut">solo</span>';
  return '<div class="row2" style="align-items:flex-start;gap:24px;flex-wrap:wrap"><div><b>Einnahmen</b><table class="mt"><tbody>' + li(s.inc) + '</tbody></table></div><div><b>Ausgaben</b><table class="mt"><tbody>' + li(s.exp) +
    '</tbody></table></div><div><b>Missionen (' + s.n_missions + ')</b>' + ms + '</div><div><b>Flügel</b><br>' + wg + '<br><br><b>Schiffe (laut Loadout-Wechsel)</b><br>' + (s.ships.length ? s.ships.map(esc).join('<br>') : esc(s.ship || '-')) + '</div></div>';
}
function renderSess(){
  const d = SD.d, L = d.sessions;
  $('ssmeta').textContent = d.n + ' Sitzungen' + (d.n > L.length ? ' (die letzten ' + L.length + ')' : '');
  $('ssres').innerHTML = L.length ? L.map((s, i) => {
    const kz = [];
    if (s.kills) kz.push(s.kills + ' Kopfgelder (' + scr(s.kill_credits) + ')');
    if (s.wing_mins) kz.push('Flügel ' + sdur(s.wing_mins));
    if (s.merits) kz.push(fmt(s.merits) + ' Verdienste');
    return '<details class="ssd"' + (i === 0 ? ' open' : '') + '><summary><b>' + esc(sdt(s.start)) + '</b> · ' + sdur(s.mins) + ' · ' + esc(s.ship || '-') + ' · <span class="' + (s.net >= 0 ? 'best' : 'warn') + '">Netto ' + (s.net > 0 ? '+' : '') + scr(s.net) + '</span>' + (kz.length ? ' · ' + kz.join(' · ') : '') + '</summary>' +
      '<table class="mt"><thead><tr><th>Sprünge</th><th>Systeme</th><th>Einnahmen</th><th>Ausgaben</th><th>Kopfgelder</th><th>Scans</th><th>Schilde gefallen</th><th>Rumpftreffer</th><th>Angriffe auf dich</th><th>Hitzewarnungen</th><th>Interdiktionen</th><th>Straftaten</th><th>Verdienste</th></tr></thead><tbody><tr>' +
      '<td>' + s.jumps + (s.ly ? '<small class="mut">' + s.ly.toLocaleString('de-DE', {maximumFractionDigits: 1}) + ' Ly</small>' : '') + '</td><td>' + s.systems + '</td><td>' + scr(s.income) + '</td><td>' + scr(s.expense) + '</td><td>' + s.kills + (s.kills ? '<small class="mut">' + scr(s.kill_credits) + '</small>' : '') +
      '</td><td>' + s.scans + '</td><td>' + s.shield + '</td><td>' + s.hull + (s.hull ? '<small class="mut">tiefster Stand ' + s.min_hull + ' %</small>' : '') + '</td><td>' + s.attacks + '</td><td>' + s.heat + (s.heat_dmg ? '<small class="warn">' + s.heat_dmg + ' Hitzeschäden</small>' : '') +
      '</td><td>' + s.interdicted + (s.interdicted ? '<small class="mut">' + s.escaped + ' entkommen</small>' : '') + '</td><td>' + s.crimes + (s.crimes ? '<small class="mut">' + scr(s.crime_bounty) + ' · ' + s.victim + ' als Opfer</small>' : '') +
      '</td><td>' + (s.merits ? '+' + fmt(s.merits) + (s.total_merits != null ? '<small class="mut">gesamt ' + fmt(s.total_merits) + '</small>' : '') : '-') + '</td></tr></tbody></table>' + ssDetail(s) + (s.died ? '<div class="warn">Ausgefallen: ' + s.died + 'x</div>' : '') + '</details>';
  }).join('') : '<div class="empty">Keine Sitzungen im Zeitraum.</div>';
}
function renderTeam(){
  const t = SD.d.team, w = t.wing, o = t.solo;
  $('tmmeta').textContent = t.wings.length + ' Flügel-Einsätze';
  const row = (lbl, f, fm) => '<tr><td>' + lbl + '</td><td class="num">' + fm(w) + '</td><td class="num">' + fm(o) + '</td></tr>';
  const ph = (x, k) => sph(x[k], x.mins);
  $('tmcmp').innerHTML = w.mins + o.mins ? '<table class="mt"><thead><tr><th></th><th>Im Flügel</th><th>Solo</th></tr></thead><tbody>' +
    row('Zeit', 0, x => sdur(x.mins)) + row('Kopfgelder', 0, x => fmt(x.kills) + ' <small class="mut">' + ph(x, 'kills') + ' pro Std.</small>') +
    row('Kopfgeld-Credits', 0, x => scr(x.kill_credits) + ' <small class="mut">' + (x.mins >= 5 ? scr(x.kill_credits / (x.mins / 60)) + ' pro Std.' : '-') + '</small>') +
    row('Einnahmen (alle Quellen)', 0, x => scr(x.income) + ' <small class="mut">' + (x.mins >= 5 ? scr(x.income / (x.mins / 60)) + ' pro Std.' : '-') + '</small>') +
    row('Ausgaben', 0, x => scr(x.expense)) + row('Gescannte Schiffe', 0, x => fmt(x.scans) + ' <small class="mut">' + ph(x, 'scans') + ' pro Std.</small>') +
    row('Schilde gefallen', 0, x => fmt(x.shield) + ' <small class="mut">' + ph(x, 'shield') + ' pro Std.</small>') + row('Rumpftreffer', 0, x => fmt(x.hull) + ' <small class="mut">' + ph(x, 'hull') + ' pro Std.</small>') +
    row('Angriffe auf dich', 0, x => fmt(x.attacks) + ' <small class="mut">' + ph(x, 'attacks') + ' pro Std.</small>') + row('Hitzewarnungen', 0, x => fmt(x.heat)) +
    row('Straftaten', 0, x => fmt(x.crimes)) + row('Powerplay-Verdienste', 0, x => fmt(x.merits) + ' <small class="mut">' + ph(x, 'merits') + ' pro Std.</small>') + '</tbody></table>' +
    '<div class="mut" style="margin-top:6px">Einnahmen sind Auszahlungen, die im Journal stehen (Verkäufe, eingelöste Gutscheine, Missionen). Kopfgelder werden erst beim Einlösen ausgezahlt. Wenige Kopfgelder ergeben stark schwankende Stundenwerte.</div>'
    : '<div class="empty">Keine Daten im Zeitraum.</div>';
  $('tmmmeta').textContent = t.members.length + ' Mitspieler';
  $('tmmem').innerHTML = t.members.length ? '<table class="mt"><thead><tr><th>Name</th><th>Zeit im Flügel</th><th>Einsätze</th><th>Zuletzt</th></tr></thead><tbody>' +
    t.members.map(m => '<tr><td class="bn">' + esc(m.name) + '</td><td>' + sdur(m.mins) + '</td><td>' + m.n + '</td><td class="mut">' + esc(dts(m.last)) + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Im Zeitraum bist du in keinem Flügel geflogen.</div>';
  $('tmwmeta').textContent = ' ';
  $('tmwings').innerHTML = t.wings.length ? '<table class="mt"><thead><tr><th>Wann</th><th>Dauer</th><th>Mit</th><th>Kopfgelder</th><th>Scans</th><th>Schilde</th><th>Rumpf</th><th>Hitze</th><th>Straftaten</th><th>Verdienste</th></tr></thead><tbody>' +
    t.wings.map(x => '<tr><td>' + esc(sdt(x.start)) + '<small class="mut">bis ' + stm(x.end) + '</small></td><td>' + sdur(x.mins) + '</td><td>' + esc(x.members.join(', ') || 'unbekannt') + '</td><td>' + x.kills + (x.kills ? '<small class="mut">' + scr(x.kill_credits) + '</small>' : '') +
      '</td><td>' + x.scans + '</td><td>' + x.shield + '</td><td>' + x.hull + '</td><td>' + x.heat + '</td><td>' + x.crimes + '</td><td>' + (x.merits ? '+' + fmt(x.merits) : '-') + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Keine Flügel-Einsätze im Zeitraum.</div>';
}
function renderKana(){
  const c = SD.d.combat;
  $('kamta').textContent = c.kills + ' Kopfgelder';
  $('kasum').innerHTML = '<table class="mt"><thead><tr><th>Kopfgelder</th><th>Credits</th><th>Pro Gegner</th><th>Pro Stunde (Sitzungsdauer)</th><th>Sitzungen mit Kopfgeld</th></tr></thead><tbody><tr><td>' + fmt(c.kills) + '</td><td>' + scr(c.credits) + '</td><td>' + (c.cr_kill != null ? scr(c.cr_kill) : '-') + '</td><td>' +
    (c.cr_h != null ? scr(c.cr_h) : '-') + '</td><td>' + c.sessions_kills + '</td></tr></tbody></table><div class="mut" style="margin-top:6px">Gezählt werden Kopfgelder und Kampfanleihen, die dein Journal dir zuschreibt. „Pro Stunde“ teilt durch die ganze Sitzungsdauer, nicht nur die Kampfzeit.</div>';
  $('kapmeta').textContent = ' ';
  const days = c.daily.length ? '<table class="mt"><thead><tr><th>Tag</th><th>Kopfgelder</th><th>Credits</th><th>Summe</th></tr></thead><tbody>' + (() => { let acc = 0; return c.daily.map(x => { acc += x.cr; return '<tr><td>' + esc(new Date(x.day + 'T12:00:00').toLocaleDateString('de-DE', {weekday:'short', day:'2-digit', month:'2-digit'})) + '</td><td>' + x.n + '</td><td>' + scr(x.cr) + '</td><td class="mut">' + scr(acc) + '</td></tr>'; }).join(''); })() + '</tbody></table>' : '<div class="empty">Keine Kopfgelder im Zeitraum.</div>';
  const se = c.sessions.filter(b => b.kills).length ? '<table class="mt" style="margin-top:10px"><thead><tr><th>Sitzung</th><th>Dauer</th><th>Kopfgelder</th><th>Credits</th><th>Pro Gegner</th><th>Pro Std. (Sitzung)</th><th>Pro Std. (erstes bis letztes Kopfgeld)</th></tr></thead><tbody>' +
    c.sessions.filter(b => b.kills).map(b => '<tr><td>' + esc(sdt(b.start)) + '</td><td>' + sdur(b.mins) + '</td><td>' + b.kills + '</td><td>' + scr(b.credits) + '</td><td>' + (b.cr_kill != null ? scr(b.cr_kill) : '-') + '</td><td>' + (b.cr_h != null ? scr(b.cr_h) : '-') + '</td><td>' + (b.cr_span_h != null ? scr(b.cr_span_h) : '<span class="mut">zu kurz</span>') + '</td></tr>').join('') + '</tbody></table>' : '';
  $('kapath').innerHTML = days + se;
  const lst = (title, rows, f) => '<div style="min-width:240px"><b>' + title + '</b><table class="mt"><tbody>' + (rows.length ? rows.map(f).join('') : '<tr><td class="mut">keine</td><td></td></tr>') + '</tbody></table></div>';
  $('kaenemy').innerHTML = '<div class="row2" style="align-items:flex-start;gap:24px;flex-wrap:wrap">' +
    lst('Gescannte Schiffstypen', c.ships, x => '<tr><td>' + esc(x.name) + '</td><td class="num">' + x.n + '</td></tr>') +
    lst('Rechtsstatus der Gescannten', c.legal, x => '<tr><td>' + esc(x.name) + '</td><td class="num">' + x.n + '</td></tr>') +
    lst('Fraktionen der Gescannten', c.factions, x => '<tr><td>' + esc(x.name) + '</td><td class="num">' + x.n + '</td></tr>') +
    lst('Kopfgelder nach Schiffstyp', c.kship, x => '<tr><td>' + esc(x.name) + '</td><td class="num">' + x.n + ' · Ø ' + scr(x.avg) + '</td></tr>') +
    lst('Kopfgelder nach Fraktion', c.kfac, x => '<tr><td>' + esc(x.name) + '</td><td class="num">' + x.n + ' · ' + scr(x.cr) + '</td></tr>') + '</div>';
  const sh = c.sessions.length ? '<table class="mt"><thead><tr><th>Sitzung</th><th>Dauer</th><th>Scans</th><th>Schilde gefallen</th><th>Rumpftreffer</th><th>Angriffe auf dich</th><th>Hitzewarnungen</th></tr></thead><tbody>' +
    c.sessions.map(b => '<tr><td>' + esc(sdt(b.start)) + '</td><td>' + sdur(b.mins) + '</td><td>' + b.scans + '</td><td>' + b.shield + '</td><td>' + b.hull + '</td><td>' + b.attacks + '</td><td>' + b.heat + '</td></tr>').join('') + '</tbody></table>' : '<div class="empty">Keine Kampfdaten im Zeitraum.</div>';
  $('kaheat').innerHTML = '<div class="row2" style="align-items:flex-start;gap:24px;flex-wrap:wrap">' +
    lst('Hitzewarnungen nach System', c.heat, x => '<tr><td>' + esc(x.sys) + '</td><td class="num">' + x.n + '<small class="mut">zuletzt ' + esc(dts(x.last)) + '</small></td></tr>') +
    lst('Schilde gefallen nach System', c.shield_sys, x => '<tr><td>' + esc(x.sys) + '</td><td class="num">' + x.n + '</td></tr>') + '</div><div style="margin-top:10px">' + sh + '</div>';
}
/* ---- Stationsakte ---- */
const SA = {key: '', list: [], rec: null};
try { SA.key = localStorage.getItem('edl_sakte') || ''; } catch(e) {}
const spct = v => (v > 0 ? '+' : '') + v.toLocaleString('de-DE', {maximumFractionDigits: 1}) + ' %';
const sdevCls = (v, good) => Math.abs(v) < 3 ? 'mut' : ((v > 0) === good ? 'best' : 'warn');
async function loadSakte(){
  try{
    if (!SA.list.length){
      const d = await (await fetch('/api/stationsakte?op=list', {cache: 'no-store'})).json();
      SA.list = d.stations || [];
      $('sast').innerHTML = '<option value="">Station wählen</option>' + SA.list.map(s => '<option value="' + esc(s.key) + '">' + esc(s.system) + ' · ' + esc(s.name) + (s.market ? '' : ' (ohne Marktdaten)') + '</option>').join('');
    }
    if (SA.key && SA.list.some(s => s.key === SA.key)) $('sast').value = SA.key; else SA.key = '';
    renderSakte();
    loadSaRec();
  }catch(e){}
}
async function loadSaRec(){
  try{
    const d = await (await fetch('/api/stationsakte?op=recovery_all', {cache: 'no-store'})).json();
    $('sarecall').innerHTML = (d.rows || []).length ? '<table class="mt"><thead><tr><th>Station</th><th>Ware</th><th>Was</th><th>Beobachtungen</th><th>Typisch genommen</th><th>Erholung pro Std. (mindestens)</th><th>Wieder voll nach (höchstens)</th><th>Zuletzt</th></tr></thead><tbody>' +
      d.rows.map(r => '<tr data-k="' + esc(r.key) + '" tabindex="0"><td class="bn">' + esc(r.station) + '<small class="mut">' + SYS(r.system) + '</small></td><td>' + esc(r.name) + '</td><td>' + r.kind + '</td><td>' + r.n + '</td><td>' + fmt(r.taken) + ' t</td><td>' +
        (r.rate > 0 ? '<span class="best">' + r.rate.toLocaleString('de-DE', {maximumFractionDigits: 1}) + ' t</span>' : '<span class="mut">keine</span>') + '</td><td>' + (r.full_h != null ? r.full_h.toLocaleString('de-DE', {maximumFractionDigits: 1}) + ' Std.' : '<span class="mut">noch nicht voll</span>') + '</td><td class="mut">' + esc(dts(r.last)) + '</td></tr>').join('') + '</tbody></table>'
      : '<div class="empty">Noch keine Erholung beobachtet. Dafür braucht EDCJ einen Kauf oder Verkauf von dir und eine spätere Marktaufnahme derselben Station.</div>';
  }catch(e){}
}
$('sast').addEventListener('change', () => { SA.key = $('sast').value; try { localStorage.setItem('edl_sakte', SA.key); } catch(e) {} renderSakte(); });
$('sarecall').addEventListener('click', e => { const tr = e.target.closest('tr[data-k]'); if (!tr) return; SA.key = tr.dataset.k; $('sast').value = SA.key; try { localStorage.setItem('edl_sakte', SA.key); } catch(x) {} renderSakte(); window.scrollTo(0, 0); });
async function renderSakte(){
  const out = ['sacard', 'sanote', 'saprices', 'sagood', 'satrades', 'sarec'].map($);
  if (!SA.key){ $('sameta').textContent = ' '; $('sacard').innerHTML = '<div class="empty">Station wählen. Es werden alle Stationen angeboten, die du besucht oder deren Markt du gespeichert hast.</div>'; ['sanote', 'saprices', 'sagood', 'satrades', 'sarec'].forEach(i => { $(i).innerHTML = ''; }); return; }
  let d;
  try{ d = await (await fetch('/api/stationsakte?op=view&key=' + encodeURIComponent(SA.key), {cache: 'no-store'})).json(); }catch(e){ return; }
  if (d.error){ $('sacard').innerHTML = '<div class="empty">' + esc(d.error) + '</div>'; return; }
  const c = d.card, kv = rows => '<table class="mt"><tbody>' + rows.filter(r => r).map(r => '<tr><td class="mut">' + r[0] + '</td><td>' + r[1] + '</td></tr>').join('') + '</tbody></table>';
  const pd = c.pads ? (c.pads.s ? 'S ' : '') + (c.pads.m ? 'M ' : '') + (c.pads.l ? 'L' : '') : null;
  $('sameta').textContent = c.type || ' ';
  $('sacard').innerHTML = '<div class="row2" style="align-items:flex-start;gap:30px;flex-wrap:wrap"><div>' + kv([
    ['Name', esc(c.name)], ['System', SYS(c.system)], ['Art', esc(c.type || '-')], ['Fraktion', esc(c.faction || '-')], ['Regierung', esc(c.gov || '-')], ['Wirtschaft', esc(c.eco || '-')],
    ['Entfernung zum Stern', c.dist_ls ? fmt(c.dist_ls) + ' ls' : '-']]) + '</div><div>' + kv([
    ['Besuche', c.visits ? c.visits + ' (erstmals ' + esc(dts(c.first)) + ', zuletzt ' + esc(dts(c.last)) + ')' : '-'],
    ['Landeplätze', pd == null ? '<span class="mut">unbekannt (nie dort angedockt)</span>' : pd.trim() + ' <small class="mut">(' + c.pads.s + ' S, ' + c.pads.m + ' M, ' + c.pads.l + ' L)</small>'],
    ['Dienste', c.services.length ? c.services.map(x => '<span>' + esc(x) + '</span>').join(', ') : '<span class="mut">' + (c.services_known ? 'keine Angaben' : 'noch nicht erfasst: wird bei deinem nächsten Andocken gespeichert') + '</span>'],
    ['Marktdaten', d.market ? d.market.snaps + ' Aufnahmen, zuletzt ' + esc(dts(d.market.last)) + (d.market.age_h != null ? ' <small class="mut">(Alter ' + (d.market.age_h < 48 ? Math.round(d.market.age_h) + ' Std.' : (d.market.age_h / 24).toFixed(1).replace('.', ',') + ' Tage') + ')</small>' : '') : '<span class="mut">keine</span>']]) + '</div></div>';
  $('sanote').innerHTML = c.note ? '<div style="white-space:pre-wrap;margin-top:6px"><b>Deine Notiz</b> <small class="mut">' + esc(dts(c.note.ts)) + '</small><br>' + esc(c.note.txt) + '</div>' : '<div class="mut" style="margin-top:6px">Keine Notiz. Unter Logbuch → Notizen kannst du eine anlegen.</div>';
  const gl = (title, rows, f) => '<div style="min-width:280px"><b>' + title + '</b><table class="mt"><tbody>' + (rows.length ? rows.map(f).join('') : '<tr><td class="mut">keine</td><td></td></tr>') + '</tbody></table></div>';
  $('sagood').innerHTML = d.market ? '<div class="row2" style="align-items:flex-start;gap:30px;flex-wrap:wrap">' +
    gl('Hier gut zu verkaufen', d.good_sell, x => '<tr><td>' + esc(x.name) + '</td><td class="num">' + fmt(x.price) + ' Cr <span class="' + sdevCls(x.dev, true) + '">' + spct(x.dev) + '</span><small class="mut">gegenüber ' + esc(x.src) + ' ' + fmt(x.base) + ' · Nachfrage ' + fmt(x.demand) + '</small></td></tr>') +
    gl('Hier günstig zu kaufen', d.good_buy, x => '<tr><td>' + esc(x.name) + '</td><td class="num">' + fmt(x.price) + ' Cr <span class="' + sdevCls(x.dev, false) + '">' + spct(x.dev) + '</span><small class="mut">gegenüber ' + esc(x.src) + ' ' + fmt(x.base) + ' · Bestand ' + fmt(x.stock) + '</small></td></tr>') + '</div>'
    : '<div class="empty">Für diese Station sind keine Marktdaten gespeichert.</div>';
  $('saprices').innerHTML = d.prices.length ? '<table class="mt"><thead><tr><th>Ware</th><th>Verkauf jetzt</th><th>Dein Schnitt (Verkauf)</th><th>Abweichung</th><th>Einkauf jetzt</th><th>Dein Schnitt (Einkauf)</th><th>Abweichung</th><th>Aufnahmen</th></tr></thead><tbody>' +
    d.prices.map(x => '<tr><td class="bn">' + esc(x.name) + '</td><td>' + (x.sell_dev != null ? fmt(x.sell) : '-') + '</td><td class="mut">' + (x.sell_dev != null ? fmt(x.sell_avg) + '<small>' + fmt(x.sell_min) + ' bis ' + fmt(x.sell_max) + '</small>' : '-') + '</td><td class="' + (x.sell_dev != null ? sdevCls(x.sell_dev, true) : '') + '">' + (x.sell_dev != null ? spct(x.sell_dev) : '-') +
      '</td><td>' + (x.buy_dev != null ? fmt(x.buy) : '-') + '</td><td class="mut">' + (x.buy_dev != null ? fmt(x.buy_avg) + '<small>' + fmt(x.buy_min) + ' bis ' + fmt(x.buy_max) + '</small>' : '-') + '</td><td class="' + (x.buy_dev != null ? sdevCls(x.buy_dev, false) : '') + '">' + (x.buy_dev != null ? spct(x.buy_dev) : '-') + '</td><td>' + x.n + '</td></tr>').join('') + '</tbody></table>' +
    '<div class="mut" style="margin-top:6px">Verglichen wird der aktuelle Preis mit dem Durchschnitt deiner früheren Aufnahmen derselben Station. Grün ist besser für dich, rot schlechter. Ab zwei früheren Aufnahmen.</div>'
    : '<div class="empty">' + (d.market ? 'Noch zu wenige Aufnahmen für einen Vergleich: es braucht mindestens drei Aufnahmen derselben Station.' : 'Keine Marktdaten.') + '</div>';
  $('satrades').innerHTML = d.trades.length ? '<table class="mt"><thead><tr><th>Ware</th><th>Gekauft</th><th>Verkauft</th><th>Gewinn</th></tr></thead><tbody>' + d.trades.map(t => '<tr><td class="bn">' + esc(t.name) + '</td><td>' + (t.bought ? fmt(t.bought) + ' t <small class="mut">' + fmt(t.spent) + ' Cr</small>' : '-') + '</td><td>' + (t.sold ? fmt(t.sold) + ' t <small class="mut">' + fmt(t.earned) + ' Cr</small>' : '-') + '</td><td class="' + (t.profit > 0 ? 'best' : '') + '">' + (t.sold ? scr(t.profit) : '-') + '</td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">Du hast hier noch nichts gekauft oder verkauft.</div>';
  $('sarec').innerHTML = d.recovery.length ? '<table class="mt"><thead><tr><th>Ware</th><th>Was</th><th>Beobachtungen</th><th>Typisch genommen</th><th>Erholung pro Std. (mindestens)</th><th>Wieder voll nach (höchstens)</th><th>Davon wieder voll</th><th>Zuletzt</th></tr></thead><tbody>' +
    d.recovery.map(r => '<tr><td class="bn">' + esc(r.name) + '</td><td>' + r.kind + '</td><td>' + r.n + '</td><td>' + fmt(r.taken) + ' t</td><td>' + (r.rate > 0 ? r.rate.toLocaleString('de-DE', {maximumFractionDigits: 1}) + ' t' : '<span class="mut">keine</span>') + '</td><td>' + (r.full_h != null ? r.full_h.toLocaleString('de-DE', {maximumFractionDigits: 1}) + ' Std.' : '<span class="mut">noch nicht voll</span>') + '</td><td>' + r.full_n + ' von ' + r.n + '</td><td class="mut">' + esc(dts(r.last)) + '</td></tr>').join('') + '</tbody></table>' +
    '<div class="mut" style="margin-top:6px">Gemessen an deinen Käufen (Bestand) und Verkäufen (Nachfrage): Menge vor deinem Handel, minus das Gehandelte, verglichen mit deiner nächsten Marktaufnahme. Das Spiel schreibt den Markt nur beim Öffnen, deshalb sind die Zeiten Grenzwerte: „wieder voll nach“ heißt, spätestens dann war die Menge zurück. Es sind Beobachtungen, keine Vorhersage.</div>'
    : '<div class="empty">Noch keine Erholung beobachtet. Dafür braucht EDCJ einen Kauf oder Verkauf von dir hier und eine spätere Marktaufnahme. Öffne bei deinen Besuchen jedes Mal den Markt.</div>';
}
let NT = {notes: [], stations: [], systems: []};
const noteOf = (kind, name) => (NT.notes.find(n => n.kind === kind && n.name === name) || {}).txt || '';
async function loadNotes(){
  try{ NT = await (await fetch('/api/notes', {cache:'no-store'})).json(); renderNotes(); }catch(e){}
}
function renderNotes(){
  const q = $('ntq').value.trim().toLowerCase();
  const list = NT.notes.filter(n => !q || (n.name + ' ' + n.txt).toLowerCase().includes(q));
  $('ntmeta').textContent = NT.notes.length + ' Notizen';
  $('ntlist').innerHTML = ($('ntkind').value === 'station' ? NT.stations : NT.systems).map(x => '<option value="' + esc(x) + '">').join('');
  $('ntres').innerHTML = list.length ? '<table class="mt"><thead><tr><th>Art</th><th>Name</th><th>Notiz</th><th>Geändert</th><th></th></tr></thead><tbody>' +
    list.map((n, i) => '<tr><td>' + (n.kind === 'station' ? 'Station' : 'System') + '</td><td class="bn">' + esc(n.name) + '</td><td style="white-space:pre-wrap">' + esc(n.txt) + '</td><td class="mut">' + dts(n.ts) +
      '</td><td><button class="xbtn" data-ne="' + i + '">Bearbeiten</button> <button class="xbtn" data-nd="' + i + '" style="background:var(--lilac)">Löschen</button></td></tr>').join('') + '</tbody></table>'
    : '<div class="empty">' + (NT.notes.length ? 'Keine Treffer.' : 'Noch keine Notizen.') + '</div>';
  NT._list = list;
}
async function noteSend(kind, name, txt){
  const r = await fetch('/api/notes', {method:'POST', headers:{'X-EDCJ':'1', 'Content-Type':'application/json'}, body: JSON.stringify({kind, name, txt})});
  const d = await r.json(); if (d.error) throw new Error(d.error);
  NT = d; renderNotes();
}
$('ntkind').addEventListener('change', renderNotes);
$('ntq').addEventListener('input', renderNotes);
$('ntname').addEventListener('input', () => { const t = noteOf($('ntkind').value, $('ntname').value.trim()); if (t) $('nttxt').value = t; });
$('ntclear').addEventListener('click', () => { $('ntname').value = ''; $('nttxt').value = ''; $('ntmsg').textContent = '\u00a0'; });
$('ntsave').addEventListener('click', async () => {
  const name = $('ntname').value.trim();
  if (!name){ $('ntmsg').textContent = 'Bitte einen Namen eintragen.'; return; }
  try{ await noteSend($('ntkind').value, name, $('nttxt').value); $('ntmsg').textContent = $('nttxt').value.trim() ? 'Gespeichert.' : 'Notiz gelöscht.'; loadMarket(true); }
  catch(e){ $('ntmsg').textContent = 'Fehler: ' + e.message; }
});
$('ntres').addEventListener('click', async e => {
  const b = e.target.closest('button'); if (!b) return;
  const n = (NT._list || [])[+(b.dataset.ne != null ? b.dataset.ne : b.dataset.nd)]; if (!n) return;
  if (b.dataset.ne != null){ $('ntkind').value = n.kind; renderNotes(); $('ntname').value = n.name; $('nttxt').value = n.txt; $('nttxt').focus(); }
  else { try{ await noteSend(n.kind, n.name, ''); }catch(x){} }
});
loadNotes();
['leg', 'pad', 'age'].forEach(k => $('tr' + k).addEventListener('change', e => {
  TRS[k] = e.target.value; try { localStorage.setItem('edl_trd', JSON.stringify(TRS)); } catch(x) {} loadTrades(); loadLoops();
}));
document.querySelectorAll('.chips button[data-ts]').forEach(b => b.addEventListener('click', () => { trd.sort = b.dataset.ts; trd.key = ''; renderTrades(); }));
$('trres').addEventListener('click', e => {
  const th = e.target.closest('th[data-tr]'); if (!th) return;
  const k = th.dataset.tr, c = TR_COLS.find(x => x[0] === k);
  if (trd.key === k) trd.dir = -trd.dir; else { trd.key = k; trd.dir = c[3]; }
  renderTrades();
});
$('trres').addEventListener('click', e => { const tr = e.target.closest('tr[data-m]'); if (!tr) return; showTab('ana'); anaPick(tr.dataset.m, tr.dataset.c); });

function hl(t, terms){
  if (!terms.length) return esc(t);
  const re = new RegExp('(' + terms.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi');
  return t.split(re).map((p, i) => i % 2 ? '<mark>' + esc(p) + '</mark>' : esc(p)).join('');
}
let searchTimer = null;
async function doSearch(){
  const q = $('sq').value.trim();
  if (!q){ $('smeta').textContent = '\u00a0'; $('sres').innerHTML = '<div class="empty">Suchbegriff eingeben.</div>'; return; }
  try{
    const d = await (await fetch('/api/search?q=' + encodeURIComponent(q), {cache:'no-store'})).json();
    $('smeta').textContent = d.total + ' Treffer' + (d.total > d.results.length ? ' (erste ' + d.results.length + ')' : '');
    $('sres').innerHTML = d.results.length ? d.results.map(r =>
      '<div class="sr"><div class="sh"><span class="sy">' + (r.system ? SYSH(r.system, hl(r.system, d.terms)) : 'System unbekannt') + '</span><span>' + esc(r.time || 'Zusammenfassung') +
      '</span><span>' + esc(r.session) + '</span></div><div class="stx">' + hl(r.text, d.terms) + '</div></div>').join('')
      : '<div class="empty">Keine Treffer im Captain\'s Log.</div>';
  }catch(e){}
}
$('sq').addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(doSearch, 300); });
document.querySelectorAll('.chips button[data-q]').forEach(b => b.addEventListener('click', () => { $('sq').value = b.dataset.q; doSearch(); }));

$('offbtn').addEventListener('click', async () => {
  $('offbtn').disabled = true;
  try { await fetch('/api/shutdown', {method: 'POST', headers: {'X-EDCJ': '1'}}); } catch(e) {}
  window.__off = true;
  $('offbox').innerHTML = '<div class="big" style="font-size:56px">Offline</div><div class="sub">Das Programm wurde beendet. Du kannst dieses Fenster jetzt schließen.</div>';
  setTimeout(() => { try { window.close(); } catch(e) {} }, 800);
});

/* ---------- Kampf / Karriere / Bilanz / Flotte ---------- */
const CR = {
  kampf:   {name:'Kampf',   subs:[['k_over','Übersicht'],['k_enemy','Gegner'],['k_places','Orte'],['k_sess','Sessions'],['k_conf','Konflikte'],['k_loss','Verluste & Strafen']]},
  karriere:{name:'Karriere',subs:[['rank','Ränge & Ruf'],['expl','Erkundung'],['disc','Entdeckungen'],['land','Landungen'],['rec','Rekorde'],['pp','Powerplay'],['stat','Lebensstatistik'],['eng','Ingenieure'],['mat','Materialien'],['need','Baupläne']]},
  bilanz:  {name:'Bilanz',  subs:[['b_in','Einnahmen'],['b_trade','Handelsgewinn'],['wares','Handelsbuch'],['b_mis','Missionen'],['b_wealth','Vermögen'],['b_time','Zeitprofil'],['report','Bericht']]},
  flotte:  {name:'Flotte',  subs:[['ships','Schiffe'],['mods','Module'],['cmp','Vergleich']]},
  akte: {name:'Personalakte', subs:[['pa','Personalakte']]},
  kolo: {name:'Im Bau', subs:[['ko_bau','Im Bau']]},
  kolm: {name:'Meine Kolonien', subs:[['ko_meine','Meine Kolonien']]},
  rueck: {name:'Rückblick', subs:[['rb_week','Wochen'],['rb_month','Monate'],['rb_ware','Gewinn je Ware'],['rb_route','Routen'],['rb_fw','Fracht gegen Weite'],['rb_verm','Vermögen']]},
  lmil: {name:'Meilensteine', subs:[['ml_over','Meilensteine'],['ml_orden','Orden']]},
  gaps: {name:'Lücken-Liste', subs:[['g_mk','Märkte'],['g_pos','Koordinaten']]},
  bio: {name:'Bio-Atlas', subs:[['bi_species','Arten'],['bi_sites','Fundorte']]},
  bgs: {name:'Fraktions-Verlauf', subs:[['b_over','Eingriffe & Einfluss'],['b_log','Chronik']]},
  carrier: {name:'Fleet Carrier', subs:[['c_over','Übersicht'],['c_stock','Bestand'],['c_jumps','Sprünge & Tritium'],['c_fin','Finanzen & Aufträge']]},
  missions:{name:'Missionen', subs:[['ms_open','Offen'],['ms_dest','Nach Ziel'],['ms_hist','Verlauf']]},
  mining:  {name:'Mining',  subs:[['m_over','Übersicht'],['m_sess','Sessions'],['m_ore','Erze & Prospektoren'],['m_ring','Ringe'],['m_sell','Verkauf & Abnehmer']]}
};
const crSub = {kampf:'k_over', karriere:'rank', bilanz:'b_in', flotte:'ships', mining:'m_over', missions:'ms_open', carrier:'c_over', bgs:'b_over', bio:'bi_species', gaps:'g_mk', akte:'pa', lmil:'ml_over', rueck:'rb_week', kolo:'ko_bau', kolm:'ko_meine'};
const crSort = {};   // "tab|sub|block" -> [spalte, richtung]
const crBlocks = {}; // tab -> aktuelle Bloecke
const crLast = {};
let crTick = 0;
async function capi(p){ return (await fetch('/api/career?' + new URLSearchParams(p), {cache:'no-store'})).json(); }
function crFmt(v, t){
  if (v == null || v === '') return '-';
  if (t === 'd') return dts(v);
  if (t === 't') return esc(v);
  if (typeof v !== 'number') return esc(v);
  if (t === 'n') return fmt(v);
  if (t === 'cr') return fmt(v) + ' Cr';
  if (t === 'r') return v.toLocaleString('de-DE', {minimumFractionDigits:1, maximumFractionDigits:1});
  if (t === 'p') return v.toLocaleString('de-DE', {minimumFractionDigits:1, maximumFractionDigits:1}) + ' %';
  if (t === 'f') return (v * 100).toLocaleString('de-DE', {minimumFractionDigits:1, maximumFractionDigits:1}) + ' %';
  if (t === 'h') return v.toLocaleString('de-DE', {minimumFractionDigits:1, maximumFractionDigits:1}) + ' h';
  if (t === 's'){ const s = Math.floor(v), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return h + 'h ' + pad(m) + 'm'; }
  return esc(v);
}
const crNum = t => t !== 't' && t !== 'd';
function crTable(tab, b, bi){
  const key = tab + '|' + crSub[tab] + '|' + bi;
  let rows = (b.rows || []).slice();
  const s = crSort[key];
  if (s){
    const c = s[0], dir = s[1];
    rows.sort((x, y) => {
      const a = x[c], z = y[c];
      if (a == null && z == null) return 0;
      if (a == null) return 1;
      if (z == null) return -1;
      return (typeof a === 'number' && typeof z === 'number' ? a - z : String(a).localeCompare(String(z), 'de')) * dir;
    });
  }
  if (!rows.length) return '<div class="empty">Keine Daten im gewählten Zeitraum.</div>';
  let h = '<table class="mt"><thead><tr>';
  b.cols.forEach((c, i) => {
    const on = s && s[0] === i;
    h += '<th class="' + (crNum(c[1]) ? 'num ' : '') + 'srt" data-sc="' + i + '" data-sb="' + bi + '">' + esc(c[0]) + (on ? (s[1] > 0 ? ' ▲' : ' ▼') : '') + '</th>';
  });
  h += '</tr></thead><tbody>';
  rows.slice(0, 400).forEach(r => {
    h += '<tr>';
    b.cols.forEach((c, i) => { h += '<td class="' + (crNum(c[1]) ? 'num' : '') + '">' + (c[1] === 't' && /system$/i.test(c[0]) && r[i] ? SYS(r[i]) : crFmt(r[i], c[1])) + '</td>'; });
    h += '</tr>';
  });
  return h + '</tbody></table>' + (rows.length > 400 ? '<div class="mut">… ' + (rows.length - 400) + ' weitere Zeilen (Spalte sortieren oder Zeitraum verkleinern)</div>' : '');
}
function crKv(b){
  let h = '<table class="mt"><tbody>';
  b.kv.forEach(r => { h += '<tr><td>' + esc(r[0]) + '</td><td class="num">' + crFmt(r[1], r[2]) + '</td></tr>'; });
  return h + '</tbody></table>';
}
const CRCOL = ['var(--orange)', 'var(--sky)', 'var(--red)', 'var(--tan)', 'var(--lilac)', 'var(--blue)', 'var(--peach)'];
function crShort(v){
  const a = Math.abs(v), s = v < 0 ? '-' : '', nf = (x, d) => x.toLocaleString('de-DE', {maximumFractionDigits: d});
  if (a >= 1e9) return s + nf(a / 1e9, 2) + ' Mrd';
  if (a >= 1e6) return s + nf(a / 1e6, 1) + ' Mio';
  if (a >= 1e3) return s + nf(a / 1e3, 0) + ' Tsd';
  return s + nf(a, 0);
}
function crChart(ch){
  const n = (ch.labels || []).length;
  if (!n) return '<div class="empty">Keine Daten im gewählten Zeitraum.</div>';
  const W = 720, H = 230, L = 70, R = 10, T = 10, B = 26, ser = ch.series || [], line = ch.type === 'line', stack = ch.type === 'stack';
  let hi = 0, lo = 0;
  for (let i = 0; i < n; i++){
    if (stack){ let t = 0; ser.forEach(s => { t += Math.max(0, s.vals[i] || 0); }); hi = Math.max(hi, t); }
    else ser.forEach(s => { hi = Math.max(hi, s.vals[i] || 0); });
  }
  if (line){
    lo = Infinity; ser.forEach(s => s.vals.forEach(v => { if (v != null) lo = Math.min(lo, v); }));
    if (!isFinite(lo)) lo = 0; const pad = (hi - lo) * 0.08 || 1; lo = Math.max(0, lo - pad); hi += pad;
  }
  if (hi <= lo) hi = lo + 1;
  const X = i => L + (i + 0.5) * (W - L - R) / n, Y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo)), bw = (W - L - R) / n;
  let g = '';
  for (let k = 0; k <= 4; k++){
    const v = lo + (hi - lo) * k / 4, y = Y(v);
    g += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + y + '" y2="' + y + '" stroke="#333" stroke-width="1"/><text x="' + (L - 6) + '" y="' + (y + 4) + '" text-anchor="end" fill="#aaa" font-size="11">' + crShort(v) + '</text>';
  }
  const step = Math.max(1, Math.ceil(n / 8));
  for (let i = 0; i < n; i += step) g += '<text x="' + X(i) + '" y="' + (H - 8) + '" text-anchor="middle" fill="#aaa" font-size="11">' + esc(ch.labels[i]) + '</text>';
  if (line){
    ser.forEach((s, si) => {
      const pts = s.vals.map((v, i) => v == null ? null : [X(i), Y(v), v, i]).filter(Boolean);
      g += '<polyline fill="none" stroke="' + CRCOL[si % CRCOL.length] + '" stroke-width="2.5" points="' + pts.map(p => p[0] + ',' + p[1]).join(' ') + '"/>';
      pts.forEach(p => { g += '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="3.5" fill="' + CRCOL[si % CRCOL.length] + '"><title>' + esc(ch.labels[p[3]] + ' · ' + s.name + ': ' + fmt(p[2]) + ' Cr') + '</title></circle>'; });
    });
  } else {
    for (let i = 0; i < n; i++){
      let acc = 0;
      ser.forEach((s, si) => {
        const v = Math.max(0, s.vals[i] || 0); if (!v) return;
        const y0 = Y(acc), y1 = Y(acc + v);
        g += '<rect x="' + (L + i * bw + bw * 0.15) + '" y="' + y1 + '" width="' + (bw * 0.7) + '" height="' + Math.max(1, y0 - y1) + '" fill="' + CRCOL[si % CRCOL.length] + '"><title>' + esc(ch.labels[i] + ' · ' + s.name + ': ' + fmt(v) + ' Cr') + '</title></rect>';
        acc += v;
      });
    }
  }
  const leg = ser.length > 1 ? '<div class="crleg">' + ser.map((s, si) => '<span><i style="background:' + CRCOL[si % CRCOL.length] + '"></i><span>' + esc(s.name) + '</span></span>').join('') + '</div>' : '';
  return '<svg viewBox="0 0 ' + W + ' ' + H + '" class="crchart" role="img" aria-label="' + esc(ch.labels[0] + ' – ' + ch.labels[n - 1]) + '">' + g + '</svg>' + leg;
}
const crAlt = {}, crData = {}, crFilt = {q: '', has: false};
function crApplyFilt(tab){
  const q = crFilt.q.trim().toLowerCase();
  document.querySelectorAll('#crbody-' + tab + ' tr[data-w]').forEach(tr => { tr.hidden = !!((q && tr.dataset.w.toLowerCase().indexOf(q) < 0) || (crFilt.has && tr.dataset.has !== '1')); });
}
function crSimple(cols, rows){
  if (!rows.length) return '<div class="empty">Keine Daten.</div>';
  return '<table class="mt"><thead><tr>' + cols.map(c => '<th class="' + (crNum(c[1]) ? 'num' : '') + '">' + esc(c[0]) + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + cols.map((c, i) => '<td class="' + (crNum(c[1]) ? 'num' : '') + '">' + (c[1] === 'in' ? '<input type="number" min="0" step="1" class="crin" data-w="' + esc(r[0]) + '" value="' + (r[i] == null ? '' : Math.round(r[i])) + '" placeholder="0" aria-label="' + esc(c[0]) + '">' : c[1] === 't' && /system$/i.test(c[0]) && r[i] ? SYS(r[i]) : crFmt(r[i], c[1])) + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
}
function crGroups(gs){
  return gs.map(g => '<details class="ssd"' + (g.open ? ' open' : '') + '><summary><b>' + esc(g.label) + '</b>' + (g.sys ? ' · ' + SYS(g.sys) : '') + (g.sum || []).map(x => ' · ' + crFmt(x[0], 'n') + ' <span>' + esc(x[1]) + '</span>').join('') + '</summary><div class="tscroll">' + crSimple(g.cols, g.rows) + '</div></details>').join('');
}
function crRender(tab, d){
  crData[tab] = d;
  const el = $('crbody-' + tab);
  crBlocks[tab] = d.blocks || [];
  let h = '';
  if (d.error) h += '<div class="empty">Fehler: ' + esc(d.error) + '</div>';
  if (d.kpi && d.kpi.length){
    h += '<div class="kpis">';
    d.kpi.forEach(k => { h += '<div class="kpi"><small>' + esc(k[0]) + '</small><b>' + crFmt(k[1], k[2]) + '</b></div>'; });
    h += '</div>';
  }
  if (d.note) h += '<div class="mut crnote">' + esc(d.note) + '</div>';
  crBlocks[tab].forEach((b, bi) => {
    h += '<h3 class="crh">' + esc(b.title) + '</h3>';
    if (b.chart){ h += crChart(b.chart); return; }
    if (b.stock){
      h += '<div class="row2"><input type="search" class="sel crfilter" placeholder="Ware suchen …" value="' + esc(crFilt.q) + '" aria-label="Ware suchen">' +
        '<label class="mut"><input type="checkbox" class="crhas"' + (crFilt.has ? ' checked' : '') + '> nur mit Bestand oder Bedarf</label></div>';
      if (b.note) h += '<div class="mut crnote">' + esc(b.note) + '</div>';
      h += '<div class="tscroll"><table class="mt"><thead><tr><th>Ware</th><th>Kategorie</th><th class="num">Im Carrier t</th><th class="num">Baustelle fehlt t</th><th class="num">Ändern (+ / −)</th></tr></thead><tbody>' +
        b.stock.rows.map(r => '<tr data-w="' + esc(r[0]) + '" data-has="' + (r[2] > 0 || r[3] > 0 ? 1 : 0) + '"><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td><td class="num"><b>' + fmt(r[2]) + '</b></td><td class="num">' + (r[3] ? fmt(r[3]) : '-') +
          '</td><td class="num"><input type="number" step="1" class="crdelta" data-w="' + esc(r[0]) + '" placeholder="± t" aria-label="Menge ändern"> <button class="xbtn crok" data-w="' + esc(r[0]) + '">OK</button></td></tr>').join('') + '</tbody></table></div>';
      return;
    }
    if (b.alts){
      const key = tab + '|' + b.title, cur = Math.min(crAlt[key] || 0, b.alts.length - 1), a = b.alts[cur];
      h += '<div class="chips crsw" data-k="' + esc(key) + '">' + b.alts.map((x, i) => '<button data-i="' + i + '" class="' + (i === cur ? 'on' : '') + '">' + esc(x.label) + '</button>').join('') + '</div>';
      if (a.note) h += '<div class="mut crnote">' + esc(a.note) + '</div>';
      h += a.groups ? crGroups(a.groups) : '<div class="tscroll">' + crSimple(a.cols, a.rows) + '</div>';
      return;
    }
    if (b.groups){
      if (b.note) h += '<div class="mut crnote">' + esc(b.note) + '</div>';
      h += crGroups(b.groups);
      return;
    }
    if (b.note) h += '<div class="mut crnote">' + esc(b.note) + '</div>';
    h += '<div class="tscroll" id="crt-' + tab + '-' + bi + '">' + (b.kv ? crKv(b) : crTable(tab, b, bi)) + '</div>';
  });
  if (!h) h = '<div class="empty">Keine Daten.</div>';
  if (tab === 'bilanz' && crSub.bilanz === 'report') h += crReportBtns();
  el.innerHTML = h;
  if (el.querySelector('tr[data-w]')) crApplyFilt(tab);
  if (tab === 'bilanz') crBindReport();
}
function crReportText(){
  const out = [];
  (crBlocks.bilanz || []).forEach(b => {
    out.push(b.title); out.push('='.repeat(b.title.length));
    if (b.cols) out.push(b.cols.map(c => c[0]).join(' | '));
    (b.rows || []).forEach(r => out.push(r.map(x => String(x)).join(' | ')));
    out.push('');
  });
  return out.join('\n');
}
function crReportBtns(){
  return '<div class="row2 noprint" style="margin-top:12px"><button class="xbtn" id="repsave">Als Textdatei speichern</button>' +
    '<button class="xbtn" id="repprint">Drucken</button></div>';
}
function crBindReport(){
  const a = $('repsave'), b = $('repprint');
  if (a) a.onclick = () => {
    const bl = new Blob(['\ufeff' + crReportText()], {type:'text/plain;charset=utf-8'});
    const l = document.createElement('a'); l.href = URL.createObjectURL(bl);
    l.download = 'ed_bericht_' + new Date().toISOString().slice(0,10) + '.txt'; l.click();
    setTimeout(() => URL.revokeObjectURL(l.href), 2000);
  };
  if (b) b.onclick = () => window.print();
}
const MAPS = {pts:[], cur:null, z:1, ox:0, oy:0, drag:null, hov:null};
async function loadMap(){
  try{
    const r = await fetch('/api/market?op=map'); const d = await r.json();
    MAPS.pts = d.points || []; MAPS.cur = d.cur || null;
    $('mapmeta').textContent = MAPS.pts.length + ' Systeme';
    drawMap();
  }catch(e){}
}
function mapXY(p){ return $('mapproj').value === 'xy' ? [p[1], -p[2]] : [p[1], -p[3]]; }
function mapBase(cv){
  const pts = MAPS.pts.map(mapXY); if (!pts.length) return null;
  let x0 = Math.min(...pts.map(q => q[0])), x1 = Math.max(...pts.map(q => q[0]));
  let y0 = Math.min(...pts.map(q => q[1])), y1 = Math.max(...pts.map(q => q[1]));
  const w = Math.max(x1 - x0, 1), h = Math.max(y1 - y0, 1);
  const sc = Math.min((cv.width - 60) / w, (cv.height - 60) / h);
  return {x0, y0, sc, w, h};
}
function mapProj(q, B, cv){
  return [30 + (q[0] - B.x0) * B.sc * MAPS.z + MAPS.ox, 30 + (q[1] - B.y0) * B.sc * MAPS.z + MAPS.oy];
}
function drawMap(){
  const cv = $('mapcv'); if (!cv) return;
  const r = cv.getBoundingClientRect(); if (!r.width) return;
  cv.width = Math.round(r.width * (window.devicePixelRatio || 1)); cv.height = Math.round(r.height * (window.devicePixelRatio || 1));
  const g = cv.getContext('2d'); g.clearRect(0, 0, cv.width, cv.height);
  const B = mapBase(cv); const css = getComputedStyle(document.documentElement);
  if (!B){ g.fillStyle = '#888'; g.font = '16px sans-serif'; g.fillText('Keine Koordinaten bekannt.', 20, 30); return; }
  const col = (css.getPropertyValue('--sky') || '#8cf').trim(), hot = (css.getPropertyValue('--orange') || '#fa0').trim();
  const dpr = window.devicePixelRatio || 1;
  let prev = null;
  MAPS.pts.forEach(p => {
    const [x, y] = mapProj(mapXY(p), B, cv);
    const rad = (3 + Math.min(6, Math.log2(1 + (p[4] || 1)))) * dpr;
    g.fillStyle = col; g.beginPath(); g.arc(x, y, rad, 0, 7); g.fill();
    p._x = x; p._y = y; p._r = rad;
  });
  if (MAPS.cur && MAPS.cur[1] != null){
    const [x, y] = mapProj(mapXY(MAPS.cur), B, cv);
    g.strokeStyle = hot; g.lineWidth = 3 * dpr; g.beginPath(); g.arc(x, y, 12 * dpr, 0, 7); g.stroke();
  }
  if (MAPS.hov){ g.fillStyle = '#fff'; g.font = (14 * dpr) + 'px sans-serif'; g.fillText(MAPS.hov[0], MAPS.hov._x + 10 * dpr, MAPS.hov._y - 8 * dpr); }
}
(function(){
  const cv = $('mapcv'); if (!cv) return;
  $('mapproj').onchange = () => { MAPS.z = 1; MAPS.ox = MAPS.oy = 0; drawMap(); };
  $('mapreset').onclick = () => { MAPS.z = 1; MAPS.ox = MAPS.oy = 0; drawMap(); };
  cv.addEventListener('wheel', e => {
    e.preventDefault(); const dpr = window.devicePixelRatio || 1, r = cv.getBoundingClientRect();
    const mx = (e.clientX - r.left) * dpr, my = (e.clientY - r.top) * dpr, f = e.deltaY < 0 ? 1.2 : 1 / 1.2;
    const nz = Math.max(0.5, Math.min(60, MAPS.z * f)), k = nz / MAPS.z;
    MAPS.ox = mx - (mx - MAPS.ox) * k; MAPS.oy = my - (my - MAPS.oy) * k; MAPS.z = nz; drawMap();
  }, {passive:false});
  const ptrs = new Map();  // Touch: Zwei-Finger-Zoom
  let pinch = 0;
  cv.addEventListener('pointerdown', e => { ptrs.set(e.pointerId, [e.clientX, e.clientY]); pinch = 0; MAPS.drag = [e.clientX, e.clientY, MAPS.ox, MAPS.oy]; cv.setPointerCapture(e.pointerId); });
  const pend = e => { ptrs.delete(e.pointerId); pinch = 0; MAPS.drag = ptrs.size === 1 ? (() => { const q = [...ptrs.values()][0]; return [q[0], q[1], MAPS.ox, MAPS.oy]; })() : null; };
  cv.addEventListener('pointerup', pend); cv.addEventListener('pointercancel', pend);
  cv.addEventListener('pointermove', e => {
    const dpr = window.devicePixelRatio || 1;
    if (ptrs.has(e.pointerId)) ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    if (ptrs.size === 2){
      const [a, b] = [...ptrs.values()], dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
      if (pinch){
        const r = cv.getBoundingClientRect(), mx = ((a[0] + b[0]) / 2 - r.left) * dpr, my = ((a[1] + b[1]) / 2 - r.top) * dpr;
        const nz = Math.max(0.5, Math.min(60, MAPS.z * dist / pinch)), k = nz / MAPS.z;
        MAPS.ox = mx - (mx - MAPS.ox) * k; MAPS.oy = my - (my - MAPS.oy) * k; MAPS.z = nz; drawMap();
      }
      pinch = dist; return;
    }
    if (MAPS.drag){
      MAPS.ox = MAPS.drag[2] + (e.clientX - MAPS.drag[0]) * dpr; MAPS.oy = MAPS.drag[3] + (e.clientY - MAPS.drag[1]) * dpr; drawMap(); return;
    }
    const r = cv.getBoundingClientRect(), mx = (e.clientX - r.left) * dpr, my = (e.clientY - r.top) * dpr;
    let best = null, bd = 1e9;
    MAPS.pts.forEach(p => { if (p._x == null) return; const d = Math.hypot(p._x - mx, p._y - my); if (d < bd){ bd = d; best = p; } });
    const h = best && bd < 14 * dpr ? best : null;
    if (h !== MAPS.hov){
      MAPS.hov = h;
      $('maptip').textContent = h ? h[0] + ' – ' + h[4] + ' Besuch(e) – ' + h[1].toFixed(1) + ' / ' + h[2].toFixed(1) + ' / ' + h[3].toFixed(1) : '\u00a0';
      drawMap();
    }
  });
  window.addEventListener('resize', () => { if (!$('tab-map').hidden) drawMap(); });
})();
const EXP_LIST = [['carrier','Fleet Carrier'],['missionen','Missionen'],['bergbau','Bergbau'],['hotspots','Ring-Hotspots'],['markt_aktuell','Märkte (aktuell)'],['markt_verlauf','Marktverlauf'],['ausruestung','Ausrüstung'],['entdeckungen','Entdeckungen'],['landungen','Landungen'],['notizen','Notizen'],['stationen','Stationen'],['systeme','Systeme + Koordinaten'],['spruenge','Sprünge'],['handel','Handel'],['buchungen','Buchungen'],['kampf','Kampf'],['ereignisse','Alle Ereignisse']];
(function(){
  const f = $('bakfile'); if (!f) return;
  f.addEventListener('change', async () => {
    const file = f.files[0]; if (!file) return;
    const m = $('bakmeta');
    if (!confirm('Backup "' + file.name + '" einspielen? Die aktuelle Datenbank wird dabei ersetzt (vorher wird sie automatisch gesichert).')) { f.value = ''; return; }
    m.textContent = 'Wird eingespielt …';
    try {
      const r = await fetch('/api/restore', {method:'POST', headers:{'X-EDCJ':'1'}, body: file});
      const d = await r.json();
      m.textContent = d.ok ? 'Fertig – Seite wird neu geladen. Alter Stand gesichert als ' + d.safety : 'Fehler: ' + (d.error || 'unbekannt');
      if (d.ok) setTimeout(() => location.reload(), 2500);
    } catch (e) { m.textContent = 'Fehler: ' + e; }
    f.value = '';
  });
})();
(function(){
  const el = $('explinks'); if (!el) return;
  el.innerHTML = EXP_LIST.map(x => '<a class="xbtn" style="text-decoration:none;display:inline-block" download href="/api/export?what=' + x[0] + '">' + esc(x[1]) + '</a>').join(' ');
})();
let hotTimer = null, hotFirst = true;
const HOT = {rows: [], hid: []};
async function hotSend(body){
  const r = await fetch('/api/hotx', {method:'POST', headers:{'X-EDCJ':'1', 'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const d = await r.json(); if (d.error) throw new Error(d.error);
  return d;
}
async function loadHidden(){
  try{
    const d = await (await fetch('/api/hotx', {cache:'no-store'})).json();
    const grp = {};
    (d.hidden || []).forEach(h => { const k = h.ring + '|' + h.ts; (grp[k] = grp[k] || {ring:h.ring, ts:h.ts, ms:[]}).ms.push(h.mineral); });
    HOT.hid = Object.values(grp);
    $('hothid').innerHTML = HOT.hid.length ? '<details><summary class="mut" style="cursor:pointer">' + HOT.hid.length + ' ausgeblendete Einträge (Wiederherstellen)</summary>' +
      '<table class="mt"><thead><tr><th>Ring</th><th>Eintrag</th><th>Gelöscht am</th><th></th></tr></thead><tbody>' +
      HOT.hid.map((h, i) => '<tr><td>' + esc(h.ring) + '</td><td>' + (h.ms.includes('*') ? 'ganzer Ring' : esc([...new Set(h.ms)].join(' / '))) + '</td><td class="mut">' + dts(h.ts) + '</td><td><button class="xbtn" data-hr="' + i + '">Wiederherstellen</button></td></tr>').join('') +
      '</tbody></table></details>' : '';
  }catch(e){}
}
$('hothid').addEventListener('click', async e => {
  const b = e.target.closest('button[data-hr]'); if (!b) return;
  const h = HOT.hid[+b.dataset.hr]; if (!h) return;
  try{ await hotSend(h.ms.includes('*') ? {op:'restore', ring:h.ring, all:true} : {op:'restore', ring:h.ring, minerals:h.ms}); loadHot(); }catch(x){}
});
$('hotres2').addEventListener('click', async e => {
  const b = e.target.closest('button[data-hd]'); if (!b) return;
  e.stopPropagation();
  const r = HOT.rows[+b.dataset.i]; if (!r) return;
  const ring = b.dataset.hd === 'r';
  if (!confirm(ring ? 'Alle Hotspots von "' + r.ring + '" ausblenden?\n\nDas Journal bleibt unverändert. Ein neuer Scan des Rings bringt die Daten zurück, und du kannst sie jederzeit wiederherstellen.'
                    : '"' + r.mineral + '" aus "' + r.ring + '" ausblenden?\n\nDas Journal bleibt unverändert. Ein neuer Scan des Rings bringt die Daten zurück, und du kannst sie jederzeit wiederherstellen.')) return;
  try{ await hotSend(ring ? {op:'del', ring:r.ring, all:true} : {op:'del', ring:r.ring, minerals:[r.raw || r.mineral, r.mineral]}); loadHot(); }catch(x){}
});
async function loadHot(){
  try{
    const d = await capi({op:'hot', q:$('hotq').value, ref:$('hotref').value, range:$('hotrange').value, cls:$('hotcls').value, res:$('hotres').value, sort:$('hotsort').value});
    if (d.error){ $('hotres2').innerHTML = '<div class="empty">' + esc(d.error) + '</div>'; return; }
    if (hotFirst || !$('hotmin').children.length){
      $('hotmin').innerHTML = d.minerals.map(m => '<option value="' + esc(m[0]) + '">').join('');
      $('hotsys').innerHTML = d.systems.map(x => '<option value="' + esc(x) + '">').join('');
      const keep = [$('hotcls').value, $('hotres').value];
      $('hotcls').innerHTML = '<option value="">alle</option>' + d.classes.map(x => '<option>' + esc(x) + '</option>').join('');
      $('hotres').innerHTML = '<option value="">alle</option>' + d.reserves.map(x => '<option>' + esc(x) + '</option>').join('');
      $('hotcls').value = keep[0]; $('hotres').value = keep[1]; hotFirst = false;
    }
    $('hotmeta').textContent = d.total + ' Treffer';
    HOT.rows = d.rows;
    loadHidden();
    $('hotctx').textContent = 'Bezug: ' + (d.ref || 'unbekannt') + (d.ref_known ? '' : ' (Koordinaten unbekannt, Entfernungen nicht berechenbar)') +
      ' · ' + d.rings_total + ' Ringe mit Hotspots gespeichert, ' + d.rings_scanned + ' Ringe gescannt · Hotspots kennt das Journal erst nach einem Detailscan (DSS) des Rings.';
    const dl = x => x == null ? 'unbekannt' : x < 0.05 ? 'hier' : x.toFixed(1).replace('.', ',') + ' Ly';
    $('hotres2').innerHTML = d.rows.length ? '<table class="mt"><thead><tr><th>Mineral</th><th>Hotspots</th><th>Ring</th><th>Ringtyp</th><th>Reserven</th><th>System</th><th>Entfernung</th><th>Vom Ankunftspunkt</th><th>Quelle</th><th>Gescannt</th><th></th></tr></thead><tbody>' +
      d.rows.map(r => '<tr data-sys="' + esc(r.system) + '"><td class="bn">' + esc(r.mineral) + '</td><td class="best">' + r.count + '</td><td>' + esc(r.parent) + ' <small class="mut">Ring ' + esc(String(r.letter).replace(/\s*(Ring|Belt)$/, '')) + '</small></td><td>' + esc(r.cls || '-') + '</td><td>' + esc(r.res || '-') +
        '</td><td>' + SYS(r.system) + '</td><td>' + dl(r.dist) + '</td><td>' + (r.ls ? fmt(Math.round(r.ls)) + ' ls' : '-') + '</td><td>' + (r.src === 'DSS' ? 'DSS' : 'FSS') + '</td><td class="mut">' + dts(r.ts) + '</td><td style="white-space:nowrap"><button class="xbtn" data-hd="m" data-i="' + d.rows.indexOf(r) + '" title="Nur dieses Mineral aus diesem Ring löschen">Eintrag</button> <button class="xbtn" data-hd="r" data-i="' + d.rows.indexOf(r) + '" style="background:var(--red)" title="Alle Hotspots dieses Rings löschen">Ring</button></td></tr>').join('') + '</tbody></table>'
      : '<div class="empty">Keine Hotspots mit diesen Einstellungen. Lockere Mineral, Umkreis oder Filter. Hotspots erscheinen erst, wenn du einen Ring mit dem Detailscanner (DSS) gescannt hast.</div>';
  }catch(e){}
}
['hotq', 'hotref'].forEach(i => $(i).addEventListener('input', () => { clearTimeout(hotTimer); hotTimer = setTimeout(loadHot, 300); }));
['hotrange', 'hotcls', 'hotres', 'hotsort'].forEach(i => $(i).addEventListener('change', loadHot));
$('hotcur').addEventListener('click', () => { $('hotref').value = ''; loadHot(); });
$('hotres2').addEventListener('click', e => { if (e.target.closest('button,.cp')) return; const tr = e.target.closest('tr[data-sys]'); if (tr){ $('hotref').value = tr.dataset.sys; loadHot(); } });
function crChips(tab){
  $('crch-' + tab).innerHTML = CR[tab].subs.map(s =>
    '<button data-cs="' + s[0] + '" class="' + (crSub[tab] === s[0] ? 'on' : '') + '">' + esc(s[1]) + '</button>').join('');
}
async function loadCr(tab, force){
  const days = $('crrange-' + tab).value;
  const sub = crSub[tab];
  try{
    const [st, d] = await Promise.all([capi({op:'status'}), capi({op:sub, days:days, mode:($('crmode-' + tab) ? $('crmode-' + tab).value : '')})]);
    const txt = JSON.stringify([st.state, st.rows, d]);
    let meta = '';
    if (st.state === 'importiere' && st.total) meta = 'Import läuft: ' + Math.min(99, Math.round(st.done / st.total * 100)) + ' %';
    else if (st.error) meta = 'Importfehler: ' + st.error;
    else meta = fmt(st.rows || 0) + ' Datensätze';
    $('crmeta-' + tab).textContent = meta;
    const mk = sub + days + ($('crmode-' + tab) ? $('crmode-' + tab).value : '') + txt;
    if (!force && crLast[tab] === mk) return;
    if (!force && document.activeElement && (document.activeElement.classList.contains('crdelta') || document.activeElement.classList.contains('crfilter'))) return;
    crLast[tab] = mk;
    crRender(tab, d);
  }catch(e){
    $('crmeta-' + tab).textContent = 'Keine Verbindung';
  }
}
function crInit(){
  const colors = {kampf:'red', karriere:'lilac', bilanz:'orange', flotte:'sky', mining:'tan', missions:'orange', carrier:'sky', bgs:'lilac', bio:'blue', gaps:'tan', akte:'lilac', lmil:'lilac', rueck:'orange', kolo:'sky', kolm:'sky'};
  Object.keys(CR).forEach(tab => {
    $('tab-' + tab).innerHTML = '<section class="panel span3" style="--c:var(--' + colors[tab] + ')"><div class="ph"><span>' + CR[tab].name +
      '</span><span id="crmeta-' + tab + '">&nbsp;</span></div><div class="pb"><div class="row2"><div class="chips" id="crch-' + tab + '" style="margin:0"></div>' +
      (tab === 'kampf' ? '<select id="crmode-kampf" class="sel" aria-label="Modus"><option value="space" selected>Nur Raumschiff</option><option value="ground">Nur zu Fuß / SRV</option><option value="">Alles zusammen</option></select>' : '') +
      '<select id="crrange-' + tab + '" class="sel" aria-label="Zeitraum"><option value="1">Letzte 24 Stunden</option><option value="7">Letzte 7 Tage</option>' +
      '<option value="30">Letzte 30 Tage</option><option value="90">Letzte 90 Tage</option><option value="0" selected>Gesamter Zeitraum</option></select></div>' +
      '<div id="crbody-' + tab + '"><div class="empty">Lade ...</div></div></div></section>';
    crChips(tab);
    $('crch-' + tab).addEventListener('click', ev => {
      const b = ev.target.closest('button[data-cs]');
      if (!b) return;
      crSub[tab] = b.dataset.cs; crChips(tab); crLast[tab] = ''; $('crbody-' + tab).innerHTML = '<div class="empty">Lade ...</div>'; loadCr(tab, true);
    });
    $('crrange-' + tab).addEventListener('change', () => { crLast[tab] = ''; loadCr(tab, true); });
    if ($('crmode-' + tab)) $('crmode-' + tab).addEventListener('change', () => { crLast[tab] = ''; loadCr(tab, true); });
    const crDelta = async inp => {
      if (!inp || inp.value === '' || isNaN(+inp.value)) return;
      try { await fetch('/api/kolonien', {method: 'POST', headers: {'X-EDCJ': '1'}, body: JSON.stringify({ware: inp.dataset.w, delta: +inp.value})}); } catch(e) {}
      crLast[tab] = ''; loadCr(tab, true);
    };
    $('crbody-' + tab).addEventListener('change', ev => { const inp = ev.target.closest('input.crdelta'); if (inp) crDelta(inp); });
    $('crbody-' + tab).addEventListener('input', ev => {
      if (ev.target.classList.contains('crfilter')){ crFilt.q = ev.target.value; crApplyFilt(tab); }
      else if (ev.target.classList.contains('crhas')){ crFilt.has = ev.target.checked; crApplyFilt(tab); }
    });
    $('crbody-' + tab).addEventListener('click', ev => {
      const ok = ev.target.closest('button.crok');
      if (ok){ crDelta(ok.parentNode.querySelector('input.crdelta')); return; }
      const sw = ev.target.closest('.crsw button');
      if (sw){ crAlt[sw.parentNode.dataset.k] = +sw.dataset.i; if (crData[tab]) crRender(tab, crData[tab]); return; }
      const th = ev.target.closest('th[data-sc]');
      if (!th) return;
      const bi = +th.dataset.sb, c = +th.dataset.sc, key = tab + '|' + crSub[tab] + '|' + bi;
      const cur = crSort[key];
      crSort[key] = [c, cur && cur[0] === c ? -cur[1] : (crNum(crBlocks[tab][bi].cols[c][1]) ? -1 : 1)];
      $('crt-' + tab + '-' + bi).innerHTML = crTable(tab, crBlocks[tab][bi], bi);
    });
  });
}
crInit();
window.__cr = 1;
{ const h0 = (location.hash || '').slice(1); if (CR[h0]) loadCr(h0, true); }

/* ---------- Settings: Reiter ein-/ausblenden, Thema ---------- */
const THEMES = {
  startrek: 'LCARS-Oberfläche wie auf einer Arbeitsstation der Enterprise-D: abgerundete Balken in Orange, Lila und Blau.',
  elite: 'Das heutige Elite-Dangerous-HUD: Orange auf Schwarz, kantige Flächen mit abgeschrägten Ecken, Cyan für Zahlen.',
  elite84: 'Elite von 1984 auf dem BBC Micro: Vektor-Look mit reinen Farben auf Schwarz, Monospace-Schrift und weißem Rahmen.',
  mono: 'Alter Monochrom-Monitor: nur Grün auf Schwarz wie ein Phosphor-Bildschirm, mit Leuchten und Zeilenraster.'
};
function setSave(){
  try { localStorage.setItem('edl_set', JSON.stringify(SET)); } catch(e) {}
  fetch('/api/settings', {method:'POST', headers:{'X-EDCJ':'1', 'Content-Type':'application/json'}, body: JSON.stringify(SET)}).catch(() => {});
}
function setApply(){
  document.documentElement.dataset.theme = SET.theme;
  document.querySelectorAll('button[data-tab]').forEach(b => { b.dataset.hide = tabHidden(b.dataset.tab) ? '1' : ''; });
  renderNav();
  const cur = TABS.find(n => !$('tab-' + n).hidden);
  if (cur && tabHidden(cur)) showTab(firstVisible());
}
function setRender(){
  const labels = {};
  document.querySelectorAll('button[data-tab]').forEach(b => { labels[b.dataset.tab] = b.textContent.trim(); });
  $('settabs').innerHTML = TABS.filter(t => t !== 'settings').map(t =>
    '<label><input type="checkbox" data-st="' + t + '"' + (tabHidden(t) ? '' : ' checked') + '> ' + esc(labels[t] || t) + '</label>').join('');
  $('settheme').value = SET.theme;
  $('setdesc').textContent = THEMES[SET.theme] || '';
  const n = SET.hidden.length;
  $('setmeta').textContent = n ? n + ' ausgeblendet' : 'alle sichtbar';
}
$('settabs').addEventListener('change', ev => {
  const cb = ev.target.closest('input[data-st]');
  if (!cb) return;
  const t = cb.dataset.st;
  SET.hidden = SET.hidden.filter(x => x !== t);
  if (!cb.checked) SET.hidden.push(t);
  setSave(); setApply(); setRender();
});
$('setall').addEventListener('click', () => { SET.hidden = []; setSave(); setApply(); setRender(); });
$('setlang').value = window.EDCJ_LANG;
$('setlang').addEventListener('change', () => window.setLang($('setlang').value));
$('settheme').addEventListener('change', () => { SET.theme = $('settheme').value; setSave(); setApply(); setRender(); });
setApply(); setRender();
fetch('/api/settings', {cache:'no-store'}).then(r => r.json()).then(d => {
  if (d && Array.isArray(d.hidden) && JSON.stringify(d) !== JSON.stringify(SET)){
    SET = {hidden: d.hidden, theme: THEMES[d.theme] ? d.theme : 'startrek'};
    try { localStorage.setItem('edl_set', JSON.stringify(SET)); } catch(e) {}
    setApply(); setRender();
  }
}).catch(() => {});

/* ---------- Journal-Ordner ---------- */
async function jdLoad(post){
  try {
    const r = await fetch('/api/journaldir', post ? {method:'POST', headers:{'X-EDCJ':'1'}, body: JSON.stringify(post)} : {cache:'no-store'});
    if (!r.ok) { $('jdpanel').hidden = true; return; }
    const d = await r.json();
    const src = {param: 'Startparameter -d', setting: 'Einstellung', env: 'Umgebungsvariable', auto: 'automatisch gefunden', file: 'Journal-Datei vom Start'}[d.source] || '';
    $('jdmeta').textContent = d.dir ? (d.files + ' Journal-Dateien') : 'nicht gefunden';
    $('jdcur').innerHTML = d.dir ? 'Aktuell: <b>' + esc(d.dir) + '</b> (' + src + ')' : 'Kein Journal-Ordner gefunden.';
    if (document.activeElement !== $('jdin')) $('jdin').value = d.saved || '';
    $('jdmsg').textContent = d.error ? d.error : (post ? 'Gespeichert.' : '');
    if (post && d.ok) { $('jdwarn').hidden = true; if (typeof poll === 'function') try { poll(); } catch(e) {} }
  } catch(e) {}
}
$('jdsave').addEventListener('click', () => jdLoad({dir: $('jdin').value}));
$('jdauto').addEventListener('click', () => { $('jdin').value = ''; jdLoad({dir: ''}); });
$('jdwgo').addEventListener('click', () => showTab('settings'));
jdLoad();

/* ---------- Tablet & Heimnetz ---------- */
async function lanLoad(post){
  try {
    const r = await fetch('/api/lan', post ? {method:'POST', headers:{'X-EDCJ':'1'}, body: JSON.stringify(post)} : {cache:'no-store'});
    if (!r.ok) { $('lanpanel').hidden = true; return; }
    const d = await r.json();
    $('lanon').checked = d.setting;
    if (document.activeElement !== $('lancode')) $('lancode').value = d.code;
    $('lanmeta').textContent = d.on_now ? 'freigegeben' : (d.setting ? 'nach Neustart' : 'aus');
    $('lanurls').innerHTML = d.on_now ? 'Adressen: ' + (d.urls.length ? d.urls.map(u => '<b>' + esc(u) + '</b>').join(' &nbsp; ') : 'keine gefunden') : 'Zurzeit nur auf diesem Rechner erreichbar.';
  } catch(e) {}
}
$('lanon').addEventListener('change', () => lanLoad({on: $('lanon').checked}));
$('lansave').addEventListener('click', () => lanLoad({code: $('lancode').value}));
$('lannew').addEventListener('click', () => lanLoad({code: ''}));
lanLoad();

/* ---------- Vollbild (pro Geraet) ---------- */
(function(){
  const de = document.documentElement;
  const can = !!(de.requestFullscreen || de.webkitRequestFullscreen);
  const isFs = () => !!(document.fullscreenElement || document.webkitFullscreenElement);
  const enter = () => { try { const r = (de.requestFullscreen || de.webkitRequestFullscreen).call(de, {navigationUI: 'hide'}); if (r && r.catch) r.catch(() => {}); } catch(e) {} };
  const leave = () => { try { (document.exitFullscreen || document.webkitExitFullscreen).call(document); } catch(e) {} };
  const toggle = () => isFs() ? leave() : enter();
  if (!can){ $('fspanel').hidden = true; return; }
  $('fsbtn').hidden = false;
  $('fsbtn').addEventListener('click', toggle);
  $('fsnow').addEventListener('click', toggle);
  const upd = () => { $('fsmeta').textContent = isFs() ? 'Vollbild an' : 'aus'; };
  document.addEventListener('fullscreenchange', upd); document.addEventListener('webkitfullscreenchange', upd); upd();
  let auto = false;
  try { auto = localStorage.getItem('edcj_fs') === '1'; } catch(e) {}
  $('fsauto').checked = auto;
  $('fsauto').addEventListener('change', () => { try { localStorage.setItem('edcj_fs', $('fsauto').checked ? '1' : '0'); } catch(e) {} });
  if (auto){
    const once = ev => {
      document.removeEventListener('pointerup', once, true);
      if (!isFs() && !(ev.target.closest && ev.target.closest('#fsbtn,#fsnow'))) enter();
    };
    document.addEventListener('pointerup', once, true);
  }
})();

/* ---------- Stationen & Siedlungen im aktuellen System (eigener Bestand aus den Journalen) ---------- */
let stnLast = '', stnTick = 0;
const stnOpen = new Set();
function stnRender(d){
  const el = $('sysstn'), st = d.stations || [];
  $('stnmeta').textContent = d.system ? st.length + ' besucht' : '-';
  if (!st.length){
    el.innerHTML = '<div class="empty">Noch keine Station oder Siedlung in diesem System besucht. Sie werden beim Andocken bzw. Anflug gespeichert.</div>';
    return;
  }
  let h = '<table class="mt"><thead><tr><th>Station</th><th>Führende Fraktion</th></tr></thead><tbody>';
  st.forEach((x, i) => {
    const open = stnOpen.has(x.name);
    const others = (d.factions || []).filter(f => f !== x.faction);
    h += '<tr class="stn" data-sn="' + esc(x.name) + '" tabindex="0"><td class="bn">' + (open ? '▾ ' : '▸ ') + esc(x.name) + '</td><td>' +
         (x.faction ? esc(x.faction) + (x.ctrl ? '<small class="good">Kontrolliert das System</small>' : '') : '<span class="mut">unbekannt</span>') + '</td></tr>';
    if (open) h += '<tr class="stnd"><td colspan="2"><small class="mut">Weitere Fraktionen im System</small>' +
         (others.length ? others.map(esc).join(', ') : '<span class="mut">keine weiteren bekannt</span>') + '</td></tr>';
  });
  el.innerHTML = h + '</tbody></table>';
}
async function loadSysStn(){
  const sys = window.__sys;
  if (!sys) return;
  try{
    const txt = await (await fetch('/api/market?' + new URLSearchParams({op:'sysstations', system:sys}), {cache:'no-store'})).text();
    const key = sys + txt + Array.from(stnOpen).join('|');
    if (key === stnLast) return;
    stnLast = key;
    stnRender(JSON.parse(txt));
  }catch(e){}
}
$('sysstn').addEventListener('click', ev => {
  const tr = ev.target.closest('tr[data-sn]');
  if (!tr) return;
  const n = tr.dataset.sn;
  if (stnOpen.has(n)) stnOpen.delete(n); else stnOpen.add(n);
  stnLast = ''; loadSysStn();
});

/* ---------- Cockpit ---------- */
let ckLast = '';
function ckBar(pct, warn){
  const p = Math.max(0, Math.min(100, pct || 0));
  return '<div class="bar"><i style="width:' + p + '%;' + (warn ? 'background:var(--red)' : '') + '"></i></div>';
}
function ckPips(v){
  const n = Math.max(0, Math.min(8, v || 0));  // Journal liefert Halb-Pips (0-8); angezeigt werden 4 Kästchen
  let h = '';
  for (let i = 0; i < 4; i++) h += '<b class="' + (n >= 2 * i + 2 ? 'on' : n === 2 * i + 1 ? 'half' : '') + '"></b>';
  return '<span class="pips">' + h + '</span>';
}
function ckAge(a){
  if (a == null) return 'Keine Status.json';
  if (a < 5) return 'live';
  if (a < 120) return 'vor ' + Math.round(a) + ' s';
  return 'Spiel inaktiv? Stand vor ' + Math.round(a / 60) + ' min';
}
function lageRender(L){
  const kv = (rows) => '<table class="mt"><tbody>' + rows.filter(r => r).map(r => '<tr><td class="mut">' + r[0] + '</td><td>' + r[1] + '</td></tr>').join('') + '</tbody></table>';
  const g2 = v => (v == null ? '-' : String(Math.round(v * 100) / 100).replace('.', ',') + ' g');
  const T = $('ck-lagetitle'), M = $('ck-lagemeta'), B = $('ck-lage');
  if (!L){ B.innerHTML = '<div class="empty">Keine Lage erkannt</div>'; return; }
  const dt = ts => ts ? new Date(ts).toLocaleString('de-DE', {day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit'}) : '-';
  if (L.kind === 'ring'){
    T.textContent = 'Lage: Im Ring'; M.textContent = L.title;
    const h = (L.hot || []).map(x => esc(x.mineral) + ' ×' + x.count).join(', ') || 'keine gespeichert';
    const mi = L.mining;
    B.innerHTML = '<div class="twocol">' + kv([
      ['Ring', esc(L.title) + (L.ring ? ' · ' + esc(L.ring.cls || '') + (L.ring.res ? ' · ' + esc(L.ring.res) : '') : '')],
      ['Hotspots', esc(h) + (L.hot_ts ? ' <span class="mut">(' + esc(L.hot_src || '') + '-Scan ' + dt(L.hot_ts) + ')</span>' : '')],
      ['Frachtraum', L.cargo && L.cargo.count != null ? L.cargo.count + (L.cargo.cap ? ' / ' + L.cargo.cap : '') + ' t' : '-']
    ]) + kv(mi ? [
      ['Abgebaut (Sitzung)', mi.tons + ' t in ' + mi.min + ' min'], ['Tempo', mi.tph + ' t/h'],
      ['Drohnen / Prospektoren', mi.drones + ' / ' + mi.prosp], ['Erz', esc(mi.ore.map(o => o[0] + ' ' + o[1]).join(', ') || '-')]
    ] : [['Mining', 'In diesem Ring noch nichts abgebaut']]) + '</div>';
  } else if (L.kind === 'station'){
    T.textContent = 'Lage: An der Station'; M.textContent = L.title + ' · ' + L.sys;
    const p = L.pads, i = L.info || {};
    const mh = L.market_h;
    const age = mh == null ? '<span class="mut">kein Markt aufgezeichnet</span>' : '<b class="' + (mh > 48 ? 'warn' : 'good') + '">' + (mh < 48 ? Math.round(mh) + ' Std.' : Math.round(mh / 24) + ' Tage') + '</b> alt';
    B.innerHTML = '<div class="twocol">' + kv([
      ['Typ / Fraktion', esc([i.type, i.faction].filter(Boolean).join(' · ') || '-')],
      ['Plattformen', p ? 'S ' + p.s + ' · M ' + p.m + ' · L ' + p.l : '<span class="mut">unbekannt</span>'],
      ['Markt', age + (L.market_ts ? ' <span class="mut">(' + dt(L.market_ts) + ')</span>' : '')],
      ['Offene Missionen hierher', L.missions ? L.missions + ' (' + fmt(L.mission_cr) + ' Cr)' : 'keine']
    ]) + kv([['Notiz', L.note ? esc(L.note.txt) + ' <span class="mut">(' + dt(L.note.ts) + ')</span>' : '<span class="mut">keine – unter Logbuch › Notizen anlegen</span>']]) + '</div>';
  } else if (L.kind === 'planet'){
    T.textContent = 'Lage: Auf dem Planeten'; M.textContent = L.title;
    const sc = L.scan, sg = L.sig;
    B.innerHTML = '<div class="twocol">' + kv([
      ['Schwerkraft', sc && sc.g ? g2(sc.g) : '<span class="mut">nicht gescannt</span>'],
      ['Atmosphäre', sc ? esc(sc.atm || 'keine') : '-'], ['Temperatur', sc && sc.temp ? sc.temp + ' K' : '-'], ['Klasse', sc ? esc(sc.cls) : '-']
    ]) + kv([
      ['Bio-Signale', sg ? sg.bio : '<span class="mut">nicht bekannt (Detailscan fehlt)</span>'], ['Geo-Signale', sg ? sg.geo : '-'],
      ['Hier analysiert', esc((L.bio_done || []).join(', ') || 'noch nichts')]
    ]) + '</div>';
  } else {
    T.textContent = 'Lage'; M.textContent = L.title || '';
    B.innerHTML = kv([['System', esc(L.title || '-')], ['Körper', esc(L.body || '-')], ['Ziel', esc(L.dest || '-')]]);
  }
}
function ckRender(d){
  try { lageRender(d.lage); } catch(e) {}
  if (d.error){ $('ck-state').innerHTML = '<div class="empty">' + esc(d.error) + '</div>'; return; }
  const sh = d.ship || {};
  $('ckmeta').textContent = ckAge(d.age);
  const ok = d.age != null && d.age < 600;
  const rows = [
    ['Zustand', '<b class="' + (ok ? 'good' : 'mut') + '">' + esc(d.state) + '</b>'],
    ['Schiff', esc((sh.name || '-') + (sh.label ? ' „' + sh.label + '“' : '') + (sh.ident ? ' ' + sh.ident : ''))],
    ['System', (d.system ? SYS(d.system) : '-') + (d.body ? ' · ' + esc(d.body) : '')],
    ['Ziel', esc(d.dest || '-')],
    ['Kontostand', d.balance != null ? fmt(d.balance) + ' Cr' : '-'],
    ['Rechtsstatus', esc(d.legal || '-')]
  ];
  if (d.mode === 'foot' && d.health != null) rows.push(['Gesundheit', Math.round(d.health * 100) + ' %']);
  if (d.mode === 'foot' && d.oxygen != null) rows.push(['Sauerstoff', Math.round(d.oxygen * 100) + ' %']);
  let h = rows.map(r => '<div class="row"><span>' + r[0] + '</span><span>' + r[1] + '</span></div>').join('');
  h += '<div class="ftags">' + ((d.flags || []).map(f => '<span class="ftag' + (f[1] ? ' warn' : '') + '">' + esc(f[0]) + '</span>').join('') || '<span class="mut">keine Besonderheiten</span>') + '</div>';
  $('ck-state').innerHTML = h;

  const fu = d.fuel || {}, fc = d.fuelcalc || {};
  let f = '';
  if (fu.FuelMain != null){
    const low = fc.pct != null && fc.pct < 25;
    f += ckBar(fc.pct, low);
    f += '<div class="row"><span>Tank</span><span>' + fu.FuelMain.toFixed(1).replace('.', ',') + ' t' + (sh.fuel_cap ? ' / ' + sh.fuel_cap + ' t' : '') +
         (fc.pct != null ? ' (' + Math.round(fc.pct) + ' %)' : '') + '</span></div>';
    f += '<div class="row"><span>Reserve</span><span>' + (fu.FuelReservoir != null ? fu.FuelReservoir.toFixed(2).replace('.', ',') + ' t' : '-') + '</span></div>';
    f += '<div class="row"><span>Ø Verbrauch / Sprung</span><span>' + (fc.per_jump ? fc.per_jump.toFixed(2).replace('.', ',') + ' t' : '-') + '</span></div>';
    const ly1 = v => v.toFixed(1).replace('.', ',') + ' Ly';
    f += '<div class="row"><span>Sprungweite</span><span>' + (sh.range_now ? '<span title="Aus Loadout, Fracht und Tankstand berechnet' + (sh.range_est ? ' (Verbrauch pro Sprung noch unbekannt, daher ca.)' : '') + '">aktuell ' + (sh.range_est ? 'ca. ' : '') + ly1(sh.range_now) + '</span>' : '-') + '</span></div>';
    f += '<div class="row"><span>Sprungweite max.</span><span>' + (sh.range ? ly1(sh.range) : '-') + '</span></div>';
  } else f += '<div class="empty">Kein Treibstoff im Status (zu Fuß oder Spiel aus).</div>';
  if (d.pips){
    f += '<div class="row"><span>SYS</span>' + ckPips(d.pips[0]) + '</div><div class="row"><span>ANT</span>' + ckPips(d.pips[1]) +
         '</div><div class="row"><span>WAF</span>' + ckPips(d.pips[2]) + '</div>';
  }
  $('ck-fuel').innerHTML = f;
  try {
    const mt = d.maint || [], bad = mt.filter(x => x.state === 'bad').length, warn = mt.filter(x => x.state === 'warn').length;
    $('ck-maintmeta').textContent = !mt.length ? '-' : bad ? bad + ' dringend' : warn ? warn + ' beachten' : 'alles in Ordnung';
    $('ck-maint').innerHTML = mt.length ? mt.map(x => '<div class="row"><span>' + esc(x.label) + '</span><span class="' + (x.state === 'ok' ? 'good' : x.state === 'bad' ? 'mbad' : 'warn') + '" style="text-align:right;min-width:0;overflow-wrap:anywhere;font-size:.9em">' +
      (x.state === 'ok' ? '✔ ' : x.state === 'bad' ? '✖ ' : '▲ ') + esc(x.text) + (x.ts ? ' <span class="mut">(Stand ' + esc(dts(x.ts)) + ')</span>' : '') + '</span></div>').join('') +
      '<div class="mut" style="font-size:14px;margin-top:6px">Abgeleitet aus Status und Journal. Munition: Maß ist der höchste bisher gesehene Stand der Waffe. Rumpf und Module: Stand des letzten Loadout- oder Schadens-Ereignisses.</div>'
      : '<div class="empty">Nur im Schiff verfügbar.</div>';
  } catch(e) {}

  const cg = d.cargo || {};
  let c = '<div class="row"><span>Fracht</span><span>' + fmt(cg.count || 0) + ' t' + (sh.cargo_cap ? ' / ' + sh.cargo_cap + ' t' : '') +
          ' · Wert bei bestem bekannten Preis ' + fmt(cg.value || 0) + ' Cr</span></div>';
  if (cg.items && cg.items.length){
    c += '<table class="mt"><thead><tr><th>Ware</th><th class="num">Menge</th><th>Bester Verkauf</th><th class="num">Preis</th><th class="num">Wert</th></tr></thead><tbody>';
    cg.items.slice().sort((a, b) => b.count - a.count).forEach(i => {
      const b = i.best;
      c += '<tr><td>' + esc(i.name) + (i.stolen ? ' <small class="dn">gestohlen</small>' : '') + (i.mission ? ' <small>Mission</small>' : '') + '</td>' +
           '<td class="num">' + fmt(i.count) + '</td><td>' + (b ? esc(b.station) + '<small>' + SYS(b.system) + (b.dist != null ? ' · ' + b.dist.toFixed(1).replace('.', ',') + ' Ly' : ' · Entfernung unbekannt') + ' · Nachfrage ' + fmt(b.demand) + ' · Stand ' + dts(b.seen) + '</small>' : '<span class="mut">kein Preis bekannt</span>') +
           '</td><td class="num">' + (b ? fmt(b.price) + ' Cr' : '-') + '</td><td class="num">' + (b ? fmt(b.price * i.count) + ' Cr' : '-') + '</td></tr>';
    });
    c += '</tbody></table>';
  } else c += '<div class="empty">Frachtraum leer.</div>';
  $('ck-cargo').innerHTML = c;

  const r = d.route || {};
  let t = '';
  if (r.items && r.items.length > 1){
    const cur = r.cur || 0, nTot = r.items.length - 1;
    t += '<div class="row"><span>Route</span><span>' + r.jumps + ' Sprünge · ' + r.dist.toFixed(1).replace('.', ',') + ' Ly · ' + r.noscoop + ' ohne Scoop-Stern</span></div>';
    if (r.on_route){
      t += '<div class="row"><span class="good">Position</span><span class="good">Sprung ' + cur + ' von ' + nTot + ' · ' + esc(r.here) + (r.rem_jumps ? ' · noch ' + r.rem_jumps + ' Sprünge · ' + r.rem_dist.toFixed(1).replace('.', ',') + ' Ly · ' + r.rem_noscoop + ' ohne Scoop-Stern' : ' · Ziel erreicht') + '</span></div>';
    } else {
      t += '<div class="row"><span class="warn">Position</span><span class="warn">' + (r.here ? esc(r.here) + ' liegt nicht auf der Route' : 'aktuelles System unbekannt') + ' · Berechnung ab Routenstart</span></div>';
    }
    if (r.fuel_total != null){
      t += '<div class="row"><span>Treibstoff ' + (r.on_route && cur ? 'für den Rest der Route' : 'für die Route') + '</span><span>' + r.fuel_total.toFixed(1).replace('.', ',') + ' t' + (fu.FuelMain != null ? ' von ' + fu.FuelMain.toFixed(1).replace('.', ',') + ' t im Tank' : '') + (r.per_tank ? ' · voller Tank: ca. ' + r.per_tank + ' Sprünge à max. Weite' : '') + '</span></div>';
      if (r.short != null){
        const st = r.scoop_stop != null ? r.items[r.scoop_stop] : null;
        t += '<div class="row"><span class="dn">Tank reicht nicht</span><span class="dn">bis Sprung ' + r.short + ' (' + esc(r.items[r.short].name) + '), ' +
             (st ? 'tanken bei ' + (r.scoop_stop === 0 ? 'Start' : 'Sprung ' + r.scoop_stop) + ': ' + esc(st.name) + ' (Scoop-Stern ' + esc(st.cls) + ')' : 'kein Scoop-Stern davor, Tank vorher füllen') + '</span></div>';
      } else t += '<div class="row"><span>Tank</span><span>reicht für die ganze Route ohne Scoopen</span></div>';
    }
    t += '<div class="tscroll" id="ck-rtscroll"><table class="mt"><thead><tr><th>#</th><th>System</th><th>Stern</th><th class="num">Sprung</th><th class="num">Verbrauch</th><th class="num">Rest</th><th>Scoop</th></tr></thead><tbody>';
    r.items.forEach((s, n) => {
      const far = sh.range && s.leg > sh.range + 0.05;
      t += '<tr class="' + (s.here ? 'rthere' : s.done ? 'rtdone' : '') + '"><td>' + n + '</td><td>' + SYS(s.name) + (s.here ? ' <b class="rtmark">◄ DU BIST HIER</b>' : '') + '</td><td>' + esc(s.cls) + '</td><td class="num ' + (far ? 'dn' : '') + '">' + (n ? s.leg.toFixed(1).replace('.', ',') + ' Ly' : '-') +
           '</td><td class="num">' + (s.fuel != null && n ? s.fuel.toFixed(2).replace('.', ',') + ' t' : '-') + '</td><td class="num ' + (s.left != null && s.left < 0 ? 'dn' : '') + '">' + (s.left != null ? (s.left < 0 ? 'leer' : s.left.toFixed(1).replace('.', ',') + ' t') : '-') +
           '</td><td>' + (s.scoop ? 'ja' : '<span class="dn">nein</span>') + '</td></tr>';
    });
    t += '</tbody></table></div>';
  } else t = '<div class="empty">Keine Route geplant.</div>';
  const old = $('ck-rtscroll'), oldTop = old ? old.scrollTop : 0, oldCur = $('ck-route').dataset.cur;
  $('ck-route').innerHTML = t;
  const sc = $('ck-rtscroll'), hr = sc && sc.querySelector('tr.rthere');
  if (sc){
    const key = (r.here || '') + '|' + (r.on_route ? 1 : 0) + '|' + (r.items ? r.items.length : 0);
    $('ck-route').dataset.cur = key;
    // Bei neuer Position die aktuelle Zeile in den Blick holen, sonst Bildlauf des Nutzers beibehalten
    if (hr && oldCur !== key) sc.scrollTop = Math.max(0, hr.offsetTop - sc.clientHeight / 3); else sc.scrollTop = oldTop;
  }
}
async function loadCockpit(){
  try{
    const txt = await (await fetch('/api/cockpit?range=' + RANGE, {cache:'no-store'})).text();
    if (txt === ckLast) return;
    ckLast = txt;
    ckRender(JSON.parse(txt));
  }catch(e){ $('ckmeta').textContent = 'Keine Verbindung'; }
}
if (!(location.hash || '').slice(1) || (location.hash || '').slice(1) === 'cockpit') loadCockpit();
function crVisible(){ return Object.keys(CR).find(t => !$('tab-' + t).hidden); }
poll(); setInterval(poll, 2000);

/* ---- Systemnamen kopieren ---- */
let cpTimer = 0;
const ME = {local: true};  // false auf Geraeten im Heimnetz (Tablet)
fetch('/api/me', {cache: 'no-store'}).then(r => r.json()).then(d => { ME.local = !!d.local; }).catch(() => {});
function cpToast(msg){
  let t = document.getElementById('cptoast');
  if (!t){ t = document.createElement('div'); t.id = 'cptoast'; document.body.appendChild(t); }
  t.textContent = msg; t.className = 'show'; clearTimeout(cpTimer); cpTimer = setTimeout(() => { t.className = ''; }, 2200);
}
async function cpCopy(txt){
  try{ await navigator.clipboard.writeText(txt); return true; }catch(e){}
  try{
    const ta = document.createElement('textarea'); ta.value = txt; ta.style.cssText = 'position:fixed;left:-999px;top:0';
    document.body.appendChild(ta); ta.select(); const ok = document.execCommand('copy'); ta.remove(); return ok;
  }catch(e){ return false; }
}
document.addEventListener('click', async e => {
  const el = e.target.closest('.cp'); if (!el) return;
  e.stopPropagation(); e.preventDefault();
  const n = el.dataset.cp;
  if (!ME.local){  // Tablet: Kurs am Rechner setzen (Zwischenablage des PCs)
    try {
      const r = await (await fetch('/api/clip', {method: 'POST', headers: {'X-EDCJ': '1', 'Content-Type': 'application/json'}, body: JSON.stringify({text: n})})).json();
      cpToast(r.ok ? 'Kurs gesetzt: ' + n : (r.error || 'Senden fehlgeschlagen'));
    } catch(err) { cpToast('Senden an den Rechner fehlgeschlagen'); }
    return;
  }
  cpToast((await cpCopy(n)) ? 'Kopiert: ' + n : 'Kopieren nicht möglich: ' + n);
}, true);

/* ---- Galerie ---- */
const shPost = o => fetch('/api/gallery', {method: 'POST', headers: {'X-EDCJ': '1', 'Content-Type': 'application/json'}, body: JSON.stringify(o)}).then(r => r.json());
const shBytes = n => n >= 1073741824 ? (n / 1073741824).toFixed(1).replace('.', ',') + ' GB' : n >= 1048576 ? (n / 1048576).toFixed(0) + ' MB' : Math.round(n / 1024) + ' KB';
async function loadShots(keepFocus){
  try{
    const d = await (await fetch('/api/gallery?' + new URLSearchParams({op: 'list', q: $('shq').value, fav: SH.fav ? '1' : '0'}), {cache: 'no-store'})).json();
    if (d.error) return;
    SH.rows = d.rows || [];
    $('shmeta').textContent = d.total + ' Bilder' + (d.favs ? ' · ' + d.favs + ' Favoriten' : '');
    $('shfav').classList.toggle('on', SH.fav);
    $('shtags').innerHTML = (d.tags || []).map(t => '<button data-tg="' + esc(t[0]) + '">' + esc(t[0]) + ' (' + t[1] + ')</button>').join('');
    $('shgrid').innerHTML = SH.rows.length ? SH.rows.map((r, i) =>
      '<div class="shc" data-i="' + i + '" tabindex="0">' + (r.has_file ? '<img loading="lazy" alt="" src="' + esc(r.tsrc || r.src) + '">' : '<div class="shno">Datei nicht gefunden</div>') +
      (r.fav ? '<span class="shstar">&#9733;</span>' : '') +
      '<div class="shi"><b>' + esc(r.sys || 'System unbekannt') + '</b><small>' + esc(r.body && r.body !== r.sys ? r.body + ' · ' : '') + esc(dts(r.ts)) + '</small></div></div>').join('')
      : '<div class="empty">' + (d.total ? 'Keine Treffer für diese Auswahl.' : 'Noch keine Screenshots. Drücke im Spiel die Screenshot-Taste (Standard F10): EDCJ übernimmt das Bild samt Ort automatisch.') + '</div>';
    $('shinfo').textContent = d.found + ' von ' + d.total + ' Bildern gefunden · Kopien in ' + d.dir + ' (' + shBytes(d.bytes) + ')' +
      (d.total - d.found > 0 ? ' · ' + (d.total - d.found) + ' Bild(er) nicht im Spielordner gefunden' : '') +
      (d.sources.length ? ' · Suche in: ' + d.sources.join(' ; ') : ' · Kein Bilderordner des Spiels gefunden: unten eintragen');
    if (!keepFocus && document.activeElement !== $('shdir')) $('shdir').value = d.custom || $('shdir').value;
  }catch(e){}
}
function shOpen(i){
  if (i < 0 || i >= SH.rows.length) return;
  SH.i = i; const r = SH.rows[i];
  $('shlb').hidden = false;
  $('shimgw').innerHTML = r.has_file ? '<img alt="" src="' + esc(r.src) + '">' : '<div class="shno" style="height:300px">Datei nicht gefunden</div>';
  const kv = [['System', SYS(r.sys) + (r.visits ? ' <small class="mut">' + r.visits + ' Besuch(e)</small>' : '')], ['Körper', esc(r.body || '-')], ['Zeit', esc(dts(r.ts))]];
  if (r.lat != null && r.lon != null) kv.push(['Position', (r.lat.toFixed(4) + ' / ' + r.lon.toFixed(4)).replace(/\./g, ',')]);
  if (r.alt != null) kv.push(['Höhe', r.alt >= 10000 ? (r.alt / 1000).toFixed(1).replace('.', ',') + ' km' : Math.round(r.alt) + ' m']);
  if (r.hdg != null) kv.push(['Blickrichtung', Math.round(r.hdg) + '°']);
  if (r.w) kv.push(['Größe', r.w + ' × ' + r.h]);
  $('shside').innerHTML = '<div class="shkv">' + kv.map(x => '<div><span class="mut">' + x[0] + '</span><span>' + x[1] + '</span></div>').join('') + '</div>' +
    '<label class="mut">Schlagworte (mit Komma)</label><input id="shtag" class="sq" style="margin:2px 0 8px" value="' + esc(r.tags) + '" placeholder="z. B. Ringe, Landschaft, Station">' +
    '<label class="mut">Notiz</label><textarea id="shnote" class="sq" rows="4" style="margin:2px 0 8px;width:100%;box-sizing:border-box;font:inherit">' + esc(r.note) + '</textarea>' +
    '<div class="row2" style="flex-wrap:wrap;gap:8px"><button class="xbtn" id="shsave">Speichern</button><button class="xbtn" id="shstar">' + (r.fav ? '&#9733; Favorit' : '&#9734; Als Favorit') + '</button>' +
    (r.has_file ? '<a class="xbtn" href="' + esc(r.src) + '" target="_blank" rel="noopener" style="text-decoration:none">Original öffnen</a>' : '') +
    '<button class="xbtn" id="shdel" style="background:var(--red)">Entfernen</button></div><div id="shmsg" class="mut" style="margin-top:8px;font-size:14px"></div>';
}
function shClose(){ $('shlb').hidden = true; SH.i = -1; }
$('shq').addEventListener('input', () => { clearTimeout(SH.tm); SH.tm = setTimeout(() => loadShots(true), 250); });
$('shfav').addEventListener('click', () => { SH.fav = !SH.fav; loadShots(true); });
$('shre').addEventListener('click', async () => { $('shre').textContent = 'Suche …'; await shPost({act: 'rescan'}); $('shre').textContent = 'Neu suchen'; loadShots(true); });
$('shdirsave').addEventListener('click', async () => { await shPost({act: 'dir', dir: $('shdir').value}); loadShots(true); });
$('shtags').addEventListener('click', e => { const b = e.target.closest('button[data-tg]'); if (!b) return; $('shq').value = b.dataset.tg; loadShots(true); });
$('shgrid').addEventListener('click', e => { const c = e.target.closest('.shc'); if (c) shOpen(+c.dataset.i); });
$('shgrid').addEventListener('keydown', e => { if (e.key === 'Enter'){ const c = e.target.closest('.shc'); if (c) shOpen(+c.dataset.i); } });
$('shclose').addEventListener('click', shClose);
$('shlb').addEventListener('click', e => { if (e.target === $('shlb')) shClose(); });
$('shprev').addEventListener('click', () => shOpen(SH.i - 1));
$('shnext').addEventListener('click', () => shOpen(SH.i + 1));
document.addEventListener('keydown', e => {
  if ($('shlb').hidden || /^(INPUT|TEXTAREA)$/.test((e.target.tagName || ''))) return;
  if (e.key === 'Escape') shClose(); else if (e.key === 'ArrowLeft') shOpen(SH.i - 1); else if (e.key === 'ArrowRight') shOpen(SH.i + 1);
});
$('shside').addEventListener('click', async e => {
  const r = SH.rows[SH.i]; if (!r) return;
  if (e.target.id === 'shsave'){
    const o = await shPost({act: 'meta', id: r.id, note: $('shnote').value, tags: $('shtag').value});
    $('shmsg').textContent = o.ok ? 'Gespeichert.' : 'Fehler beim Speichern.';
    if (o.ok){ const i = SH.i; await loadShots(true); SH.i = i; }
  } else if (e.target.id === 'shstar'){
    await shPost({act: 'fav', id: r.id, v: r.fav ? 0 : 1}); const i = SH.i; await loadShots(true); shOpen(i);
  } else if (e.target.id === 'shdel'){
    if (!confirm('Dieses Bild aus der Galerie entfernen? Die kopierte Datei wird gelöscht, das Original im Spielordner bleibt.')) return;
    await shPost({act: 'delete', id: r.id}); shClose(); loadShots(true);
  }
});

/* ---- Eigene Menge (Handel) ---- */
['trqty', 'mkqty'].forEach(id => { const el = $(id); el.value = QTY; el.addEventListener('change', () => setQty(el.value)); el.addEventListener('keydown', e => { if (e.key === 'Enter') setQty(el.value); }); });

/* ---- Spielstil ---- */
const PF_COL = {handel: '#ffcc66', erkundung: '#66ccff', kampf: '#ff6666', mining: '#66ff99', sonst: '#8a8a8a'};
const pfHours = m => m >= 60 ? Math.floor(m / 60) + ' Std. ' + String(Math.round(m % 60)).padStart(2, '0') + ' Min.' : Math.round(m) + ' Min.';
async function loadProfil(){
  try{
    PF.weeks = +$('pfweeks').value;
    const d = await (await fetch('/api/profile?weeks=' + PF.weeks, {cache: 'no-store'})).json();
    if (d.error){ $('pfmain').innerHTML = '<div class="empty">' + esc(d.error) + '</div>'; return; }
    PF.d = d;
    if (!d.weeks.some(w => w.start === PF.week)) PF.week = d.weeks.length ? d.weeks[d.weeks.length - 1].start : '';
    renderProfil();
  }catch(e){}
}
function pfDonut(parts, total){
  const R = 80, r = 48, cx = 100, cy = 100;
  if (!total) return '<svg viewBox="0 0 200 200" class="pfdonut"><circle cx="100" cy="100" r="64" fill="none" stroke="#333" stroke-width="32"/></svg>';
  const pol = (rad, a) => [cx + rad * Math.sin(a), cy - rad * Math.cos(a)];
  let a0 = 0, out = '';
  parts.filter(p => p.v > 0).forEach(p => {
    const frac = p.v / total;
    if (frac > 0.9999){ out += '<circle cx="100" cy="100" r="' + ((R + r) / 2) + '" fill="none" stroke="' + p.c + '" stroke-width="' + (R - r) + '"><title>' + esc(p.l) + ': ' + pfHours(p.v) + '</title></circle>'; return; }
    const a1 = a0 + frac * 2 * Math.PI, big = a1 - a0 > Math.PI ? 1 : 0;
    const [x0, y0] = pol(R, a0), [x1, y1] = pol(R, a1), [x2, y2] = pol(r, a1), [x3, y3] = pol(r, a0);
    out += '<path d="M' + x0 + ' ' + y0 + 'A' + R + ' ' + R + ' 0 ' + big + ' 1 ' + x1 + ' ' + y1 + 'L' + x2 + ' ' + y2 + 'A' + r + ' ' + r + ' 0 ' + big + ' 0 ' + x3 + ' ' + y3 + 'Z" fill="' + p.c + '" stroke="#000" stroke-width="1.5"><title>' + esc(p.l) + ': ' + pfHours(p.v) + ' (' + Math.round(frac * 100) + ' %)</title></path>';
    a0 = a1;
  });
  return '<svg viewBox="0 0 200 200" class="pfdonut" role="img" aria-label="Verteilung der Tätigkeiten">' + out + '<text x="100" y="97" text-anchor="middle" fill="#fff" font-size="22" font-weight="700">' + Math.round(total / 6) / 10 + ' h</text><text x="100" y="118" text-anchor="middle" fill="#aaa" font-size="12">gespielt</text></svg>';
}
function renderProfil(){
  const d = PF.d; if (!d) return;
  const W = d.weeks, cats = d.cats;
  $('pfmeta').textContent = d.total_min ? pfHours(d.total_min) + ' im Zeitraum · ' + W.length + ' Wochen' : '-';
  if (!W.length){ $('pfmain').innerHTML = '<div class="empty">Noch keine Spielzeit gefunden. Sobald das Journal eingelesen ist, erscheint hier dein Spielstil.</div>'; $('pfheat').innerHTML = ''; $('pfrec').innerHTML = ''; return; }
  const cur = W.find(w => w.start === PF.week) || W[W.length - 1];
  const parts = cats.map(c => ({id: c[0], l: c[1], c: PF_COL[c[0]], v: cur.min[c[0]]}));
  const legend = parts.map(p => '<div class="pfleg"><i style="background:' + p.c + '"></i><span>' + esc(p.l) + '</span><b>' + pfHours(p.v) + '</b><small class="mut">' + (cur.total ? Math.round(p.v / cur.total * 100) : 0) + ' %</small></div>').join('');
  const maxT = Math.max(...W.map(w => w.total), 1), bw = Math.max(8, Math.min(46, Math.floor(640 / W.length) - 4)), H = 150, gap = 4;
  let bars = '';
  W.forEach((w, i) => {
    let y = H, x = 6 + i * (bw + gap);
    cats.forEach(c => {
      const h = w.min[c[0]] / maxT * (H - 4);
      if (h > 0){ y -= h; bars += '<rect x="' + x + '" y="' + y.toFixed(1) + '" width="' + bw + '" height="' + h.toFixed(1) + '" fill="' + PF_COL[c[0]] + '"><title>' + esc(w.label) + ' · ' + esc(c[1]) + ': ' + pfHours(w.min[c[0]]) + '</title></rect>'; }
    });
    bars += '<rect class="pfwk" data-wk="' + w.start + '" x="' + (x - 2) + '" y="0" width="' + (bw + 4) + '" height="' + H + '" fill="' + (w.start === cur.start ? 'rgba(255,255,255,.14)' : 'transparent') + '" stroke="' + (w.start === cur.start ? '#fff' : 'none') + '" style="cursor:pointer"><title>KW ' + w.kw + ' · ' + esc(w.label) + ' · ' + pfHours(w.total) + '</title></rect>';
  });
  const svgW = 12 + W.length * (bw + gap);
  const tr = (d.trend || []).filter(t => t.id !== 'sonst').map(t => '<div class="pftr"><span>' + esc(t.label) + '</span><b class="' + (t.diff > 1 ? 'good' : t.diff < -1 ? 'dn' : 'mut') + '">' + (t.diff > 0 ? '▲ +' : t.diff < 0 ? '▼ ' : '≈ ') + t.diff.toFixed(1).replace('.', ',') + ' Pp</b><small class="mut">jetzt ' + t.now.toFixed(0) + ' % · davor ' + t.before.toFixed(0) + ' %</small></div>').join('');
  $('pfmain').innerHTML = '<div class="pfrow"><div class="pfcol"><div class="mut" style="margin-bottom:4px">KW ' + cur.kw + ' · ' + esc(cur.label) + '</div>' + pfDonut(parts, cur.total) + '</div>' +
    '<div class="pfcol pfl">' + legend + '</div>' +
    '<div class="pfcol pfw"><div class="mut" style="margin-bottom:4px">Spielzeit pro Woche (Wochenbalken anklicken)</div><svg viewBox="0 0 ' + svgW + ' ' + (H + 2) + '" width="' + svgW + '" height="' + (H + 2) + '" role="img" aria-label="Wochenverlauf">' + bars + '</svg>' +
    '<div class="pfkey">' + cats.map(c => '<span><i style="background:' + PF_COL[c[0]] + '"></i>' + esc(c[1]) + '</span>').join('') + '</div></div></div>' +
    (tr ? '<div class="mut" style="margin:10px 0 4px">Trend: letzte Woche (die laufende zählt mit) gegen den Schnitt der vier Wochen davor, Anteil an der Spielzeit, Pp = Prozentpunkte</div><div class="pftrs">' + tr + '</div>' : '<div class="mut" style="margin-top:10px">Für einen Trend braucht es mindestens zwei Wochen.</div>');
  // Heatmap
  const h = d.heat;
  if (h){
    const mx = Math.max(...h.avg.map(r => Math.max(...r)), 1);
    const pk = h.peak ? h.days[h.peak.wd] + ' ' + h.peak.h + '–' + (h.peak.h + 1) + ' Uhr (Ø ' + Math.round(h.peak.min) + ' Min. pro Stunde)' : '-';
    const bestDay = h.day_avg.indexOf(Math.max(...h.day_avg)), bestHour = h.hour_avg.indexOf(Math.max(...h.hour_avg));
    $('pfhmeta').textContent = 'Stärkste Stunde: ' + pk;
    let t = '<div class="tscroll" style="max-height:none"><table class="pfheat"><thead><tr><th></th>' + [...Array(24).keys()].map(i => '<th>' + i + '</th>').join('') + '<th>Ø Std.</th></tr></thead><tbody>';
    h.days.forEach((dn, wd) => {
      t += '<tr><th>' + dn + '</th>';
      for (let hr = 0; hr < 24; hr++){
        const v = h.avg[wd][hr], tc = h.top[wd][hr], sh = h.share[wd][hr];
        let st = '';
        if (v > 0){
          const a = Math.max(0.12, v / mx);
          st = PF.mode === 'act' && tc ? 'background:' + PF_COL[tc] + ';opacity:' + (0.25 + 0.75 * a).toFixed(2) : 'background:#ff9c00;opacity:' + (0.15 + 0.85 * a).toFixed(2);
        }
        const catName = tc ? (cats.find(c => c[0] === tc) || [0, tc])[1] : '';
        t += '<td title="' + dn + ' ' + hr + '–' + (hr + 1) + ' Uhr: ' + (v ? 'Ø ' + Math.round(v) + ' Min. pro Stunde · häufigste Tätigkeit: ' + esc(catName) + ' (' + sh + ' %)' : 'keine Spielzeit') + '"><i style="' + st + '"></i></td>';
      }
      t += '<td class="num mut">' + h.day_avg[wd].toFixed(1).replace('.', ',') + '</td></tr>';
    });
    t += '</tbody></table></div>';
    const leg = PF.mode === 'act' ? '<div class="pfkey">' + cats.map(c => '<span><i style="background:' + PF_COL[c[0]] + '"></i>' + esc(c[1]) + '</span>').join('') + '</div>' : '<div class="mut" style="font-size:14px;margin-top:4px">Je heller der Block, desto mehr Spielzeit in dieser Stunde (Durchschnitt über alle Tage im Zeitraum).</div>';
    $('pfheat').innerHTML = t + leg + '<div style="margin-top:8px">Aktivster Wochentag: <b>' + h.days[bestDay] + '</b> (Ø ' + h.day_avg[bestDay].toFixed(1).replace('.', ',') + ' Std.) · Aktivste Tageszeit: <b>' + bestHour + '–' + (bestHour + 1) + ' Uhr</b></div>';
  } else $('pfheat').innerHTML = '';
  // Rekorde
  const groups = {};
  (d.records || []).forEach(r => (groups[r.group] = groups[r.group] || []).push(r));
  $('pfrmeta').textContent = (d.records || []).length + ' Werte';
  $('pfrec').innerHTML = (d.records || []).length ? '<table class="mt"><thead><tr><th>Rekord</th><th class="num">Wert</th><th>Details</th><th>Datum</th></tr></thead><tbody>' +
    Object.keys(groups).map(g => '<tr><td colspan="4" class="pfgrp">' + esc(g) + '</td></tr>' + groups[g].map(r => '<tr><td class="bn">' + esc(r.label) + (r.recent ? ' <small class="iu">neu in den letzten 7 Tagen</small>' : '') + '</td><td class="num best">' + esc(r.value) + '</td><td class="mut">' + esc(r.detail) + '</td><td class="mut">' + (r.date ? new Date(r.date + 'T12:00:00').toLocaleDateString('de-DE') : '-') + '</td></tr>').join('')).join('') + '</tbody></table>'
    : '<div class="empty">Noch keine Rekorde.</div>';
}
$('pfweeks').addEventListener('change', loadProfil);
$('pfmode').addEventListener('change', () => { PF.mode = $('pfmode').value; renderProfil(); });
$('pfmain').addEventListener('click', e => { const r = e.target.closest('.pfwk'); if (!r) return; PF.week = r.dataset.wk; renderProfil(); });
