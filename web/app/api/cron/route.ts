import { timingSafeEqual } from "node:crypto";

import {
  createInstallationToken,
  dispatchScan,
  resolveCommit,
  type AvailableRepository,
} from "@/lib/github";
import {
  claimDueMonitors,
  recordScheduledRun,
  recordScheduleError,
} from "@/lib/monitors";

function authorized(request: Request): boolean {
  const expected = process.env.CRON_SECRET?.trim() || "";
  const received = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "") || "";
  if (!expected || received.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(received), Buffer.from(expected));
}

export async function GET(request: Request) {
  if (!authorized(request)) return Response.json({ error: "Not authorized." }, { status: 401 });
  const monitors = await claimDueMonitors();
  const results = await Promise.all(
    monitors.map(async (monitor) => {
      try {
        const repository: AvailableRepository = {
          id: Number(monitor.repositoryId),
          installationId: Number(monitor.installationId),
          fullName: monitor.repositoryFullName,
          private: true,
          defaultBranch: monitor.defaultBranch,
          url: `https://github.com/${monitor.repositoryFullName}`,
          ownerAvatarUrl: "",
        };
        const targetToken = await createInstallationToken(
          repository.installationId,
          [repository.id],
          { contents: "read", metadata: "read" },
        );
        const commit = await resolveCommit(repository.fullName, monitor.scanBranch, targetToken);
        const run = await dispatchScan({
          repository,
          branch: monitor.scanBranch,
          commit,
          trigger: "schedule",
        });
        await recordScheduledRun(monitor, run.runId, run.runUrl);
        return { repository: repository.fullName, queued: true, runId: run.runId };
      } catch (error) {
        const message = error instanceof Error ? error.message : "The scheduled scan could not start.";
        await recordScheduleError(monitor, message);
        return { repository: monitor.repositoryFullName, queued: false, error: message };
      }
    }),
  );
  return Response.json({ checked: monitors.length, results });
}
