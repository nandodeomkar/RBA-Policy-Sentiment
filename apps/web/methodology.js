/* ============================================================
   Methodology page wiring. Theme toggle + privacy-friendly view
   event, then progressive-enhancement: overwrite the page's
   data-driven facts (corpus size, date range, outcome tallies,
   engine + component versions) from the live contract. The HTML
   carries correct defaults, so the page reads fine if this fails.
   ============================================================ */
(function () {
  "use strict";
  var C = window.RBACore;

  // theme (same key as the home page, so the choice persists across pages)
  var themeLabel = document.getElementById("theme-label");
  var themeApi = C.initTheme({
    def: "light", key: "rba-sentiment-theme",
    onChange: function (mode) { if (themeLabel) themeLabel.textContent = mode === "dark" ? "Light" : "Dark"; }
  });
  var toggleBtn = document.getElementById("theme-toggle");
  if (toggleBtn) toggleBtn.addEventListener("click", themeApi.toggle);

  // privacy-friendly page-view event (no-op locally; activates on Vercel)
  if (window.va) window.va("event", { name: "methodology_view" });

  // data-driven facts
  Promise.all([
    fetch("data/decisions.json", { cache: "no-cache" }).then(okJson),
    fetch("data/scores.json", { cache: "no-cache" }).then(okJson)
  ]).then(function (res) { fill(res[0], res[1]); })
    .catch(function (e) { if (typeof console !== "undefined") console.warn("methodology: using static fallback —", e.message); });

  function okJson(r) { if (!r.ok) throw new Error("HTTP " + r.status + " for " + r.url); return r.json(); }
  function setText(id, t) { var el = document.getElementById(id); if (el) el.textContent = t; }

  function fill(decisions, scores) {
    var rows = C.joinDecisions(decisions, scores);
    if (!rows.length) return;

    setText("corpus-count", String(rows.length));
    setText("corpus-range", C.formatDate(rows[0].decision.date) + " – " + C.formatDate(rows[rows.length - 1].decision.date));

    var t = { cut: 0, hold: 0, hike: 0 };
    rows.forEach(function (r) { var a = r.decision.outcome.action; if (t[a] != null) t[a]++; });
    setText("corpus-tally", t.hold + " holds, " + t.hike + " hikes, " + t.cut + " cuts");

    var latest = rows[rows.length - 1].score;

    // engine fingerprint (body + footer)
    var ev = latest.engine_version || "—";
    var engineEls = document.querySelectorAll(".js-engine");
    for (var i = 0; i < engineEls.length; i++) engineEls[i].textContent = ev;
    setText("engine-version", ev);

    // per-component versions
    var compEl = document.getElementById("components");
    if (compEl && latest.components) {
      compEl.innerHTML = Object.keys(latest.components).map(function (name) {
        var v = (latest.components[name] && latest.components[name].version) || "";
        return '<li><strong>' + C.escapeHtml(name) + '</strong><span class="ver">' + C.escapeHtml(v) + "</span></li>";
      }).join("");
    }

    // reconciliation method + weights
    var rec = latest.reconciliation || {};
    if (rec.method) {
      var w = rec.weights ? Object.keys(rec.weights).map(function (k) { return k + " " + rec.weights[k]; }).join(", ") : "";
      setText("reconcile-method", rec.method + (w ? " (" + w + ")" : ""));
    }
  }
})();
