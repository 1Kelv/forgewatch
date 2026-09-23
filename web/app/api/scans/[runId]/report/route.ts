import { unzipSync } from "fflate";

import { automationToken, downloadReport } from "@/lib/github";
import { errorResponse } from "@/lib/http";
import { monitorOwnsRun } from "@/lib/monitors";
import { requireSession } from "@/lib/session";

export async function GET(
  _request: Request,
  context: { params: Promise<{ runId: string }> },
) {
  try {
    const session = await requireSession();
    const { runId } = await context.params;
    if (!/^\d+$/.test(runId)) throw new Error("The scan run ID is invalid.");
    if (!(await monitorOwnsRun(session.githubUserId, runId))) {
      throw new Error("That scan report is not available to this account.");
    }
    const archive = await downloadReport(Number(runId), await automationToken());
    if (archive.byteLength > 10 * 1024 * 1024) throw new Error("The report archive is unexpectedly large.");
    const files = unzipSync(new Uint8Array(archive), {
      filter: (file) => file.name.endsWith("scan.md") && file.originalSize <= 1024 * 1024,
    });
    const entry = Object.entries(files).find(([name]) => name.endsWith("scan.md"));
    if (!entry) throw new Error("The scan report does not contain scan.md.");
    return Response.json({ report: new TextDecoder().decode(entry[1]) });
  } catch (error) {
    return errorResponse(error);
  }
}
