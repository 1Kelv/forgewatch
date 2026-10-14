"use client";

import { useState } from "react";

export function CopyWorkflowButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);

  async function copy() {
    setError(false);
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError(true);
    }
  }

  return (
    <div className="copyWorkflowControl">
      <button className="button primary compact" type="button" onClick={() => void copy()}>
        {copied ? "Copied" : "Copy workflow"}
      </button>
      <span className="copyFeedback" role="status">{error ? "Copy did not work. Select and copy the file text below." : copied ? "Ready to paste into GitHub." : ""}</span>
    </div>
  );
}
