"use client";

import { useEffect, useRef } from "react";
import { LegacyReport } from "@/components/legacy-report";
import { ReportView } from "@/components/report-view";
import { ThemeToggle } from "@/components/theme-toggle";
import type { ScanReport } from "@/lib/report";

export type OpenReport = { name: string; text: string; scan: ScanReport | null };

export function ReportDialog({ report, onClose }: { report: OpenReport; onClose: () => void }) {
  const panel = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    close.current?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key !== "Tab") return;
      const elements = Array.from(panel.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), input, select, summary, [tabindex="0"]') || []).filter((element) => element.getClientRects().length > 0);
      const first = elements[0], last = elements.at(-1);
      if (!elements.includes(document.activeElement as HTMLElement)) { event.preventDefault(); (event.shiftKey ? last : first)?.focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    document.addEventListener("keydown", keyboard);
    return () => { document.body.style.overflow = overflow; document.removeEventListener("keydown", keyboard); previous?.focus(); };
  }, [onClose]);

  function download() {
    const url = URL.createObjectURL(new Blob([report.text], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${report.name.replace(/[^\w.-]/g, "-")}-security-report.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="modalBackdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={panel} className="reportModal" role="dialog" aria-modal="true" aria-labelledby="report-title">
      <div className="reportHeader"><div><p className="step">Latest report</p><h2 id="report-title">{report.name}</h2></div><div className="reportActions"><ThemeToggle /><button className="button secondary compact" onClick={download}>Download report</button><button ref={close} className="button secondary compact" onClick={onClose}>Close</button></div></div>
      {report.scan ? <ReportView report={report.scan} /> : <LegacyReport text={report.text} />}
    </section>
  </div>;
}
