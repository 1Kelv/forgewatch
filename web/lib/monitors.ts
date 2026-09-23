import { db } from "@/lib/db";
import { type AvailableRepository } from "@/lib/github";
import { type Frequency, nextScanAt } from "@/lib/repository";

export type Monitor = {
  githubUserId: string;
  installationId: string;
  repositoryId: string;
  repositoryFullName: string;
  defaultBranch: string;
  scanBranch: string;
  frequency: Frequency;
  nextScanAt: string | null;
  lastRunId: string | null;
  lastRunUrl: string | null;
  lastStartedAt: string | null;
  lastError: string | null;
};

function monitor(row: Record<string, unknown>): Monitor {
  const date = (value: unknown) => (value instanceof Date ? value.toISOString() : value ? String(value) : null);
  return {
    githubUserId: String(row.github_user_id),
    installationId: String(row.installation_id),
    repositoryId: String(row.repository_id),
    repositoryFullName: String(row.repository_full_name),
    defaultBranch: String(row.default_branch),
    scanBranch: String(row.scan_branch),
    frequency: String(row.frequency) as Frequency,
    nextScanAt: date(row.next_scan_at),
    lastRunId: row.last_run_id ? String(row.last_run_id) : null,
    lastRunUrl: row.last_run_url ? String(row.last_run_url) : null,
    lastStartedAt: date(row.last_started_at),
    lastError: row.last_error ? String(row.last_error) : null,
  };
}

export async function listMonitors(githubUserId: number): Promise<Monitor[]> {
  const rows = await db()`
    SELECT * FROM forgewatch_monitors
    WHERE github_user_id = ${githubUserId}
    ORDER BY repository_full_name
  `;
  return rows.map((row) => monitor(row));
}

export async function saveMonitor(input: {
  githubUserId: number;
  repository: AvailableRepository;
  branch: string;
  frequency: Frequency;
  runId: number;
  runUrl: string;
}): Promise<void> {
  const next = nextScanAt(input.frequency);
  await db()`
    INSERT INTO forgewatch_monitors (
      github_user_id, installation_id, repository_id, repository_full_name,
      default_branch, scan_branch, frequency, next_scan_at, last_run_id, last_run_url,
      last_started_at, last_error, updated_at
    ) VALUES (
      ${input.githubUserId}, ${input.repository.installationId}, ${input.repository.id},
      ${input.repository.fullName}, ${input.repository.defaultBranch}, ${input.branch},
      ${input.frequency}, ${next},
      ${input.runId}, ${input.runUrl}, NOW(), NULL, NOW()
    )
    ON CONFLICT (github_user_id, repository_id) DO UPDATE SET
      installation_id = EXCLUDED.installation_id,
      repository_full_name = EXCLUDED.repository_full_name,
      default_branch = EXCLUDED.default_branch,
      scan_branch = EXCLUDED.scan_branch,
      frequency = EXCLUDED.frequency,
      next_scan_at = EXCLUDED.next_scan_at,
      last_run_id = EXCLUDED.last_run_id,
      last_run_url = EXCLUDED.last_run_url,
      last_started_at = EXCLUDED.last_started_at,
      last_error = NULL,
      updated_at = NOW()
  `;
}

export async function updateFrequency(
  githubUserId: number,
  repositoryId: string,
  frequency: Frequency,
): Promise<Monitor> {
  const next = nextScanAt(frequency);
  const rows = await db()`
    UPDATE forgewatch_monitors
    SET frequency = ${frequency}, next_scan_at = ${next}, updated_at = NOW()
    WHERE github_user_id = ${githubUserId} AND repository_id = ${repositoryId}
    RETURNING *
  `;
  if (!rows[0]) throw new Error("That monitored repository was not found.");
  return monitor(rows[0]);
}

export async function removeMonitor(githubUserId: number, repositoryId: string): Promise<void> {
  const rows = await db()`
    DELETE FROM forgewatch_monitors
    WHERE github_user_id = ${githubUserId} AND repository_id = ${repositoryId}
    RETURNING repository_id
  `;
  if (!rows[0]) throw new Error("That monitored repository was not found.");
}

export async function monitorForRun(githubUserId: number, runId: string): Promise<Monitor | null> {
  const rows = await db()`
    SELECT * FROM forgewatch_monitors
    WHERE github_user_id = ${githubUserId} AND last_run_id = ${runId}
    LIMIT 1
  `;
  return rows[0] ? monitor(rows[0]) : null;
}

export function runRepositoryFullName(
  value: Pick<Monitor, "lastRunUrl" | "repositoryFullName">,
): string {
  if (!value.lastRunUrl) return value.repositoryFullName;
  try {
    const url = new URL(value.lastRunUrl);
    const parts = url.pathname.split("/").filter(Boolean);
    if (url.hostname === "github.com" && parts.length >= 5 && parts[2] === "actions") {
      return `${parts[0]}/${parts[1]}`;
    }
  } catch {
    // Fall back to the monitored repository when an old URL cannot be parsed.
  }
  return value.repositoryFullName;
}

export async function claimDueMonitors(): Promise<Monitor[]> {
  const rows = await db()`
    WITH due AS (
      SELECT github_user_id, repository_id
      FROM forgewatch_monitors
      WHERE next_scan_at IS NOT NULL AND next_scan_at <= NOW()
      ORDER BY next_scan_at
      FOR UPDATE SKIP LOCKED
      LIMIT 20
    )
    UPDATE forgewatch_monitors AS monitor
    SET
      next_scan_at = CASE monitor.frequency
        WHEN 'daily' THEN
          (date_trunc('day', NOW() AT TIME ZONE 'UTC') + INTERVAL '1 day 3 hours 17 minutes') AT TIME ZONE 'UTC'
        WHEN 'weekly' THEN
          (date_trunc('day', NOW() AT TIME ZONE 'UTC') + INTERVAL '7 days 3 hours 17 minutes') AT TIME ZONE 'UTC'
        ELSE NULL
      END,
      updated_at = NOW()
    FROM due
    WHERE monitor.github_user_id = due.github_user_id
      AND monitor.repository_id = due.repository_id
    RETURNING monitor.*
  `;
  return rows.map((row) => monitor(row));
}

export async function recordScheduledRun(monitorValue: Monitor, runId: number, runUrl: string) {
  await db()`
    UPDATE forgewatch_monitors
    SET last_run_id = ${runId}, last_run_url = ${runUrl}, last_started_at = NOW(),
        last_error = NULL, updated_at = NOW()
    WHERE github_user_id = ${monitorValue.githubUserId}
      AND repository_id = ${monitorValue.repositoryId}
  `;
}

export async function recordScheduleError(monitorValue: Monitor, message: string) {
  await db()`
    UPDATE forgewatch_monitors
    SET last_error = ${message.slice(0, 500)}, next_scan_at = NOW() + INTERVAL '15 minutes',
        updated_at = NOW()
    WHERE github_user_id = ${monitorValue.githubUserId}
      AND repository_id = ${monitorValue.repositoryId}
  `;
}
