CREATE TABLE IF NOT EXISTS forgewatch_monitors (
  github_user_id BIGINT NOT NULL,
  installation_id BIGINT NOT NULL,
  repository_id BIGINT NOT NULL,
  repository_full_name TEXT NOT NULL,
  default_branch TEXT NOT NULL,
  scan_branch TEXT NOT NULL,
  frequency TEXT NOT NULL CHECK (frequency IN ('manual', 'daily', 'weekly')),
  next_scan_at TIMESTAMPTZ,
  last_run_id BIGINT,
  last_run_url TEXT,
  last_started_at TIMESTAMPTZ,
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (github_user_id, repository_id)
);

CREATE INDEX IF NOT EXISTS forgewatch_monitors_due
  ON forgewatch_monitors (next_scan_at)
  WHERE next_scan_at IS NOT NULL;
