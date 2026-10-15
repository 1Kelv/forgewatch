import { unzipSync } from "fflate";

import { automationToken, createInstallationToken, downloadReport } from "@/lib/github";
import { errorResponse } from "@/lib/http";
import { monitorForRun, runRepositoryFullName } from "@/lib/monitors";
import { requireSession } from "@/lib/session";
import { normaliseReport } from "@/lib/report";

export async function GET(
  _request: Request,
  context: { params: Promise<{ runId: string }> },
) {
  try {
    const session = await requireSession();
    const { runId } = await context.params;
    if (!/^\d+$/.test(runId)) throw new Error("The scan run ID is invalid.");
    const monitor = await monitorForRun(session.githubUserId, runId);
    if (!monitor) {
      throw new Error("That scan report is not available to this account.");
    }
    const runRepository = runRepositoryFullName(monitor);
    const token = runRepository.toLowerCase() === monitor.repositoryFullName.toLowerCase()
      ? await createInstallationToken(
        Number(monitor.installationId),
        [Number(monitor.repositoryId)],
        { actions: "read", metadata: "read" },
      )
      : await automationToken();
    const archive = await downloadReport(runRepository, Number(runId), token);
    if (archive.byteLength > 10 * 1024 * 1024) throw new Error("The report archive is unexpectedly large.");
    const accepted = new Set<string>();
    const files = unzipSync(new Uint8Array(archive), {
      filter: (file) => {
        const name = file.name.split("/").at(-1) || "";
        const limit = name === "scan.json" ? 6 * 1024 * 1024 : name === "scan.md" ? 2 * 1024 * 1024 : 0;
        if (!limit || file.originalSize > limit || accepted.has(name)) return false;
        accepted.add(name);
        return true;
      },
    });
    const entry = Object.entries(files).find(([name]) => name.split("/").at(-1) === "scan.md");
    if (!entry) throw new Error("The scan report does not contain scan.md.");
    const structured = Object.entries(files).find(([name]) => name.split("/").at(-1) === "scan.json");
    let scan = null;
    if (structured) {
      try { scan = normaliseReport(JSON.parse(new TextDecoder().decode(structured[1])), monitor.repositoryFullName); }
      catch { /* Older artifacts can still use the text-only, escaped Markdown fallback. */ }
    }
    const body = JSON.stringify({ report: new TextDecoder().decode(entry[1]), scan });
    if (new TextEncoder().encode(body).byteLength > 4 * 1024 * 1024) {
      throw new Error("This report is too large to display here. Open the scan in GitHub and download its report artifact instead.");
    }
    return new Response(body, { headers: { "Content-Type": "application/json", "Cache-Control": "private, no-store" } });
  } catch (error) {
    return errorResponse(error);
  }
}
