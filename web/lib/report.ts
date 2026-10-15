export const priorities = {
  critical: "Urgent", high: "Important", medium: "Needs attention", low: "Lower priority", info: "For awareness",
} as const;
export type Severity = keyof typeof priorities;
export type ReportFinding = {
  id: string; title: string; severity: Severity; where: string; sourceUrl: string | null;
  why: string; action: string; validation: string; steps: string[]; basis: string[];
  commands: string[]; directory: string; disclaimer: string; rule: string; evidence: string; references: string[];
};
export type ScanReport = {
  repository: string; branch: string; commit: string; status: string; headline: string; summary: string;
  nextStep: string; findings: ReportFinding[];
  checks: { name: string; result: string; coverage: string; reason: string; technical: string }[];
  closing: { text: string; steps: string[] };
};

const checkNames: Record<string, string> = { semgrep: "Code safety checks", osv: "Dependency version checks", "osv-scanner": "Dependency version checks", gitleaks: "Exposed secret checks" };
const checkResults: Record<string, string> = { passed: "Finished, with no matching problem", findings: "Finished and found items to review", not_applicable: "No supported files for this check", failed: "Could not finish", skipped: "Did not run" };
const record = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const string = (value: unknown, fallback = ""): string => typeof value === "string" ? value.slice(0, 6000) : fallback;
const list = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string").slice(0, 30).map((item) => item.slice(0, 3000)) : [];

export function safeReportLink(value: string): string | null {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

function sourceLink(repository: string, commit: string, path: string, line: number): string | null {
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository) || !/^[a-f\d]{40,64}$/i.test(commit)) return null;
  if (!path || path.startsWith("/") || path.includes("\\") || path.split("/").some((part) => !part || part === ".." || part === ".")) return null;
  return `https://github.com/${repository}/blob/${commit}/${path.split("/").map(encodeURIComponent).join("/")}#L${line}`;
}

export function normaliseReport(value: unknown, expectedRepository: string): ScanReport | null {
  const scan = record(value);
  if (!Array.isArray(scan.findings) || !Array.isArray(scan.scanner_runs) || scan.findings.length > 5000) return null;
  const simple = record(scan.plain_language);
  const plainFindings = record(simple.findings);
  const plainChecks = Array.isArray(simple.checks) ? simple.checks.map(record) : [];
  const commit = string(scan.commit_sha);
  const hasUnfinishedCheck = !scan.scanner_runs.length || scan.scanner_runs.some((run) => !["passed", "findings", "not_applicable"].includes(string(record(run).status)));
  const status = hasUnfinishedCheck || !["clean", "findings"].includes(string(scan.status)) ? "incomplete" : scan.findings.length ? "findings" : "clean";
  const nextStep = string(simple.next_step, status === "incomplete" ? "One or more checks did not finish. This is not an all-clear; fix the unfinished check and scan again." : status === "findings" ? "Review urgent and important items first, then test your changes and scan again." : "No supported problem was found. This is not a guarantee that the repository has no security issues.");
  const findings = scan.findings.map((value, index): ReportFinding => {
    const item = record(value);
    const plain = record(plainFindings[string(item.fingerprint)]);
    const guidance = record(item.fix_guidance || plain.fix_guidance);
    const location = record(Array.isArray(item.locations) ? item.locations[0] : null);
    const path = string(location.path);
    const line = typeof location.start_line === "number" && Number.isSafeInteger(location.start_line) && location.start_line > 0 ? location.start_line : 1;
    const severity = Object.hasOwn(priorities, string(item.severity)) ? string(item.severity) as Severity : "medium";
    return {
      id: `${string(item.fingerprint, "finding")}-${index}`, title: string(plain.title, string(item.title, "Item to review")), severity,
      where: string(plain.where, path ? `${path}, line ${line}` : "Location not available"), sourceUrl: sourceLink(expectedRepository, commit, path, line),
      why: string(plain.why_it_matters, string(item.explanation)), action: string(plain.what_to_do, string(item.remediation)),
      validation: string(plain.fix_check, "Not tested yet"), steps: list(guidance.steps), basis: list(guidance.basis),
      commands: list(guidance.commands), directory: string(guidance.working_directory, "."),
      disclaimer: string(guidance.disclaimer, "Suggested advice, not an applied or tested fix. Check compatibility and scan again after changes."),
      rule: string(item.rule_id), evidence: string(item.evidence), references: list(item.references).map(safeReportLink).filter((url): url is string => url !== null),
    };
  }).sort((a, b) => Object.keys(priorities).indexOf(a.severity) - Object.keys(priorities).indexOf(b.severity));
  const closing = record(simple.closing_summary);
  return {
    repository: expectedRepository, branch: string(scan.ref), commit, status,
    headline: status === "incomplete" ? "The scan could not finish" : status === "findings" ? "Items need your review" : "No supported problems found",
    summary: string(simple.summary, `${findings.length} ${findings.length === 1 ? "item" : "items"} recorded for review.`), nextStep, findings,
    checks: scan.scanner_runs.slice(0, 20).map((value, index) => {
      const run = record(value), plain = plainChecks[index] || {};
      const scanner = string(run.scanner), result = string(run.status);
      return { name: checkNames[scanner] || scanner, result: checkResults[result] || "Could not finish", coverage: string(plain.coverage, string(run.coverage)), reason: string(plain.reason, run.error ? "This check could not finish. Open the technical message below for the recorded reason." : ""), technical: string(run.error) };
    }),
    closing: { text: string(closing.text, nextStep), steps: list(closing.steps).length ? list(closing.steps) : [
      ...(status === "incomplete" ? ["Resolve the unfinished checks; this scan is not an all-clear."] : []),
      ...(findings.length ? ["Work through the highest-priority items first.", "Review each suggested fix, run the project's checks, and scan again."] : []),
      "Keep scanning when code or dependencies change. No automated scan can guarantee complete security.",
    ] },
  };
}
