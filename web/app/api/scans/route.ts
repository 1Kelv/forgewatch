import { z } from "zod";

import {
  automationToken,
  dispatchScan,
  findAvailableRepository,
  getWorkflowRun,
  resolveCommit,
} from "@/lib/github";
import { errorResponse, requireSameOrigin } from "@/lib/http";
import { listMonitors, saveMonitor } from "@/lib/monitors";
import { FREQUENCIES, parseGitHubRepository, validateBranch } from "@/lib/repository";
import { requireSession } from "@/lib/session";

const requestSchema = z.object({
  repository: z.string().min(1).max(300),
  branch: z.string().max(255).optional().default(""),
  frequency: z.enum(FREQUENCIES),
});

export async function GET() {
  try {
    const session = await requireSession();
    const monitors = await listMonitors(session.githubUserId);
    const token = monitors.some((item) => item.lastRunId) ? await automationToken() : null;
    const values = await Promise.all(
      monitors.map(async (monitor) => {
        if (!monitor.lastRunId || !token) return { ...monitor, run: null };
        try {
          const run = await getWorkflowRun(Number(monitor.lastRunId), token);
          return {
            ...monitor,
            run: {
              status: run.status,
              conclusion: run.conclusion,
              url: run.html_url,
              createdAt: run.created_at,
              updatedAt: run.updated_at,
            },
          };
        } catch (error) {
          return {
            ...monitor,
            run: null,
            lastError: error instanceof Error ? error.message : "The scan status is unavailable.",
          };
        }
      }),
    );
    return Response.json({ monitors: values });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request: Request) {
  try {
    requireSameOrigin(request);
    const session = await requireSession();
    const input = requestSchema.parse(await request.json());
    const fullName = parseGitHubRepository(input.repository);
    const repository = await findAvailableRepository(session.accessToken, fullName);
    const branch = validateBranch(input.branch || repository.defaultBranch);
    const commit = await resolveCommit(repository.fullName, branch, session.accessToken);
    const run = await dispatchScan({ repository, branch, commit, trigger: "manual" });
    await saveMonitor({
      githubUserId: session.githubUserId,
      repository,
      branch,
      frequency: input.frequency,
      runId: run.runId,
      runUrl: run.runUrl,
    });
    return Response.json(
      {
        message: `${repository.fullName} was queued for scanning.`,
        run: { id: run.runId, url: run.runUrl },
      },
      { status: 202 },
    );
  } catch (error) {
    return errorResponse(error);
  }
}
