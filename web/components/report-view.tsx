"use client";

import { useState } from "react";
import { priorities, type ScanReport } from "@/lib/report";

export function ReportView({ report }: { report: ScanReport }) {
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState("all");
  const [visible, setVisible] = useState(10);
  const findings = report.findings.filter((item) => (priority === "all" || item.severity === priority) && `${item.title} ${item.where} ${item.rule}`.toLowerCase().includes(query.toLowerCase()));
  const counts = Object.entries(priorities).map(([key, label]) => ({ key, label, count: report.findings.filter((item) => item.severity === key).length }));
  return (
    <div className="reportBody">
      <section className={`reportOverview ${report.status === "incomplete" ? "unfinished" : ""}`} aria-labelledby="report-overview">
        <p className="step">At a glance</p>
        <h3 id="report-overview">{report.headline}</h3>
        <p>{report.summary}</p>
        <p className="reportNext"><strong>Start here:</strong> {report.nextStep}</p>
        <div className="priorityCounts" aria-label="Items by priority">
          {counts.filter((item) => item.count).map((item) => <span className={`priorityPill ${item.key}`} key={item.key}><strong>{item.count}</strong> {item.label}</span>)}
          {!report.findings.length && <span className="priorityPill info">0 items recorded</span>}
        </div>
        <p className="snapshot">Branch: <strong>{report.branch || "Not recorded"}</strong> <span>Version: <code title={report.commit}>{report.commit.slice(0, 12) || "Not recorded"}</code></span></p>
      </section>

      <section className="reportSection" aria-labelledby="report-checks">
        <h3 id="report-checks">What was checked</h3>
        <ul className="reportChecks">{report.checks.map((check, index) => <li key={index}>
          <strong>{check.name}</strong><span>{check.result}</span><small>{check.coverage}</small>
          {check.reason && <p className="inlineError">{check.reason}</p>}
          {check.technical && <details className="technicalDetails"><summary>Technical failure message</summary><pre>{check.technical}</pre></details>}
        </li>)}</ul>
      </section>

      <section className="reportSection" aria-labelledby="report-items">
        <div className="reportSectionHeading"><h3 id="report-items">Items to review <span>({report.findings.length})</span></h3><a className="textLink" href="#report-summary">Skip to summary</a></div>
        {report.findings.length > 0 ? <>
          <p className="reportHint">Highest priorities come first. Open an item for its explanation and suggested fix.</p>
          <div className="reportFilters">
            <label>Find an item<input type="search" placeholder="Search package, file, or issue" value={query} onChange={(event) => { setQuery(event.target.value); setVisible(10); }} /></label>
            <label>Priority<select value={priority} onChange={(event) => { setPriority(event.target.value); setVisible(10); }}><option value="all">All priorities</option>{Object.entries(priorities).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
          </div>
          <p className="reportHint" role="status">Showing {Math.min(visible, findings.length)} of {findings.length} matching items</p>
          <div className="findingList">{findings.slice(0, visible).map((item) => <details className="finding" key={item.id}>
            <summary><span className={`priorityPill ${item.severity}`}>{priorities[item.severity]}</span><span className="findingHeading"><strong>{item.title}</strong><small>{item.where}</small></span><span className="findingExpand" aria-hidden="true">+</span></summary>
            <div className="findingBody">
              {item.sourceUrl && <a className="textLink" href={item.sourceUrl} target="_blank" rel="noreferrer">Open the affected file in GitHub</a>}
              <h4>Why this matters</h4><p>{item.why}</p>
              <h4>How to fix it</h4>
              {item.steps.length ? <ol className="fixSteps">{item.steps.map((step, index) => <li key={index}>{step}</li>)}</ol> : <><p>{item.action}</p><p className="reportHint">Run a new scan to include project-specific steps in this older report.</p></>}
              {item.commands.length > 0 && <div className="suggestedCommands"><h4>Commands to review and run yourself</h4><p>From <code>{item.directory}</code>, in a trusted development environment:</p><pre>{item.commands.join("\n")}</pre><p className="reportHint">These commands may run project scripts. Forgewatch has not run them or tested this fix.</p></div>}
              <p className="guidanceDisclaimer">{item.disclaimer}</p>
              {item.basis.length > 0 && <details className="technicalDetails"><summary>Why this advice fits this project</summary><ul>{item.basis.map((basis, index) => <li key={index}>{basis}</li>)}</ul></details>}
              <details className="technicalDetails"><summary>Technical details and advisory links</summary><p><strong>Rule or advisory:</strong> {item.rule}</p><p><strong>Fix validation:</strong> {item.validation}</p>{item.evidence && <pre>{item.evidence}</pre>}{item.references.length > 0 && <ul>{item.references.map((url) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul>}</details>
            </div>
          </details>)}</div>
          {!findings.length && <p className="reportHint">No items match. Try a different search or priority.</p>}
          {visible < findings.length && <button className="button secondary compact showMore" onClick={() => setVisible((count) => count + 10)}>Show 10 more items</button>}
        </> : <p>{report.status === "incomplete" ? "No items were recorded, but some checks did not finish. Do not treat this as an all-clear." : "The completed checks found no supported problem. Other kinds of issues may still exist."}</p>}
      </section>
      <section className="closingSummary" id="report-summary" tabIndex={-1} aria-labelledby="closing-heading"><p className="step">The bottom line</p><h3 id="closing-heading">Summary and next steps</h3><p>{report.closing.text}</p><ul>{report.closing.steps.map((step, index) => <li key={index}>{step}</li>)}</ul></section>
    </div>
  );
}
