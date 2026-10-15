import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { runInNewContext } from "node:vm";

import { normaliseReport, safeReportLink } from "../lib/report";
import { ReportView } from "../components/report-view";
import { LegacyReport } from "../components/legacy-report";
import { themeBootstrap } from "../lib/theme";

const scan = () => ({
  status: "findings", ref: "main", commit_sha: "a".repeat(40),
  scanner_runs: [{ scanner: "osv-scanner", status: "findings", coverage: "1 lockfile" }],
  findings: [{ fingerprint: "one", severity: "high", title: "Update a package", rule_id: "GHSA-example", locations: [{ path: "app/package-lock.json", start_line: 1 }], remediation: "Update compatibly", references: ["javascript:alert(1)", "https://example.com/advisory"], fix_guidance: { steps: ["Edit app/package.json", "Run the checks"], commands: ["npm run test"], basis: ["Declared in devDependencies"], working_directory: "app" } }],
});

test("old scan.json reports get readable checks, priorities, and a closing summary", () => {
  const report = normaliseReport(scan(), "owner/repo")!;
  assert.equal(report.headline, "Items need your review");
  assert.equal(report.checks[0].name, "Dependency version checks");
  assert.equal(report.findings[0].severity, "high");
  assert.equal(report.findings[0].sourceUrl, `https://github.com/owner/repo/blob/${"a".repeat(40)}/app/package-lock.json#L1`);
  assert.deepEqual(report.findings[0].references, ["https://example.com/advisory"]);
  assert.ok(report.closing.steps.length);
});

test("failed checks never appear as a clean scan", () => {
  const value = { ...scan(), status: "clean", findings: [], scanner_runs: [{ scanner: "osv", status: "failed", error: "Unavailable" }] };
  const report = normaliseReport(value, "owner/repo")!;
  assert.equal(report.status, "incomplete");
  assert.match(report.nextStep, /not an all-clear/);
  assert.match(report.checks[0].reason, /could not finish/);
});

test("untrusted report values are escaped and unsafe links and paths are rejected", () => {
  const value = scan();
  value.findings[0].title = '<img src=x onerror="alert(1)">';
  value.findings[0].locations[0].path = "../private.txt";
  const report = normaliseReport(value, "owner/repo")!;
  assert.equal(report.findings[0].sourceUrl, null);
  const html = renderToStaticMarkup(createElement(ReportView, { report }));
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;img"));
  for (const url of ["javascript:alert(1)", "data:text/html,bad", "https://user:password@example.com"]) assert.equal(safeReportLink(url), null);
});

test("large reports initially show ten collapsed findings and retain the full summary", () => {
  const value = scan();
  value.findings = Array.from({ length: 37 }, (_, index) => ({ ...scan().findings[0], fingerprint: String(index) }));
  const report = normaliseReport(value, "owner/repo")!;
  const html = renderToStaticMarkup(createElement(ReportView, { report }));
  assert.equal((html.match(/class="finding"/g) || []).length, 10);
  assert.ok(!html.includes('<details class="finding" open'));
  assert.match(html, /Showing 10 of 37 matching items/);
  assert.match(html, /Summary and next steps/);
  assert.match(html, /How to fix it/);
  assert.match(html, /npm run test/);
});

test("Markdown-only artifacts have readable headings, bold text and lists, without HTML execution", () => {
  const html = renderToStaticMarkup(createElement(LegacyReport, { text: "# Report\n\n- **Important:** update it\n- Run tests\n\n<script>alert(1)</script>" }));
  assert.match(html, /<h3>Report<\/h3>/);
  assert.match(html, /<strong>Important:<\/strong>/);
  assert.match(html, /<ul>/);
  assert.ok(!html.includes("<script>"));
});

test("theme starts with saved preference, or system preference if storage is unavailable", () => {
  for (const [stored, system, expected] of [["light", true, "light"], ["dark", false, "dark"], [null, true, "dark"], ["invalid", false, "light"]] as const) {
    const document = { documentElement: { dataset: { theme: "" } } };
    runInNewContext(themeBootstrap, { document, localStorage: { getItem: () => stored }, matchMedia: () => ({ matches: system }) });
    assert.equal(document.documentElement.dataset.theme, expected);
  }
  const document = { documentElement: { dataset: { theme: "" } } };
  runInNewContext(themeBootstrap, { document, localStorage: { getItem: () => { throw new Error("Disabled"); } }, matchMedia: () => ({ matches: true }) });
  assert.equal(document.documentElement.dataset.theme, "dark");
});

test("malformed and excessive structured reports fall back safely", () => {
  assert.equal(normaliseReport(null, "owner/repo"), null);
  assert.equal(normaliseReport({ findings: [], scanner_runs: "wrong" }, "owner/repo"), null);
  assert.equal(normaliseReport({ ...scan(), findings: Array(5001).fill({}) }, "owner/repo"), null);
});
