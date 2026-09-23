# Forgewatch

Forgewatch is a standalone repository security agent. It scans a Git checkout, explains what needs attention in plain English, remembers findings between scans, prepares narrow fixes in disposable workspaces, and can hand a validated patch to a human through a pull request.

Forgewatch never merges, enables auto-merge, deploys, rotates credentials, or changes production infrastructure.

Forgewatch is independent from every repository it scans. It can scan any authorised private or public repository without becoming part of that project's codebase.

## Current status

This repository contains a working local MVP, GitHub Actions automation, and a Vercel-ready hosted dashboard. A new hosted installation needs GitHub App credentials, a PostgreSQL database, and a Vercel deployment.

- The local dashboard can register repositories, run scans, show plain-English reports, and schedule recurring local scans.
- The hosted dashboard under `web/` works on phones, lists repositories approved through the signed-in user's GitHub App installation, and starts a repository-owned workflow.
- Local scanning and the deliberately vulnerable demonstration fixture are working.
- The GitHub Actions test, reusable scan, and target workflow templates are included. Each hosted target runs in its own repository, so its logs, report artifact, and Actions usage stay with its owner.
- GitHub App webhook handling is implemented but is not active until an App, secrets, and an HTTPS host are configured.
- AI patch generation is implemented but has not been called because no API credential was provided.
- Containerised application testing reports `blocked` when Docker is unavailable. It never falls back to running untrusted repository code directly on the host.

## What Forgewatch checks

| Check | Purpose | Current coverage |
|---|---|---|
| Code safety | Finds risky source-code patterns | Two committed JavaScript and TypeScript rules |
| Dependency versions | Finds packages with known public security advisories | Lockfiles and manifests supported by OSV-Scanner |
| Exposed secrets | Finds likely passwords, tokens, and private keys | Current repository files by default |

The underlying tools are Semgrep, OSV-Scanner, and Gitleaks. Human reports use ordinary language first. Tool names, rule IDs, and original advisory wording are kept in collapsed technical sections for maintainers.

Forgewatch does not prove that a repository is secure. A clean result means only that every configured check finished and did not find an issue it currently knows how to detect.

## Safety model

Forgewatch treats repository files, filenames, commit messages, webhook data, scanner output, and AI output as untrusted.

- Scanner processes do not receive GitHub, OpenAI, or approval credentials.
- Secret values are removed from reports.
- Repository test and build commands run only in Docker with no network, dropped capabilities, a read-only container filesystem, and resource limits.
- Each proposed fix is restricted to the files connected to its finding.
- Patches containing common rule-suppression or test-weakening markers are rejected.
- A failed, disabled, or unexpectedly skipped scanner makes the whole scan incomplete, never clean. A check with no applicable file type is reported separately as not applicable.
- GitHub write credentials remain in the controller and are never passed into repository code execution.
- A proposed pull request is rejected if validation is blocked or failed, or if the default branch changed after the patch was prepared.

## Requirements

The versions used in local and CI validation are:

- Python 3.9 or newer. CI uses Python 3.12.
- Semgrep 1.177.0.
- OSV-Scanner 2.5.1.
- Gitleaks 8.30.1.
- Git.
- Docker for target application tests, type checks, and builds.
- GitHub CLI for the repository setup commands in this guide.

Later scanner versions may work, but their output formats and exit codes should be tested before changing the pinned CI versions.

## Fastest way to see it work

The demonstration creates a temporary Git repository containing an intentionally unsafe link. It runs all three real scanners, prepares the supported fix, proves the focused check fails before the fix and passes afterwards, and writes a plain-English report and patch artifact.

```sh
cd /Users/kelvinolasupo/Documents/Codex/forgewatch
. .venv/bin/activate
python scripts/demo.py
```

Expected key results:

```text
scan_status: findings
semgrep: findings
osv-scanner: passed
gitleaks: passed
security_test_before: failed
security_test_after: passed
security_rescan: passed
```

If Docker is not installed, `isolated_validation` will say `blocked`. That is the intended safe behaviour. The report and candidate patch are still written under `.forgewatch/artifacts/demo-fixture/`, but the patch is not eligible for automatic pull-request publication.

There is no `npm run dev` command. Forgewatch is a Python application. Use `forgewatch dashboard` for the local interface. The separate `forgewatch serve` command starts only the GitHub webhook receiver.

## Fresh local installation

Clone Forgewatch, create a virtual environment, and install the package and pinned Semgrep version:

```sh
git clone https://github.com/1Kelv/forgewatch.git
cd forgewatch
python3 -m venv .venv
. .venv/bin/activate
python -m pip install . semgrep==1.177.0
cp forgewatch.example.json forgewatch.json
```

Install OSV-Scanner 2.5.1 and Gitleaks 8.30.1 from their official release pages, then confirm all three commands are available:

```sh
semgrep --version
osv-scanner --version
gitleaks version
```

- [OSV-Scanner releases](https://github.com/google/osv-scanner/releases/tag/v2.5.1)
- [Gitleaks releases](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)

The GitHub Actions workflows download these binaries and verify their published SHA-256 checksums automatically.

## Use the dashboard

Start the interface from the Forgewatch folder:

```sh
cd /Users/kelvinolasupo/Documents/Codex/forgewatch
. .venv/bin/activate
python -m pip install -e .
forgewatch --config "$PWD/forgewatch.json" dashboard
```

The browser opens `http://127.0.0.1:8790`. Keep the terminal window open while using the dashboard.

To scan a repository:

1. Select `Add a repository`.
2. Enter the full folder path of a Git repository already cloned onto the computer.
3. Optionally enter a display name such as `OWNER/REPOSITORY` and its default branch.
4. Choose `Manual only`, `Every 6 hours`, `Every day`, or `Every week`.
5. Select `Add repository`, then `Run scan`.
6. When it finishes, select `View report`.

The dashboard remembers repository choices in `.forgewatch/dashboard.json`. Reports are written under `.forgewatch/artifacts/dashboard/`. Both locations are ignored by Git and remain outside every target repository.

Local recurring scans run only while the dashboard server is open. Hosted daily and weekly choices are kept in the database; Vercel's protected cron endpoint starts the target repository's GitHub Actions workflow when it is due.

## Use the hosted dashboard

The hosted dashboard is the recommended interface for phone and multi-repository use. It lists repositories approved through the signed-in user's GitHub App installations, refreshes the list after repository access changes, starts the target repository's own `Forgewatch` workflow, saves daily or weekly monitoring choices, and displays the uploaded plain-English report. Each target needs the small one-time workflow from [the repository installation guide](docs/INSTALL_REPOSITORY.md). The central Forgewatch repository is intentionally not offered as a scan target. Completed repositories are kept in a collapsible monitoring section so a growing scan history does not overwhelm the page.

Its source is under `web/`. Follow [the hosted dashboard guide](docs/HOSTED_DASHBOARD.md) to create the GitHub App credentials, database, and Vercel deployment. The Python dashboard remains available for local, folder-based scanning.

## Scan any local repository

For a public GitHub repository:

```sh
git clone https://github.com/OWNER/REPOSITORY.git /tmp/repository-to-scan

forgewatch \
  --root /tmp/repository-to-scan \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  --repository OWNER/REPOSITORY \
  --default-branch main \
  scan \
  --trigger manual \
  --ref main \
  --fail-on high
```

For a private repository, clone it using your normal approved GitHub authentication first. Forgewatch itself does not bypass repository permissions.

The target can also be a local checkout from GitLab, Bitbucket, an internal Git service, or a repository with no remote. The scanner core only needs a Git checkout with a resolvable commit.

### Exit codes

- `0`: the scan completed and no finding reached the selected failure threshold.
- `1`: the scan completed, but at least one finding reached the threshold.
- `2`: the scan was incomplete or an operational error occurred.

An exit code of `1` still means a valid report was produced. It is intended to make CI fail when an important finding needs review.

## Reports

The default report directory is `.forgewatch/artifacts/latest/` inside the Forgewatch project, not inside the target repository.

- `scan.md` is the human report. It leads with priorities, why each item matters, and what to do next in plain English.
- `scan.json` is the automation report. It includes commit SHA, tool versions, coverage, execution status, normalised findings, and a `plain_language` section.

Priority wording in the human report:

- Urgent: review immediately.
- Important: review and fix soon.
- Needs attention: plan a fix after important items.
- Lower priority: review when practical.

Raw advisory IDs and scanner messages remain available under `Technical details for maintainers`. Secret values are redacted from both formats.

## Finding history and dismissals

List current findings:

```sh
forgewatch \
  --root /absolute/path/to/repository \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  findings
```

Dismiss a reviewed finding with a required reason and actor:

```sh
forgewatch \
  --root /absolute/path/to/repository \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  dismiss \
  --finding FINDING_ID \
  --reason "Reviewed test-only dependency with no production path" \
  --actor YOUR_GITHUB_NAME
```

A dismissal remains while the same finding stays continuously present. A complete scan of a verified default branch can mark an absent finding resolved. If it later returns, Forgewatch reopens it. Dirty, incomplete, or unverified-branch scans cannot resolve findings.

## Fix policies

The default policy prepares supported fixes automatically but still requires human review before merge:

```json
{
  "policy": {
    "fix_generation": "automatic"
  }
}
```

To require approval before even generating a patch:

```json
{
  "policy": {
    "fix_generation": "require_approval"
  }
}
```

Issue and use a short-lived approval:

```sh
export SECURITY_APPROVAL_KEY='replace-with-at-least-32-random-bytes'

forgewatch \
  --root /absolute/path/to/repository \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  approve-fix \
  --finding FINDING_ID \
  --commit FULL_COMMIT_SHA \
  --actor YOUR_GITHUB_NAME

forgewatch \
  --root /absolute/path/to/repository \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  prepare-fix \
  --finding FINDING_ID \
  --commit FULL_COMMIT_SHA \
  --approval APPROVAL_TOKEN
```

Approval tokens are bound to one repository, finding, commit, action, actor, and expiry. They are single-use and reject stale or replayed requests. Keep the approval key in a secrets manager and never write tokens to CI logs.

## Optional AI patch generation

The deterministic fixer is the supported MVP remediation. Other findings can request one bounded AI patch proposal when OpenAI credentials are available:

```sh
export OPENAI_API_KEY='set-this-outside-the-repository'

forgewatch \
  --root /absolute/path/to/repository \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  prepare-fix \
  --finding FINDING_ID \
  --commit FULL_COMMIT_SHA \
  --ai
```

The provider and model are configurable. The current implementation uses the OpenAI Responses API with JSON Schema output, sends only bounded affected-file context, sets `store: false`, and permits one request per fix by default.

AI output is never treated as a scanner result or a successful fix. It must apply cleanly, remain within approved files, avoid suppression markers, pass the relevant security scanner, and pass the configured isolated checks.

## Configuration reference

Copy `forgewatch.example.json` to the ignored `forgewatch.json` file for local changes.

| Section | Purpose |
|---|---|
| `repository` | Report label and default branch for the target |
| `policy` | Automatic patch preparation or approval-before-generation |
| `scanners` | Scanner enablement, binary paths, rules, and time limits |
| `execution` | Docker image, network setting, timeout, and trusted validation commands |
| `ai` | Provider, model, endpoint, request count, and output limit |
| `github` | Allowed target repositories and the automation repository |
| `state` | SQLite database and report or patch artifact locations |

Do not put tokens, webhook secrets, private keys, passwords, or approval keys in either configuration file.

## Run the complete local test set

From the Forgewatch project:

```sh
cd /Users/kelvinolasupo/Documents/Codex/forgewatch
. .venv/bin/activate
python -m unittest discover -s tests -v
python -m compileall -q forgewatch scripts tests
python -m pip wheel . --no-deps --wheel-dir /tmp/forgewatch-wheel
python scripts/demo.py
```

The demonstration must show that the focused security test fails before the fix, passes afterwards, and that Semgrep no longer detects the original finding in the fixed workspace.

## Kelvin's exact commit and push commands

The GitHub repository already exists. Review and commit the workflow repair and dashboard yourself:

```sh
cd /Users/kelvinolasupo/Documents/Codex/forgewatch

git config user.name
git config user.email
git status --short --branch
git add -A
git diff --cached --check
git diff --cached --stat
git commit -m "feat: run scans in each repository"
git push origin HEAD:main
git push origin HEAD:codex/forgewatch-mvp
```

If either Git identity command prints nothing, set repository-local values before committing:

```sh
git config user.name "YOUR NAME"
git config user.email "YOUR VERIFIED GITHUB EMAIL"
```

These commands do not modify or push the target repository.

## Test the GitHub push

The `Forgewatch tests` workflow needs no App secrets. It runs on pushes to `main` and the implementation branch. It executes the Python and hosted-dashboard tests, builds the Python wheel and Next.js site, runs all three real scanners against the vulnerable fixture, and uploads the demonstration report and patch.

List the runs:

```sh
gh run list \
  --repo 1Kelv/forgewatch \
  --workflow "Forgewatch tests" \
  --limit 5
```

Copy the newest run ID from that output, then watch it:

```sh
gh run watch RUN_ID --repo 1Kelv/forgewatch --exit-status
```

Download its report and patch:

```sh
gh run download RUN_ID \
  --repo 1Kelv/forgewatch \
  --name forgewatch-test-RUN_ID \
  --dir ./downloaded-test-artifact
```

Open `downloaded-test-artifact/scan.md` and confirm it is the plain-English report. Do not configure monitoring until this workflow passes.

## Configure hosted GitHub scans

The hosted design deliberately runs each scan in the target repository instead of spending the central `1Kelv/forgewatch` repository's Actions allowance. The target owner can see the job, cancel it, inspect its logs, and remove the workflow at any time.

### 1. Make the scanning code callable

The central `1Kelv/forgewatch` repository must be public before repositories belonging to unrelated GitHub accounts can call `.github/workflows/reusable-scan.yml`. Review the current files and the complete Git history for credentials, private keys, `.env` files, customer data, or other material that must not become public before changing visibility.

The old `.github/workflows/scan.yml` remains available for legacy and self-scan runs. Hosted dashboard scans use the target-owned workflow instead.

### 2. Give the GitHub App minimum permissions

Configure these repository permissions:

- Metadata: read-only, supplied automatically by GitHub.
- Contents: read-only, to resolve the selected branch to an exact commit.
- Actions: read and write, to start the approved target workflow and read its status and report artifact.

No Contents write or Pull requests write permission is required for scanning. If fix pull requests are added later, use a separate publisher App rather than expanding the scanner's permissions.

To allow anyone to install it, open the App's settings, open `Advanced`, find the danger-zone visibility control, and make the App public. GitHub may show this as changing the App from private to public rather than as the older `Any account` wording. Marketplace listing is not required.

### 3. Add the target workflow

For every approved repository, follow [Add Forgewatch to a repository](docs/INSTALL_REPOSITORY.md). The owner creates `.github/workflows/forgewatch.yml` through GitHub's website and commits it to the default branch. No local folder or terminal is required.

The workflow requests only `contents: read` and calls the reusable scanner in this repository. The exact copyable file is also stored at [templates/forgewatch.yml](templates/forgewatch.yml) and displayed at `/setup` on the hosted site.

### 4. Run and verify the first scan

1. Sign in to the hosted dashboard.
2. Select `Manage repository access` and approve the target.
3. Return to the dashboard and select `Refresh list`.
4. Choose the target, keep `Manual only`, and select `Run scan`.
5. Open the target repository's `Actions` tab and confirm a `Forgewatch` run starts there.
6. Open `View report` after it completes.

A completed scan with findings still produces a valid report. A red run means at least one required check could not finish. The job summary and report state which check failed and why. Never treat an incomplete result as an all-clear.

### 5. Enable schedules carefully

After a manual scan succeeds, change its dashboard frequency to daily or weekly. The Vercel cron endpoint finds due repositories and dispatches their own workflows. A failed dispatch is retried after 15 minutes and remains visible as `Needs attention` in that user's dashboard.

## How another repository owner tries Forgewatch

Another repository owner has three options:

1. Local use: clone Forgewatch, clone any repository they are allowed to read, add its folder in the dashboard, and run a manual or recurring local scan.
2. Self-host: clone or fork Forgewatch, create their own GitHub App, install it only on selected repositories, configure the allow-list and secrets, and run the same workflows.
3. Hosted onboarding: install the public Forgewatch App on selected repositories, add the one-time target workflow, return to the hosted dashboard, refresh the repository list, then choose the target.

After onboarding, their normal workflow is simple:

1. Push code or open a pull request.
2. Wait for the Forgewatch scan.
3. Read `scan.md`, starting with Important or Urgent items.
4. Review any proposed patch and its before-and-after checks.
5. Merge only after a person approves it.

The hosted dashboard provides installation sign-in and tenant-aware repository selection. Every monitor query is filtered by the signed-in GitHub user ID, so one user does not see another user's monitored repositories. `FORGEWATCH_ALLOWED_GITHUB_LOGINS` accepts comma-separated GitHub names for an invite-only beta and `*` for deliberately enabled public sign-in. A public beta should still add rate limits, abuse controls, clear retention information, and service monitoring.

## Pull-request handoff

A prepared fix artifact contains `change.patch`, `metadata.json`, and `pr.md`. Publication requires `validation_status: passed` and rechecks the remote default-branch commit immediately before creating the branch and pull request.

```sh
GH_TOKEN='short-lived-installation-token' forgewatch \
  --root /absolute/path/to/repository \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  publish-pr \
  --artifact /absolute/path/to/fix-artifact
```

There is no merge, auto-merge, or deploy command.

## Troubleshooting

### `forgewatch: scanner executable not found`

Activate the virtual environment and verify `semgrep`, `osv-scanner`, and `gitleaks` are on `PATH`.

### Scan exits with code 1

The scan completed and found an item at or above `--fail-on`. Read `scan.md`. This is different from exit code 2, which means the scan was incomplete or encountered an operational error.

### Validation says blocked

Install and start Docker, then make sure target dependencies were installed without lifecycle scripts. Forgewatch will not run project build commands directly on the host.

### `gh auth status` says the token is invalid

Run:

```sh
gh auth login -h github.com -p https -w
gh auth status
gh auth setup-git
```

### The GitHub scan workflow cannot check out the target

Confirm the target contains `.github/workflows/forgewatch.yml` on its default branch, the App is installed on that target, and the installation owner has approved the App's current permissions. The target workflow checks out its own repository using GitHub's short-lived job token; no personal access token is required.

If the reusable workflow cannot be found, make sure `1Kelv/forgewatch` is public and `.github/workflows/reusable-scan.yml` exists on `main`.

### Every scheduled GitHub scan is red

The old central workflow no longer has a daily timer. Push the current `.github/workflows/scan.yml` to `main` to stop those duplicate scheduled runs. Current daily and weekly scans should appear in each selected target repository.

For a current red run, open its summary and read the plain-English failure reason. Completed scans with findings are successful runs with warnings and an uploaded report. Red is reserved for incomplete scans and operational failures.

## Documentation

- [How someone uses Forgewatch with GitHub](docs/USING_WITH_GITHUB.md)
- [Add Forgewatch to a repository](docs/INSTALL_REPOSITORY.md)
- [Architecture and threat model](docs/ARCHITECTURE.md)
- [Coverage, scanner choices, and licences](docs/COVERAGE.md)
- [GitHub App setup and deployment](docs/GITHUB_APP.md)
- [Hosted dashboard on Vercel](docs/HOSTED_DASHBOARD.md)
- [Operations, scheduling, and costs](docs/OPERATIONS.md)
- [Current limitations](docs/LIMITATIONS.md)
