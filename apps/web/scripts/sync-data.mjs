// Copies the scorer's precomputed JSON contract into the web app's served directory,
// then derives the published CSV (FR-008) from that same contract. The single source of
// truth is the repo-root data/ (scorer output); apps/web/data/ is generated + gitignored
// and must never be hand-edited. Runs at local preview time and as the Vercel build
// command. Pure Node, no dependencies — the CSV column logic is single-sourced in core.js.
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url)); // apps/web/scripts
const repoData = resolve(here, "../../../data");      // repo-root data/
const outDir = resolve(here, "../data");              // apps/web/data/
const files = ["decisions.json", "scores.json"];

mkdirSync(outDir, { recursive: true });
for (const f of files) {
  copyFileSync(resolve(repoData, f), resolve(outDir, f));
  console.log(`synced ${f}`);
}

// Precompute scores.csv from the same JSON, reusing core.js so the column contract
// stays unit-tested and identical to what the site documents. Served as a static file.
const C = require("../core.js");
const decisions = JSON.parse(readFileSync(resolve(repoData, "decisions.json"), "utf8"));
const scores = JSON.parse(readFileSync(resolve(repoData, "scores.json"), "utf8"));
const rows = C.joinDecisions(decisions, scores);
writeFileSync(resolve(outDir, "scores.csv"), C.buildScoresCsv(rows));
console.log(`built scores.csv (${rows.length} rows)`);

console.log(`✓ data synced → ${outDir}`);
