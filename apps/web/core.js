/* ============================================================
   RBA Policy Sentiment — shared core (window.RBACore)
   Pure logic + reusable DOM wiring, mirroring the RBA-Tracker's
   core.js. Dual-exported (browser global + CommonJS) so the pure
   helpers are unit-testable under `node --test`. The render
   functions (stance chart, table, detail panel) are added in
   later build phases.
   ============================================================ */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.RBACore = api;
})(typeof window !== "undefined" ? window : null, function () {
  "use strict";

  // ---------- date / number helpers (pure) ----------
  var MONTHS = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

  function parseDate(s) { var p = String(s).split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function ts(s) { return parseDate(s).getTime(); }
  function yearOf(s) { return String(s).slice(0, 4); }
  function formatDate(s) { var d = parseDate(s); return d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear(); }
  function formatDateShort(s) { var d = parseDate(s); return d.getDate() + " " + MONTHS[d.getMonth()].slice(0, 3) + " " + d.getFullYear(); }
  function fmtRate(p) { return Number(p).toFixed(2) + "%"; }
  function fmtPP(bps) { var v = (Math.abs(bps) / 100).toFixed(2).replace(/0+$/, "").replace(/\.$/, ""); return v + "%"; }
  function fmtChange(bps) { if (!bps) return "—"; return (bps > 0 ? "+" : "−") + fmtPP(bps); }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // ---------- stance helpers (pure) ----------
  // Signed value with a true minus glyph (U+2212): 0.309 -> "+0.31", -0.312 -> "−0.31", 0 -> "0.00".
  function signed(x, dp) {
    dp = dp == null ? 2 : dp;
    var n = Number(x);
    var sign = n > 0 ? "+" : (n < 0 ? "−" : "");
    return sign + Math.abs(n).toFixed(dp);
  }

  // Net dovish(−)↔hawkish(+) bucket. Half-open boundaries per design §6.
  function stanceBucket(net) {
    var n = Number(net);
    if (n <= -0.60) return { key: "strong-dovish", label: "Strongly dovish" };
    if (n <= -0.15) return { key: "dovish", label: "Dovish" };
    if (n < 0.15) return { key: "neutral", label: "Broadly neutral" };
    if (n < 0.60) return { key: "hawkish", label: "Hawkish" };
    return { key: "strong-hawkish", label: "Strongly hawkish" };
  }

  function confidenceBucket(conf) {
    var c = Number(conf);
    var pct = Math.round(c * 100);
    if (c >= 0.80) return { key: "high", label: "High", pct: pct };
    if (c >= 0.50) return { key: "moderate", label: "Moderate", pct: pct };
    return { key: "low", label: "Low", pct: pct };
  }

  var DIM_LABELS = { inflation: "inflation", growth: "growth", employment: "employment" };

  // The single largest-magnitude sub-dimension, only if |value| >= threshold; else null.
  function dominantSubDimension(subScores, threshold) {
    threshold = threshold == null ? 0.15 : threshold;
    var best = null;
    Object.keys(subScores || {}).forEach(function (k) {
      var v = Number(subScores[k]);
      if (Math.abs(v) >= threshold && (best === null || Math.abs(v) > Math.abs(best.value))) {
        best = { key: k, label: DIM_LABELS[k] || k, value: v };
      }
    });
    return best;
  }

  // Decision outcome (our shape: decision.outcome.{action,change_bps}).
  function describeOutcome(decision) {
    var o = (decision && decision.outcome) || {};
    var bps = o.change_bps || 0;
    if (o.action === "hike") return { glyph: "▲", label: "Hike", dir: "up", verb: "raised the cash rate", change_bps: bps };
    if (o.action === "cut") return { glyph: "▼", label: "Cut", dir: "down", verb: "lowered the cash rate", change_bps: bps };
    return { glyph: "●", label: "Hold", dir: "flat", verb: "held the cash rate steady", change_bps: bps };
  }

  // ---------- join (pure) ----------
  // decisions[] (with .id, .date) ⨯ scores{by id} -> sorted-ascending [{decision, score}].
  // Decisions without a score are skipped (warned).
  function joinDecisions(decisions, scores) {
    var out = [];
    (decisions || []).forEach(function (d) {
      var s = (scores || {})[d.id];
      if (!s) { if (typeof console !== "undefined") console.warn("No score for decision " + d.id); return; }
      out.push({ decision: d, score: s });
    });
    out.sort(function (a, b) { return ts(a.decision.date) - ts(b.decision.date); });
    return out;
  }

  // ---------- hero headline (pure) ----------
  // Deterministic, hedged plain-language sentence (FR-012's LLM summary stays M3).
  function buildHeadline(decision, score) {
    var d = describeOutcome(decision);
    var bucket = stanceBucket(score.net);
    var dom = dominantSubDimension(score.sub_scores);
    var lean = dom ? (", leaning " + dom.label) : "";
    var rate = fmtRate(decision.cash_rate_target);
    var did = d.dir === "flat" ? "held the cash rate steady"
      : (d.dir === "up" ? "raised the cash rate by " + fmtPP(d.change_bps)
        : "lowered the cash rate by " + fmtPP(d.change_bps));
    return "On " + formatDate(decision.date) + ", the RBA's tone read as "
      + bucket.label.toLowerCase() + lean + " while it " + did + " to " + rate + ".";
  }

  // ---------- browser-only wiring (reused from the tracker) ----------
  function prefersReducedMotion() {
    return typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }
  function countUp(el, target, opts) {
    opts = opts || {};
    var decimals = opts.decimals != null ? opts.decimals : 0;
    var dur = opts.duration != null ? opts.duration : 1100;
    var prefix = opts.prefix || "", suffix = opts.suffix || "", delay = opts.delay || 0;
    var ease = opts.ease || function (t) { return 1 - Math.pow(1 - t, 3); };
    function set(v) { el.textContent = prefix + v.toFixed(decimals) + suffix; }
    if (prefersReducedMotion() || dur <= 0) { set(target); return; }
    set(0);
    var start = null;
    function frame(now) {
      if (start === null) start = now;
      var t = Math.min(1, (now - start) / dur);
      set(target * ease(t));
      if (t < 1) requestAnimationFrame(frame); else set(target);
    }
    setTimeout(function () { requestAnimationFrame(frame); }, delay);
  }
  function initTheme(opts) {
    opts = opts || {};
    var KEY = opts.key || "rba-sentiment-theme";
    var html = document.documentElement;
    function apply(mode) { html.setAttribute("data-theme", mode); if (opts.onChange) opts.onChange(mode); }
    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    apply(saved || opts.def || "light");
    return {
      get: function () { return html.getAttribute("data-theme"); },
      toggle: function () {
        var next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
        try { localStorage.setItem(KEY, next); } catch (e) {}
        apply(next);
        return next;
      }
    };
  }
  function setupFilters(opts) {
    var yearSel = opts.yearSel, checks = opts.checks, resetBtn = opts.resetBtn,
      statusEl = opts.statusEl, onApply = opts.onApply, rows = opts.rows || [];
    var years = [];
    rows.forEach(function (r) { var y = yearOf(r.decision.date); if (years.indexOf(y) < 0) years.push(y); });
    years.sort();
    years.forEach(function (y) { var o = document.createElement("option"); o.value = y; o.textContent = y; yearSel.appendChild(o); });
    function currentTypes() { var t = {}; checks.forEach(function (cb) { t[cb.value] = cb.checked; }); return t; }
    function apply() {
      var year = yearSel.value, types = currentTypes();
      var shown = onApply(year, types);
      if (statusEl) statusEl.textContent = "Showing " + shown + " of " + rows.length + " decisions" + (year === "all" ? "" : " in " + year) + ".";
    }
    yearSel.addEventListener("change", apply);
    checks.forEach(function (cb) { cb.addEventListener("change", apply); });
    if (resetBtn) resetBtn.addEventListener("click", function () { yearSel.value = "all"; checks.forEach(function (cb) { cb.checked = true; }); apply(); });
    apply();
  }
  function revealOnLoad() {
    var done = false;
    function go() { if (done) return; done = true; document.documentElement.setAttribute("data-revealed", "1"); }
    requestAnimationFrame(function () { requestAnimationFrame(go); });
    setTimeout(go, 140);
  }

  return {
    // pure
    parseDate: parseDate, ts: ts, yearOf: yearOf, formatDate: formatDate, formatDateShort: formatDateShort,
    fmtRate: fmtRate, fmtPP: fmtPP, fmtChange: fmtChange, escapeHtml: escapeHtml,
    signed: signed, stanceBucket: stanceBucket, confidenceBucket: confidenceBucket,
    dominantSubDimension: dominantSubDimension, describeOutcome: describeOutcome,
    joinDecisions: joinDecisions, buildHeadline: buildHeadline,
    // browser-only
    prefersReducedMotion: prefersReducedMotion, cssVar: cssVar, countUp: countUp,
    initTheme: initTheme, setupFilters: setupFilters, revealOnLoad: revealOnLoad
    // render fns (buildStanceChart, renderRecordTable, renderDetail) added in later phases
  };
});
