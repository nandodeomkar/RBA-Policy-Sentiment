# RBA Policy Sentiment — web (`apps/web`)

Static, build-free front end. Plain HTML/CSS/JS + vendored Apache ECharts — the same stack as the RBA Board Vote Tracker. It renders the precomputed JSON the scorer produces; there is no server and no API key.

## Data

The site reads `data/decisions.json` + `data/scores.json`. These are **generated** by syncing the scorer's output (repo-root `data/`). `apps/web/data/` is gitignored and must never be hand-edited.

```
node scripts/sync-data.mjs    # copies repo-root data/{decisions,scores}.json -> apps/web/data/
                              # and derives data/scores.csv (the FR-008 download)
```

The published **`data/scores.csv`** (one row per decision) is precomputed by this same step — the column logic lives in `core.js` (`buildScoresCsv`), so it stays unit-tested and identical to what the methodology page documents.

No Node? PowerShell equivalent:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Copy-Item ..\..\data\decisions.json, ..\..\data\scores.json .\data\
```

## Local preview

`fetch()` needs http(s), so serve over a static server (not `file://`):

```
node scripts/sync-data.mjs
python -m http.server 8080     # then open http://localhost:8080
```

## Tests

```
node --test                    # unit tests for the pure helpers in core.js (run from apps/web)
```

## Deploy (Vercel, free tier)

| Setting | Value |
| ------- | ----- |
| Root Directory | `apps/web` |
| Build Command | `node scripts/sync-data.mjs` |
| Output Directory | `.` |
| Framework Preset | Other / None |

## Resilience & decision-day operations (NFR-007/008)

The site is **static-first**, which is the whole resilience story — there is no
always-on service to fall over:

- **Last good data stays live.** Vercel serves precomputed JSON/CSV from its CDN. New
  data only goes live when the maintainer commits it. So a failed scoring job means we
  simply *don't push* — the previously published data keeps serving, unchanged (NFR-007).
  The scorer enforces this too: a missing key/model aborts **before** writing, leaving
  `data/scores.json` intact (see [`../scorer/REFRESH.md`](../scorer/REFRESH.md)).
- **Decision-day spikes are absorbed by the CDN.** The RBA decides ~8×/year (≈2:30 pm
  AEST); static delivery scales to those bursts with nothing to provision (NFR-008).
- **Fetch-failure fallback.** If the data can't load, the page shows a graceful message
  linking to the RBA's decisions page rather than a broken screen (`showError` in
  `app.js`) — kept in the QA checklist below.
- **No fake "awaiting" state.** The hero always shows the latest *scored* decision — the
  honest state between meetings. We deliberately do **not** track a future-meeting
  calendar (that drifts toward the forecasting non-goal).

**Adding a new decision** is the manual, offline refresh in
[`../scorer/REFRESH.md`](../scorer/REFRESH.md) (FR-009).

## QA checklist (run before shipping)

- [ ] Light + dark themes legible (AA contrast) — home **and** `methodology.html`
- [ ] ~375px mobile: hero, explainer cards, chart, table usable
- [ ] Full keyboard pass: skip link, theme toggle, filters, **cash-rate toggle**, table rows, detail panel, CSV download
- [ ] No-JS: the `<noscript>` message points to the RBA
- [ ] Data missing / fetch fails: graceful message links to the RBA
- [ ] Deep link `#<decision-id>` opens that decision's breakdown
- [ ] **Download CSV** returns a well-formed file (header + one row per decision)
- [ ] **Methodology page** loads; corpus size, engine + component versions fill from live data
- [ ] **Cash-rate overlay (FR-004):** off by default; the **Cash rate** toggle adds a right-hand `%` axis + stepped line aligned to the time axis; the line shows its target % on hover; Year/Outcome filters still drive chart + table with it on; **Reset** clears it; legible in light/dark/~375px
- [ ] **Date zoom + shareable URL (FR-010):** the slider windows the chart **and** the table together; the Year select sets the window and a custom drag flips Year to "All"; **Reset** clears window/outcomes/overlay and the query; a copied URL restores the window + outcomes + overlay + open decision
- [ ] **Tone summary (FR-012):** the plain-language summary shows on the hero **and** in every decision's detail panel, and falls back to the deterministic headline when a record has no `tone_summary`
