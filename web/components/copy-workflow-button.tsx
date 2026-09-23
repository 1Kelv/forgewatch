"use client";

import { useState } from "react";

export function CopyWorkflowButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button className="button primary compact" type="button" onClick={() => void copy()}>
      {copied ? "Copied" : "Copy workflow"}
    </button>
  );
}
