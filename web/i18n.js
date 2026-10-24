/* EDCJ Sprachumschaltung: Deutsch (Original) / English. Nur EDCJ-Oberflaeche, Spieldaten bleiben unberuehrt. */
(function(){
  var L = 'de';
  try { var m = /[?&]lang=(en|de)\b/.exec(location.search); if (m) localStorage.setItem('edcj_lang', m[1]); L = localStorage.getItem('edcj_lang') || 'de'; } catch(e) {}
  if (L !== 'en') L = 'de';
  window.EDCJ_LANG = L;
  try { document.cookie = 'edcj_lang=' + L + '; Path=/; Max-Age=31536000; SameSite=Lax'; } catch(e) {}
  document.documentElement.lang = L;
  window.setLang = function(l){ try { localStorage.setItem('edcj_lang', l); } catch(e) {} try { document.cookie = 'edcj_lang=' + l + '; Path=/; Max-Age=31536000; SameSite=Lax'; } catch(e) {} location.reload(); };
  window.tr = function(s){ return s; };
  if (L !== 'en' || !window.EDCJ_EN) return;

  var P = window.EDCJ_EN.p, X = window.EDCJ_EN.x, RXS = (window.EDCJ_EN.r || []).map(function(r){ return [new RegExp(r[0], 'g'), r[1]]; }), memo = new Map();
  var keys = Object.keys(P).sort(function(a, b){ return b.length - a.length; });
  var WC = /[\p{L}\p{N}_]/u, byFirst = Object.create(null), special = [];
  keys.forEach(function(k){
    var m = /^[\p{L}\p{N}_]+/u.exec(k);
    if (m) (byFirst[m[0]] = byFirst[m[0]] || []).push(k); else special.push(k);
  });
  var WORD = /[\p{L}\p{N}_]+/gu;
  var HAS_DE = /[A-Za-zÄÖÜäöüß]/;
  function tokpass(s){
    var out = '', last = 0, m, re = new RegExp(WORD.source, 'gu');
    while ((m = re.exec(s))) {
      var c = byFirst[m[0]]; if (!c) continue;
      var i = m.index, hit = null;
      for (var j = 0; j < c.length; j++) {
        var k = c[j];
        if (s.startsWith(k, i)) {
          var e = i + k.length;
          if (WC.test(k.charAt(k.length - 1)) && e < s.length && WC.test(s.charAt(e))) continue;
          hit = k; break;
        }
      }
      if (hit) { var rep = P[hit]; if (hit.indexOf(' ') < 0 && /^[A-ZÄÖÜ]/.test(rep) && /[a-zäöüß0-9] ?$/.test(s.slice(Math.max(0, i - 2), i)) && !/^[A-Z]{2}/.test(rep)) rep = rep.charAt(0).toLowerCase() + rep.slice(1); out += s.slice(last, i) + rep; last = i + hit.length; re.lastIndex = last; }
    }
    return out + s.slice(last);
  }
  function tr(s){
    if (!s || typeof s !== 'string' || !HAS_DE.test(s)) return s;
    var h = memo.get(s); if (h !== undefined) return h;
    var t = s.trim(), r;
    if (X[t] !== undefined) r = s.replace(t, X[t]);
    else {
      r = s.replace(/\s+/g, ' ');
      for (var i = 0; i < special.length; i++) { var k = special[i]; if (r.indexOf(k) >= 0) r = r.split(k).join(P[k]); }
      r = tokpass(r);
      for (var q = 0; q < RXS.length; q++) r = RXS[q][1] === '@th' ? r.replace(RXS[q][0], function(m){ return m.replace(/\./g, ','); }) : r.replace(RXS[q][0], RXS[q][1]);
    }
    if (memo.size > 20000) memo.clear();
    memo.set(s, r); return r;
  }
  window.tr = tr;

  /* Zahlen- und Datumsformat */
  var nl = Number.prototype.toLocaleString, dl = Date.prototype.toLocaleString, dd = Date.prototype.toLocaleDateString, dt = Date.prototype.toLocaleTimeString;
  Number.prototype.toLocaleString = function(l, o){ return nl.call(this, l === 'de-DE' ? 'en-US' : l, o); };
  Date.prototype.toLocaleString = function(l, o){ return dl.call(this, l === 'de-DE' ? 'en-GB' : l, o); };
  Date.prototype.toLocaleDateString = function(l, o){ return dd.call(this, l === 'de-DE' ? 'en-GB' : l, o); };
  Date.prototype.toLocaleTimeString = function(l, o){ return dt.call(this, l === 'de-DE' ? 'en-GB' : l, o); };

  /* Dialoge */
  var oc = window.confirm, oa = window.alert, op = window.prompt;
  window.confirm = function(m){ return oc.call(window, tr(m)); };
  window.alert = function(m){ return oa.call(window, tr(m)); };
  window.prompt = function(m, d){ return op.call(window, tr(m), d); };

  var ATTR = ['title', 'placeholder', 'alt', 'aria-label', 'label'];
  function node(n){
    if (n.nodeType === 3) {
      if (n.__o === n.data) return;
      var p = n.parentNode && n.parentNode.nodeName;
      if (p === 'SCRIPT' || p === 'STYLE' || p === 'TEXTAREA') return;
      var r = tr(n.data); n.__o = r; if (r !== n.data) n.data = r;
    } else if (n.nodeType === 1) {
      if (n.nodeName === 'SCRIPT' || n.nodeName === 'STYLE') return;
      for (var i = 0; i < ATTR.length; i++) { var v = n.getAttribute(ATTR[i]); if (v) { var r2 = tr(v); if (r2 !== v) n.setAttribute(ATTR[i], r2); } }
      if (n.nodeName === 'INPUT' && (n.type === 'button' || n.type === 'submit') && n.value) n.value = tr(n.value);
      for (var c = n.firstChild; c; c = c.nextSibling) node(c);
    }
  }
  function run(){
    document.title = tr(document.title);
    node(document.body);
    new MutationObserver(function(ms){
      for (var i = 0; i < ms.length; i++) {
        var m = ms[i];
        if (m.type === 'characterData') node(m.target);
        else if (m.type === 'attributes') { var v = m.target.getAttribute(m.attributeName); if (v) { var r = tr(v); if (r !== v) m.target.setAttribute(m.attributeName, r); } }
        else for (var j = 0; j < m.addedNodes.length; j++) node(m.addedNodes[j]);
      }
    }).observe(document.body, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTR});
  }
  if (document.body) run(); else document.addEventListener('DOMContentLoaded', run);
})();
