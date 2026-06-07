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

  // ---------- render: stance chart (FR-003) ----------
  var SYM_UP = "path://M512 96 L928 864 L96 864 Z";
  var SYM_DOWN = "path://M96 160 L928 160 L512 928 Z";
  var DAY = 86400000;

  function buildStanceChart(elId, rows, cfg) {
    cfg = cfg || {};
    var el = typeof elId === "string" ? document.getElementById(elId) : elId;
    if (!el) return null;
    if (typeof echarts === "undefined") {
      el.innerHTML = '<p style="padding:18px;opacity:.6">The chart could not load. The full record is in the table below.</p>';
      return { update: function () {}, rebuild: function () {}, resize: function () {} };
    }
    var chart = null, curYear = "all", curTypes = { cut: true, hold: true, hike: true };

    function theme() {
      return {
        ink: cssVar("--chart-ink", cssVar("--ink", "#222")),
        accent: cssVar("--chart-accent", cssVar("--accent", "#1d4ed8")),
        muted: cssVar("--chart-muted", cssVar("--muted", "#888")),
        line: cssVar("--chart-line", cssVar("--hair", "#ccc")),
        grid: cssVar("--chart-grid", cssVar("--grid", "#eee")),
        bg: cssVar("--bg", "#fff"),
        font: cssVar("--font", "sans-serif")
      };
    }
    function inYear(r) { return curYear === "all" || yearOf(r.decision.date) === curYear; }
    function linePoints() { return rows.filter(inYear).map(function (r) { return [ts(r.decision.date), r.score.net]; }); }
    function markerSeries(action, t) {
      var names = { hike: "Hike", hold: "Hold", cut: "Cut" }, sym = { hike: SYM_UP, hold: "circle", cut: SYM_DOWN };
      return {
        name: names[action], type: "scatter", symbol: sym[action],
        symbolSize: action === "hold" ? 11 : 13, z: 10,
        itemStyle: { color: t.accent, borderColor: t.bg, borderWidth: 1.5 },
        emphasis: { scale: 1.4 },
        data: rows.filter(function (r) { return r.decision.outcome.action === action && inYear(r) && curTypes[action]; })
          .map(function (r) { return { value: [ts(r.decision.date), r.score.net], row: r }; })
      };
    }
    function yearWindow() {
      if (curYear === "all") return [null, null];
      return [ts(curYear + "-01-01") - 20 * DAY, ts(curYear + "-12-31") + 20 * DAY];
    }
    function tooltip(p) {
      var r = p.data && p.data.row; if (!r) return "";
      var d = r.decision, s = r.score, o = describeOutcome(d), b = stanceBucket(s.net), cb = confidenceBucket(s.confidence);
      return "<strong>" + formatDate(d.date) + "</strong><br>"
        + b.label + " · net " + signed(s.net) + "<br>"
        + "Inflation " + signed(s.sub_scores.inflation) + " · Growth " + signed(s.sub_scores.growth) + " · Employment " + signed(s.sub_scores.employment) + "<br>"
        + o.label + " · cash rate " + fmtRate(d.cash_rate_target) + "<br>Confidence " + cb.pct + "%";
    }
    function render() {
      if (chart) chart.dispose();
      var t = theme();
      chart = echarts.init(el, null, { renderer: "svg" });
      var anim = !prefersReducedMotion();
      chart.setOption({
        animation: anim, animationDuration: anim ? 1100 : 0, animationEasing: "cubicOut",
        textStyle: { fontFamily: t.font, color: t.ink },
        grid: { left: 4, right: 16, top: 38, bottom: 4, containLabel: true },
        legend: {
          top: 4, selectedMode: false, itemGap: 16, icon: "roundRect",
          textStyle: { color: t.muted, fontSize: 11, fontFamily: t.font },
          data: [{ name: "Net stance", icon: "line" }, { name: "Hike", icon: SYM_UP }, { name: "Hold", icon: "circle" }, { name: "Cut", icon: SYM_DOWN }]
        },
        tooltip: {
          trigger: "item", confine: true, triggerOn: "mousemove|click",
          backgroundColor: cssVar("--chart-tip-bg", "#fff"), borderColor: t.line, borderWidth: 1,
          textStyle: { color: cssVar("--chart-tip-ink", t.ink), fontSize: 12.5, fontFamily: t.font },
          extraCssText: "box-shadow:0 8px 30px rgba(0,0,0,.18);border-radius:10px;padding:9px 12px;max-width:280px;white-space:normal;",
          formatter: tooltip
        },
        xAxis: {
          type: "time", axisLine: { lineStyle: { color: t.line } }, axisTick: { lineStyle: { color: t.line } },
          axisLabel: { color: t.muted, fontSize: 11, fontFamily: t.font }, splitLine: { show: false }
        },
        yAxis: {
          type: "value", min: -1, max: 1, interval: 0.5,
          axisLabel: { color: t.muted, fontSize: 11, fontFamily: t.font },
          axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: t.grid } }
        },
        series: [
          {
            name: "Net stance", type: "line", data: linePoints(), showSymbol: false, z: 3,
            lineStyle: { color: t.ink, width: 2 },
            markLine: {
              symbol: "none", silent: true,
              lineStyle: { color: t.muted, type: "dashed", width: 1, opacity: .7 },
              label: { show: true, formatter: "Neutral", position: "insideEndTop", color: t.muted, fontSize: 10.5, fontFamily: t.font },
              data: [{ yAxis: 0 }]
            }
          },
          markerSeries("hike", t), markerSeries("hold", t), markerSeries("cut", t)
        ]
      });
      chart.off("click");
      chart.on("click", function (p) { if (p.data && p.data.row && cfg.onSelect) cfg.onSelect(p.data.row.decision.id); });
      chart.setOption({ xAxis: { min: yearWindow()[0], max: yearWindow()[1] } });
    }
    function update(year, types) {
      curYear = year; curTypes = types;
      if (!chart) return;
      var t = theme();
      chart.setOption({
        xAxis: { min: yearWindow()[0], max: yearWindow()[1] },
        series: [{ data: linePoints() }, markerSeries("hike", t), markerSeries("hold", t), markerSeries("cut", t)]
      });
    }
    render();
    var raf;
    window.addEventListener("resize", function () { cancelAnimationFrame(raf); raf = requestAnimationFrame(function () { if (chart) chart.resize(); }); });
    return { update: update, rebuild: function () { render(); }, resize: function () { if (chart) chart.resize(); } };
  }

  // ---------- render: full-record table (NFR-005) ----------
  function renderRecordTable(tbody, rows) {
    var tb = typeof tbody === "string" ? document.getElementById(tbody) : tbody;
    if (!rows.length) { tb.innerHTML = '<tr class="empty-row"><td colspan="7">No decisions match these filters.</td></tr>'; return 0; }
    tb.innerHTML = rows.slice().reverse().map(function (r) {
      var d = r.decision, s = r.score, o = describeOutcome(d), b = stanceBucket(s.net), cb = confidenceBucket(s.confidence);
      return '<tr data-id="' + d.id + '" tabindex="0" role="button" aria-label="'
        + escapeHtml(formatDate(d.date) + ", " + b.label + ", net " + signed(s.net) + ". Open breakdown.") + '">'
        + '<td class="num">' + formatDateShort(d.date) + "</td>"
        + '<td><span class="cell-decision" data-dir="' + o.dir + '"><span class="glyph" aria-hidden="true">' + o.glyph + "</span>" + o.label + "</span></td>"
        + '<td class="num">' + fmtChange(o.change_bps) + "</td>"
        + '<td class="num rate">' + fmtRate(d.cash_rate_target) + "</td>"
        + '<td class="num">' + signed(s.net) + ' <span class="stance-tag stance-' + b.key + '">' + b.label + "</span></td>"
        + '<td class="num">' + cb.pct + "%</td>"
        + '<td><a href="' + d.source_url + '" rel="noopener" data-noselect>RBA&nbsp;statement ↗</a></td>'
        + "</tr>";
    }).join("");
    return rows.length;
  }

  // ---------- render: detail breakdown (FR-005 + FR-011) ----------
  function subsInline(sub) {
    return ["inflation", "growth", "employment"].map(function (k) {
      return '<span class="sub-inline"><span class="sub-name">' + k + '</span> <span class="num">' + signed(sub[k]) + "</span></span>";
    }).join("");
  }
  function miniScale(net) {
    var pct = Math.max(0, Math.min(100, (Number(net) + 1) / 2 * 100));
    return '<span class="scale mini"><span class="scale-marker" style="left:' + pct.toFixed(1) + '%"></span></span>';
  }
  function renderDetail(container, row) {
    var c = typeof container === "string" ? document.getElementById(container) : container;
    var d = row.decision, s = row.score, o = describeOutcome(d), b = stanceBucket(s.net), cb = confidenceBucket(s.confidence);

    var comps = Object.keys(s.components || {}).map(function (name) {
      var comp = s.components[name], extra = "";
      if (name === "lexicon" && comp.matched_terms) {
        extra = comp.matched_terms.length
          ? '<p class="muted-line">Matched: ' + comp.matched_terms.map(function (term) {
              return "<code>" + escapeHtml(typeof term === "string" ? term : (term.term || "")) + "</code>"; }).join(" ") + "</p>"
          : '<p class="muted-line">No lexicon terms matched.</p>';
      }
      if (name === "llm" && comp.rationale) extra = '<p class="muted-line">' + escapeHtml(comp.rationale) + "</p>";
      return '<div class="component-card"><h4>' + escapeHtml(name) + ' <span class="ver">' + escapeHtml(comp.version || "") + "</span></h4>"
        + '<p class="num">net ' + signed(comp.net) + "</p>"
        + '<p class="subs-inline">' + subsInline(comp.sub_scores || { inflation: 0, growth: 0, employment: 0 }) + "</p>"
        + extra + "</div>";
    }).join("");

    var rec = s.reconciliation || {};
    var weights = rec.weights ? Object.keys(rec.weights).map(function (k) { return k + " " + rec.weights[k]; }).join(", ") : "—";
    var evi = (s.evidence_phrases || []).map(function (e) {
      return '<span class="evi-chip"><span class="pol">' + escapeHtml(e.polarity) + '</span> · <span class="dim">' + escapeHtml(e.dimension) + "</span> · " + escapeHtml(e.text) + "</span>";
    }).join("");

    c.innerHTML =
      '<div class="detail-head"><strong>' + formatDate(d.date) + "</strong>"
        + '<span class="chip"><span class="glyph" aria-hidden="true">' + o.glyph + "</span> " + o.label + " · " + fmtRate(d.cash_rate_target) + "</span>"
        + '<a class="read" href="' + d.source_url + '" rel="noopener">Read the RBA statement <span class="ar">→</span></a></div>'
      + '<div class="detail-reconciled"><p class="eyebrow">Reconciled result</p>'
        + '<p><span class="num big">' + signed(s.net) + '</span> <span class="stance-tag stance-' + b.key + '">' + b.label + "</span></p>"
        + miniScale(s.net)
        + '<p class="subs-inline" style="margin-top:14px">' + subsInline(s.sub_scores) + "</p>"
        + '<p class="muted-line">Confidence ' + cb.label.toLowerCase() + " · " + cb.pct + "% · component disagreement " + Number(rec.disagreement || 0).toFixed(3) + "</p></div>"
      + '<p class="eyebrow" style="margin-top:26px">Components</p><div class="detail-grid">' + comps + "</div>"
      + '<p class="muted-line">Reconciliation — ' + escapeHtml(rec.method || "—") + " (" + escapeHtml(weights) + ")</p>"
      + (evi ? '<p class="eyebrow" style="margin-top:26px">Evidence phrases</p><div class="evi-list">' + evi + "</div>" : "")
      + '<p class="detail-foot">Engine ' + escapeHtml(s.engine_version || "") + " · scored " + escapeHtml((s.scored_at || "").slice(0, 10)) + "</p>";
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
    initTheme: initTheme, setupFilters: setupFilters, revealOnLoad: revealOnLoad,
    buildStanceChart: buildStanceChart, renderRecordTable: renderRecordTable, renderDetail: renderDetail
  };
});
