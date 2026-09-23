# Operations, scheduling and costs

## Scan lifecycle

The legacy central workflow supports:

- `workflow_dispatch` for manual scans.
- `repository_dispatch` for signed GitHub push and pull-request events.
- No automatic timer. Hosted schedules are dispatched by the Vercel cron into each selected target.

Hosted dashboard scans use `.github/workflows/reusable-scan.yml` through a small caller workflow committed to each target. The run, logs, cache, artifact storage, and Actions usage belong to the target repository. The dashboard's Vercel cron dispatches due daily and weekly scans; it does not perform the scan itself.

Completed scans with findings upload their reports and finish with a workflow warning. Only an incomplete scan or operational failure makes the workflow red. This keeps “problems were found” separate from “the scanner did not work.”

Each run checks out Forgewatch and the exact target revision separately. Scanner releases and third-party Actions are pinned. Downloaded OSV-Scanner and Gitleaks binaries are checked against their published SHA-256 checksum files. Reports and candidate patches are retained as workflow artifacts for 30 days in the target repository.

The local dashboard offers manual, six-hourly, daily, and weekly schedules. Those schedules are deliberately local and run only while `forgewatch dashboard` remains open. Repository selection and next-run times are stored in `.forgewatch/dashboard.json`.

SQLite state is restored and saved through the Actions cache. This is adequate for a one-repository MVP but is not a durable multi-worker database. Back up the database and move to a managed transactional database before commercial or high-concurrency operation.

## Reporting and triage

Inspect `scan.md` first. It is the plain-English report intended for developers at any experience level. Raw scanner names, advisory IDs and original messages are kept under a collapsed technical-details section so they do not obscure the action to take. Retain `scan.json` for automation; it also contains a `plain_language` summary. A status means:

- `clean`: every configured scanner completed and no supported finding was detected.
- `findings`: every configured scanner completed and one or more supported findings were detected.
- `incomplete`: at least one configured scanner failed, was disabled, or unexpectedly skipped. A check with no supported file type is labelled not applicable instead. Never describe an incomplete result as clean.

Prioritise critical and high findings, then confidence, production reachability and exposure. A dependency advisory in a build-only package may have lower practical exploitability than its upstream severity, but it should be dismissed only with a recorded, reviewable reason.

## Cost controls

The scanner CLIs selected for the MVP have no per-scan fee under the linked licences. Operating costs to monitor are:

- GitHub Actions minutes, cache storage and 30-day report artifacts in each target repository. GitHub provides plan-dependent quotas and bills overages to the target owner's account or organisation. Review the [current GitHub Actions billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions) rather than hard-coding an estimate.
- Compute and HTTPS hosting for the webhook dispatcher if it is not colocated with existing internal infrastructure.
- Container registry and retained log or database storage.
- OpenAI API input and output tokens when `--ai` is used. The example uses `gpt-5.6-terra`, one request and at most 6,000 output tokens per fix. Check the [current OpenAI model pricing](https://developers.openai.com/api/docs/models) before enabling it.
- Engineering time for triage, scanner upgrades, custom rule maintenance, false-positive review and dependency upgrade testing.

Budget guardrails should include GitHub Actions spending limits, alerting on dispatcher error rates, a maximum AI request count and output-token cap, repository allow-lists, job timeouts and artifact retention limits.

## Scanner upgrades

Upgrade one scanner at a time. Verify its licence, release notes, JSON schema and exit codes. Update the version in the workflow, rerun parser fixtures and unit tests, run the deliberately vulnerable fixture, then scan a representative private target. A scanner upgrade that cannot produce a version or parseable output is a failed run.

## Incident handling for a secret finding

Forgewatch never prints the detected value. Use the file and line location to validate through an approved secure channel. If real, revoke or rotate the credential first, then remove it from the current tree and Git history as appropriate. Treat deletion without rotation as insufficient because copies may already exist.
