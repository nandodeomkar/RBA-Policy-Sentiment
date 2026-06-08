/* ============================================================
   RBA Policy Sentiment — page wiring.
   Reusable logic lives in core.js (window.RBACore). This file
   loads the data and renders the page. The record section
   (chart, table, detail, filters) is wired in Phase D.
   ============================================================ */
(function () {
  "use strict";
  var C = window.RBACore;

  // ---- theme (works before data loads) ----
  var themeLabel = document.getElementById("theme-label");
  var themeApi = C.initTheme({
    def: "light", key: "rba-sentiment-theme",
    onChange: function (mode) {
      if (themeLabel) themeLabel.textContent = mode === "dark" ? "Light" : "Dark";
      if (window.__rbaChart) window.__rbaChart.rebuild(); // re-read CSS vars after theme switch (Phase D)
    }
  });
  var toggleBtn = document.getElementById("theme-toggle");
  if (toggleBtn) toggleBtn.addEventListener("click", themeApi.toggle);

  // CSV download (FR-008) — privacy-friendly event; the link works regardless.
  var csvLink = document.getElementById("csv-download");
  if (csvLink) csvLink.addEventListener("click", function () {
    if (window.va) window.va("event", { name: "csv_download" });
  });

  // ---- load data ----
  Promise.all([
    fetch("data/decisions.json", { cache: "no-cache" }).then(okJson),
    fetch("data/scores.json", { cache: "no-cache" }).then(okJson)
  ]).then(function (res) {
    render(res[0], res[1]);
  }).catch(function (err) {
    console.error(err);
    showError();
  });

  function okJson(r) { if (!r.ok) throw new Error("HTTP " + r.status + " for " + r.url); return r.json(); }

  function render(decisions, scores) {
    var rows = C.joinDecisions(decisions, scores);
    if (!rows.length) { showError(); return; }

    var latest = rows[rows.length - 1];
    renderHero(latest);
    setEngineVersion(latest.score.engine_version);

    initRecord(rows);

    C.revealOnLoad();
  }

  // ---- hero ----
  function renderHero(row) {
    var d = row.decision, s = row.score;
    var bucket = C.stanceBucket(s.net);
    var out = C.describeOutcome(d);

    byId("hero-eyebrow").textContent = "Latest decision · " + C.formatDate(d.date);
    // FR-012: the LLM tone summary leads when present; the deterministic headline is the fallback.
    var heroH = byId("hero-h");
    if (s.tone_summary) {
      heroH.textContent = s.tone_summary;
      heroH.classList.add("hero-statement--summary");
    } else {
      heroH.innerHTML = headlineHtml(d, s);
    }

    byId("stance-num").textContent = C.signed(s.net);
    var labelEl = byId("stance-label");
    labelEl.textContent = bucket.label;
    labelEl.className = "stance-label stance-" + bucket.key;
    setScale(byId("stance-scale"), s.net);

    byId("hero-subs").appendChild(subsList(s.sub_scores));

    byId("hero-outcome").innerHTML = '<span class="glyph" aria-hidden="true">' + out.glyph + "</span> "
      + out.label + " · " + C.fmtRate(d.cash_rate_target);
    var cb = C.confidenceBucket(s.confidence);
    byId("hero-conf").innerHTML = '<span class="dot conf-' + cb.key + '"></span>' + cb.label + " confidence · " + cb.pct + "%";

    var q = pickQuote(s);
    if (q) byId("hero-quote").textContent = "“" + q.text + "”";
    else byId("hero-quote").style.display = "none";

    byId("hero-read").href = d.source_url;
  }

  function headlineHtml(d, s) {
    var phrase = C.stanceBucket(s.net).label.toLowerCase();
    var plain = C.escapeHtml(C.buildHeadline(d, s));
    return plain.replace(phrase, '<span class="accent">' + phrase + "</span>");
  }

  // diverging scale marker: net −1..+1 → 0..100% from the left.
  function setScale(el, net) {
    var pct = Math.max(0, Math.min(100, (Number(net) + 1) / 2 * 100));
    el.innerHTML = '<span class="scale-marker" style="left:' + pct.toFixed(1) + '%"></span>';
  }

  function subsList(sub) {
    var frag = document.createDocumentFragment();
    ["inflation", "growth", "employment"].forEach(function (k) {
      var v = Number(sub[k]);
      var row = document.createElement("div");
      row.className = "sub-row";
      row.innerHTML = '<span class="sub-name">' + k + "</span>"
        + '<span class="sub-bar">' + barHtml(v) + "</span>"
        + '<span class="sub-val num">' + C.signed(v) + "</span>";
      frag.appendChild(row);
    });
    return frag;
  }
  function barHtml(v) {
    var half = Math.max(0, Math.min(50, Math.abs(v) * 50));
    var side = v >= 0 ? "left:50%" : "right:50%";
    return '<span class="sub-fill" style="' + side + ";width:" + half.toFixed(1) + '%"></span>';
  }

  // first evidence phrase matching the net sign; fallback to the first.
  function pickQuote(s) {
    var ev = s.evidence_phrases || [];
    if (!ev.length) return null;
    var want = s.net > 0 ? "hawkish" : (s.net < 0 ? "dovish" : null);
    if (want) { for (var i = 0; i < ev.length; i++) { if (ev[i].polarity === want) return ev[i]; } }
    return ev[0];
  }

  function setEngineVersion(v) {
    var el = byId("engine-version");
    if (el && v) el.textContent = v;
  }

  function showError() {
    var hero = byId("hero");
    if (hero) {
      hero.innerHTML = '<p class="eyebrow">Latest decision</p>'
        + '<h1 class="hero-statement">The data couldn’t be loaded.</h1>'
        + '<p style="color:var(--ink-2);max-width:60ch">Please refresh, or read the decisions directly on the '
        + '<a class="accent" href="https://www.rba.gov.au/monetary-policy/int-rate-decisions/">RBA’s monetary policy decisions page</a>.</p>';
    }
    document.documentElement.setAttribute("data-revealed", "1");
  }

  // ---- record section: chart + table + detail + filters (FR-003/005/010) ----
  function initRecord(rows) {
    var tbody = byId("record-tbody");
    var detailSection = byId("detail-section");
    var detailEl = byId("detail");
    var statusEl = byId("filter-status");
    var yearSel = byId("filter-year");
    var rateCheck = byId("filter-rate");
    var checks = Array.prototype.slice.call(document.querySelectorAll('input[name="type"]'));

    var byIdMap = {};
    rows.forEach(function (r) { byIdMap[r.decision.id] = r; });

    // canonical, shareable view-state (FR-010): date window + outcomes + overlay
    var view = { from: null, to: null, types: { cut: true, hold: true, hike: true }, rate: false };

    var chart = C.buildStanceChart("chart", rows, { onSelect: openDetail, onWindowChange: onDragWindow });
    window.__rbaChart = chart;

    function inWindow(r) {
      var d = r.decision.date;
      return (!view.from || d >= view.from) && (!view.to || d <= view.to);
    }
    function readToggles() {
      var t = {}; checks.forEach(function (cb) { t[cb.value] = cb.checked; }); view.types = t;
      view.rate = !!(rateCheck && rateCheck.checked);
    }
    function setUrl() {
      // encodeViewState reads `out`; our view keeps outcomes under `types`.
      var qs = C.encodeViewState({ from: view.from, to: view.to, out: view.types, rate: view.rate });
      history.replaceState(null, "", location.pathname + qs + location.hash);
    }
    // Render everything from `view`. `fromDrag` = the chart already moved (slider
    // drag), so sync the table/URL/Year display but don't push the window back to it.
    function applyView(fromDrag) {
      if (!fromDrag) chart.setView({ from: view.from, to: view.to, types: view.types, rate: view.rate });
      if (yearSel) yearSel.value = C.yearForWindow(view.from, view.to) || "all";
      var filtered = rows.filter(function (r) { return inWindow(r) && view.types[r.decision.outcome.action]; });
      var n = C.renderRecordTable(tbody, filtered);
      if (statusEl) {
        var yr = C.yearForWindow(view.from, view.to);
        var scope = view.from && view.to ? (yr ? " in " + yr : " in range") : "";
        statusEl.textContent = "Showing " + n + " of " + rows.length + " decisions" + scope + ".";
      }
      setUrl();
    }

    // coalesce rapid-fire slider drags to one render per frame
    var dragRaf = null, dragWin = null;
    function onDragWindow(from, to) {
      dragWin = { from: from, to: to };
      if (dragRaf) return;
      dragRaf = requestAnimationFrame(function () {
        dragRaf = null; view.from = dragWin.from; view.to = dragWin.to; applyView(true);
      });
    }

    C.setupFilters({
      yearSel: yearSel, checks: checks, rateCheck: rateCheck, resetBtn: byId("filter-reset"), rows: rows,
      onYear: function (year) { var w = C.windowForYear(year); view.from = w.from; view.to = w.to; applyView(); },
      onToggle: function () { readToggles(); applyView(); },
      onReset: function () { view = { from: null, to: null, types: { cut: true, hold: true, hike: true }, rate: false }; applyView(); }
    });

    // delegated row selection (click + keyboard)
    tbody.addEventListener("click", function (e) {
      if (e.target.closest("[data-noselect]")) return;
      var tr = e.target.closest("tr[data-id]");
      if (tr) openDetail(tr.getAttribute("data-id"));
    });
    tbody.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var tr = e.target.closest("tr[data-id]");
      if (tr) { e.preventDefault(); openDetail(tr.getAttribute("data-id")); }
    });

    function openDetail(id) {
      var r = byIdMap[id];
      if (!r) return;
      C.renderDetail(detailEl, r);
      detailSection.hidden = false;
      // keep the view query, just set/refresh the decision hash
      if (location.hash !== "#" + id) history.replaceState(null, "", location.pathname + location.search + "#" + id);
      detailSection.scrollIntoView({ behavior: C.prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    }

    // initial: restore the view from the URL, reflect it into the controls, render, then open any deep-linked decision
    var decoded = C.decodeViewState(location.search);
    view.from = decoded.from; view.to = decoded.to; view.types = decoded.out; view.rate = decoded.rate;
    checks.forEach(function (cb) { cb.checked = !!view.types[cb.value]; });
    if (rateCheck) rateCheck.checked = !!view.rate;
    applyView();

    function fromHash() {
      var id = decodeURIComponent(location.hash.replace(/^#/, ""));
      if (id && byIdMap[id]) openDetail(id);
    }
    fromHash();
    window.addEventListener("hashchange", fromHash);
  }

  function byId(id) { return document.getElementById(id); }
})();
