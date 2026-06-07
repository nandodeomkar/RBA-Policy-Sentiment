// Copies the scorer's precomputed JSON contract into the web app's served directory.
// The single source of truth is the repo-root data/ (scorer output); apps/web/data/
// is generated + gitignored and must never be hand-edited. Runs at local preview time
// and as the Vercel build command. Pure Node, no dependencies.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url)); // apps/web/scripts
const repoData = resolve(here, "../../../data");      // repo-root data/
const outDir = resolve(here, "../data");              // apps/web/data/
const files = ["decisions.json", "scores.json"];

mkdirSync(outDir, { recursive: true });
for (const f of files) {
  copyFileSync(resolve(repoData, f), resolve(outDir, f));
  console.log(`synced ${f}`);
}
console.log(`✓ data synced → ${outDir}`);
