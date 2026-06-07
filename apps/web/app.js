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

  // ---- load data ----
  Promise.all([
    fetch("data/decisions.json").then(okJson),
    fetch("data/scores.json").then(okJson)
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
    byId("hero-h").innerHTML = headlineHtml(d, s);

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

  // ---- record section: chart + table + detail + filters ----
  function initRecord(rows) {
    var tbody = byId("record-tbody");
    var detailSection = byId("detail-section");
    var detailEl = byId("detail");

    var byIdMap = {};
    rows.forEach(function (r) { byIdMap[r.decision.id] = r; });

    var chart = C.buildStanceChart("chart", rows, { onSelect: openDetail });
    window.__rbaChart = chart;

    function applyFilter(year, types) {
      return rows.filter(function (r) {
        return (year === "all" || C.yearOf(r.decision.date) === year) && types[r.decision.outcome.action];
      });
    }
    C.setupFilters({
      yearSel: byId("filter-year"),
      checks: Array.prototype.slice.call(document.querySelectorAll('input[name="type"]')),
      resetBtn: byId("filter-reset"),
      statusEl: byId("filter-status"),
      rows: rows,
      onApply: function (year, types) {
        var filtered = applyFilter(year, types);
        var n = C.renderRecordTable(tbody, filtered);
        chart.update(year, types);
        return n;
      }
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
      if (location.hash !== "#" + id) history.replaceState(null, "", "#" + id);
      detailSection.scrollIntoView({ behavior: C.prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    }

    // deep link on load + on hash change
    function fromHash() {
      var id = decodeURIComponent(location.hash.replace(/^#/, ""));
      if (id && byIdMap[id]) openDetail(id);
    }
    fromHash();
    window.addEventListener("hashchange", fromHash);
  }

  function byId(id) { return document.getElementById(id); }
})();
