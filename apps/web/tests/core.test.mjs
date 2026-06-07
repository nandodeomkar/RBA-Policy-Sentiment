import test from "node:test";
import assert from "node:assert/strict";
import C from "../core.js";

test("stanceBucket — half-open boundaries", () => {
  assert.equal(C.stanceBucket(-0.80).key, "strong-dovish");
  assert.equal(C.stanceBucket(-0.60).key, "strong-dovish"); // ≤ −0.60
  assert.equal(C.stanceBucket(-0.50).key, "dovish");
  assert.equal(C.stanceBucket(-0.15).key, "dovish");        // ≤ −0.15
  assert.equal(C.stanceBucket(-0.149).key, "neutral");
  assert.equal(C.stanceBucket(0).key, "neutral");
  assert.equal(C.stanceBucket(0.149).key, "neutral");
  assert.equal(C.stanceBucket(0.15).key, "hawkish");        // ≥ +0.15
  assert.equal(C.stanceBucket(0.59).key, "hawkish");
  assert.equal(C.stanceBucket(0.60).key, "strong-hawkish"); // ≥ +0.60
  assert.equal(C.stanceBucket(0.90).key, "strong-hawkish");
});

test("confidenceBucket — boundaries + pct", () => {
  assert.equal(C.confidenceBucket(0.97).key, "high");
  assert.equal(C.confidenceBucket(0.80).key, "high");
  assert.equal(C.confidenceBucket(0.79).key, "moderate");
  assert.equal(C.confidenceBucket(0.50).key, "moderate");
  assert.equal(C.confidenceBucket(0.49).key, "low");
  assert.equal(C.confidenceBucket(0.12).key, "low");
  assert.equal(C.confidenceBucket(0.691).pct, 69);
});

test("signed — true minus glyph and explicit sign", () => {
  assert.equal(C.signed(0.309), "+0.31");
  assert.equal(C.signed(-0.312), "−0.31"); // U+2212
  assert.equal(C.signed(0), "0.00");
  assert.equal(C.signed(0.8, 1), "+0.8");
});

test("fmtChange", () => {
  assert.equal(C.fmtChange(0), "—");
  assert.equal(C.fmtChange(25), "+0.25%");
  assert.equal(C.fmtChange(-25), "−0.25%");
});

test("describeOutcome — maps action to glyph/dir", () => {
  assert.equal(C.describeOutcome({ outcome: { action: "hike", change_bps: 25 } }).dir, "up");
  assert.equal(C.describeOutcome({ outcome: { action: "cut", change_bps: -25 } }).dir, "down");
  assert.equal(C.describeOutcome({ outcome: { action: "hold", change_bps: 0 } }).dir, "flat");
  assert.equal(C.describeOutcome({ outcome: { action: "hike", change_bps: 25 } }).glyph, "▲");
});

test("dominantSubDimension — largest magnitude ≥ threshold, else null", () => {
  assert.equal(C.dominantSubDimension({ inflation: 0.40, growth: -0.31, employment: 0 }).key, "inflation");
  assert.equal(C.dominantSubDimension({ inflation: -0.20, growth: 0.50, employment: 0 }).key, "growth");
  assert.equal(C.dominantSubDimension({ inflation: 0.10, growth: -0.05, employment: 0 }), null);
});

test("joinDecisions — ascending order, skips missing scores", () => {
  const decisions = [
    { id: "2026-05-05", date: "2026-05-05" },
    { id: "2020-02-04", date: "2020-02-04" },
    { id: "2099-01-01", date: "2099-01-01" }, // no score → skipped
  ];
  const scores = { "2026-05-05": { net: 0.3 }, "2020-02-04": { net: -0.04 } };
  const rows = C.joinDecisions(decisions, scores);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].decision.id, "2020-02-04");
  assert.equal(rows[1].decision.id, "2026-05-05");
});

test("formatDate", () => {
  assert.equal(C.formatDate("2026-05-05"), "5 May 2026");
  assert.equal(C.formatDateShort("2026-05-05"), "5 May 2026");
});

test("buildHeadline — deterministic, hedged sentence (real latest decision)", () => {
  const h = C.buildHeadline(
    { date: "2026-05-05", cash_rate_target: 4.35, outcome: { action: "hike", change_bps: 25 } },
    { net: 0.309, sub_scores: { inflation: 0.398, growth: -0.312, employment: 0 } }
  );
  assert.match(h, /5 May 2026/);
  assert.match(h, /hawkish/);
  assert.match(h, /leaning inflation/);
  assert.match(h, /raised the cash rate by 0\.25%/);
  assert.match(h, /4\.35%/);
});

test("buildScoresCsv — header, one row per decision, FR-008 columns", () => {
  const rows = [
    { decision: { date: "2020-02-04", source_url: "https://www.rba.gov.au/a", outcome: { action: "hold", change_bps: 0 }, cash_rate_target: 0.75 },
      score: { net: -0.04, sub_scores: { inflation: -0.1, growth: 0, employment: 0.2 }, confidence: 0.6, engine_version: "engine-x" } },
    { decision: { date: "2026-05-05", source_url: "https://www.rba.gov.au/b", outcome: { action: "hike", change_bps: 25 }, cash_rate_target: 4.35 },
      score: { net: 0.277342, sub_scores: { inflation: 0.398214, growth: -0.3125, employment: 0 }, confidence: 0.743366, engine_version: "engine-x" } },
  ];
  const csv = C.buildScoresCsv(rows);
  const lines = csv.replace(/\r\n$/, "").split("\r\n");
  assert.equal(lines.length, 3); // header + 2 rows
  assert.equal(lines[0], "date,outcome,change_bps,cash_rate_target,net,inflation,growth,employment,confidence,engine_version,source_url");
  assert.equal(lines[1], "2020-02-04,hold,0,0.75,-0.04,-0.1,0,0.2,0.6,engine-x,https://www.rba.gov.au/a");
  // full precision preserved for citation; ASCII minus (machine-readable, not the display glyph)
  assert.equal(lines[2], "2026-05-05,hike,25,4.35,0.277342,0.398214,-0.3125,0,0.743366,engine-x,https://www.rba.gov.au/b");
  assert.ok(csv.endsWith("\r\n"));
});

test("buildScoresCsv — RFC-4180 quoting and empty input", () => {
  assert.equal(C.buildScoresCsv([]).replace(/\r\n$/, ""),
    "date,outcome,change_bps,cash_rate_target,net,inflation,growth,employment,confidence,engine_version,source_url");
  const csv = C.buildScoresCsv([
    { decision: { date: "2021-01-01", outcome: { action: "hold", change_bps: 0 }, cash_rate_target: 0.1 },
      score: { net: 0, sub_scores: {}, confidence: 0, engine_version: 'eng,"quoted"' } },
  ]);
  // engine_version with a comma + quotes must be wrapped and the quotes doubled
  assert.match(csv, /"eng,""quoted"""/);
});
