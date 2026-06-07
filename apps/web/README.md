# RBA Policy Sentiment — web (`apps/web`)

Static, build-free front end. Plain HTML/CSS/JS + vendored Apache ECharts — the same stack as the RBA Board Vote Tracker. It renders the precomputed JSON the scorer produces; there is no server and no API key.

## Data

The site reads `data/decisions.json` + `data/scores.json`. These are **generated** by syncing the scorer's output (repo-root `data/`). `apps/web/data/` is gitignored and must never be hand-edited.

```
node scripts/sync-data.mjs    # copies repo-root data/{decisions,scores}.json -> apps/web/data/
```

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

## QA checklist (run before shipping)

- [ ] Light + dark themes legible (AA contrast)
- [ ] ~375px mobile: hero, chart, table usable
- [ ] Full keyboard pass: skip link, theme toggle, filters, table rows, detail panel
- [ ] No-JS: the `<noscript>` message points to the RBA
- [ ] Data missing / fetch fails: graceful message links to the RBA
- [ ] Deep link `#<decision-id>` opens that decision's breakdown
