import { Fragment, type ReactNode } from "react";

// A deliberately small, text-only Markdown fallback. Never interpret report HTML.
function inline(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, index) => part.startsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong> : part.startsWith("`") ? <code key={index}>{part.slice(1, -1)}</code> : <Fragment key={index}>{part}</Fragment>);
}

export function LegacyReport({ text }: { text: string }) {
  const blocks = text.split(/\n\s*\n/).filter(Boolean);
  return <div className="reportBody legacyReport"><p className="reportHint">This older report has no readable structured data. A new scan will include the latest report layout and fix guidance.</p>{blocks.map((block, index) => {
    const lines = block.split("\n").filter((line) => !/^<\/?(?:details|summary)>/.test(line.trim()));
    if (!lines.length) return null;
    const content = lines.join("\n");
    if (/^#{1,6} /.test(content)) return <h3 key={index}>{inline(content.replace(/^#{1,6} /, ""))}</h3>;
    if (lines.every((line) => /^[-*] /.test(line))) return <ul key={index}>{lines.map((line, number) => <li key={number}>{inline(line.slice(2))}</li>)}</ul>;
    if (lines.every((line) => /^\d+\. /.test(line))) return <ol key={index}>{lines.map((line, number) => <li key={number}>{inline(line.replace(/^\d+\. /, ""))}</li>)}</ol>;
    if (lines.length > 1 && lines.every((line) => line.startsWith("|"))) return <div className="legacyTable" key={index}><table><tbody>{lines.filter((line) => !/^\|[-| :]+\|$/.test(line)).map((line, number) => <tr key={number}>{line.split("|").slice(1, -1).map((cell, column) => number === 0 ? <th key={column}>{inline(cell.trim())}</th> : <td key={column}>{inline(cell.trim())}</td>)}</tr>)}</tbody></table></div>;
    return <p key={index}>{inline(content.replace(/^>\s?/, ""))}</p>;
  })}</div>;
}
