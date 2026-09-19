# Forgewatch

Forgewatch is Pervigil's standalone repository security agent. It scans a Git checkout, explains what needs attention in plain English, remembers findings between scans, prepares narrow fixes in disposable workspaces, and can hand a validated patch to a human through a pull request.

Forgewatch never merges, enables auto-merge, deploys, rotates credentials, or changes production infrastructure.

The first configured target is `1Kelv/sentinel`, but Forgewatch is a separate Git repository and runtime. Nothing needs to be added to Sentinel or to another repository being scanned.

## Current status

This repository contains a working local MVP and GitHub Actions automation, not a public hosted service.

- The local dashboard can register repositories, run scans, show plain-English reports, and schedule recurring local scans.
- Local scanning and the deliberately vulnerable demonstration fixture are working.
- The GitHub Actions test and scan workflows are included. A scan of Forgewatch itself or another public repository does not require a GitHub App.
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
3. Optionally enter a display name such as `1Kelv/sentinel` and its default branch.
4. Choose `Manual only`, `Every 6 hours`, `Every day`, or `Every week`.
5. Select `Add repository`, then `Run scan`.
6. When it finishes, select `View report`.

The dashboard remembers repository choices in `.forgewatch/dashboard.json`. Reports are written under `.forgewatch/artifacts/dashboard/`. Both locations are ignored by Git and remain outside every target repository.

Local recurring scans run only while the dashboard server is open. GitHub Actions schedules run independently in GitHub and are the better choice for always-on monitoring.

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
git add .github README.md docs forgewatch pyproject.toml tests
git diff --cached --check
git diff --cached --stat
git commit -m "feat: add dashboard and repair scheduled scans"
git push origin HEAD:main
git push origin HEAD:codex/forgewatch-mvp
```

If either Git identity command prints nothing, set repository-local values before committing:

```sh
git config user.name "YOUR NAME"
git config user.email "YOUR VERIFIED GITHUB EMAIL"
```

These commands do not modify or push Sentinel.

## Test the GitHub push

The `Forgewatch tests` workflow needs no App secrets. It runs on pushes to `main` and the implementation branch. It executes the unit tests, builds the Python wheel, runs all three real scanners against the vulnerable fixture, and uploads the demonstration report and patch.

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

## Configure automatic GitHub scans

The test workflow proves Forgewatch itself works. The scan workflow can scan Forgewatch itself and public repositories without App secrets. Scanning a different private repository such as Sentinel requires a GitHub App installation or a read-only fine-grained token stored as the `FORGEWATCH_TARGET_TOKEN` Actions secret.

With no target variables configured, the daily schedule scans the Forgewatch repository itself. Set the target variables below only after credentials for the private target are ready.

### 1. Register the App

In GitHub, open `Settings`, `Developer settings`, `GitHub Apps`, then `New GitHub App`.

Use:

- Name: a globally unique variation of `Forgewatch`.
- Homepage URL: `https://pervigil.co.uk`.
- Webhook URL: `https://YOUR_HTTPS_HOST/github/webhook`.
- Webhook secret: a new high-entropy value stored outside source control.
- SSL verification: enabled.
- Installation scope: only this account for the internal MVP.

Repository permissions for the single-App MVP:

- Metadata: read-only, supplied automatically by GitHub.
- Contents: read and write. Read checks out repositories; write is needed for repository dispatch and optional fix branches.
- Pull requests: read and write for pull-request events and optional reviewed fix pull requests.
- Actions: read-only only if the hosted controller will inspect workflow runs.

Subscribe to `push` and `pull_request` events. Select the minimum permissions required and install the App only on `forgewatch` and `sentinel`.

For stronger production separation, use a read-only scanning App and a separate publisher App with write permission. The MVP supports one App, but never passes its token into target code execution.

### 2. Generate and store the App key

Record the App ID, generate a private key from the App settings, and store that file in an approved secrets manager. Do not copy the key into either repository.

Add the App ID and private key as Actions secrets:

```sh
gh secret set FORGEWATCH_APP_ID --repo 1Kelv/forgewatch

gh secret set FORGEWATCH_APP_PRIVATE_KEY \
  --repo 1Kelv/forgewatch \
  < /absolute/private/path/to/forgewatch-app.pem
```

The first command prompts for the App ID without placing it in shell history.

Set the scheduled target:

```sh
gh variable set FORGEWATCH_TARGET_OWNER \
  --repo 1Kelv/forgewatch \
  --body 1Kelv

gh variable set FORGEWATCH_TARGET_REPOSITORY \
  --repo 1Kelv/forgewatch \
  --body sentinel

gh variable set FORGEWATCH_TARGET_DEFAULT_BRANCH \
  --repo 1Kelv/forgewatch \
  --body main
```

### 3. Run the first real GitHub scan manually

```sh
gh workflow run scan.yml \
  --repo 1Kelv/forgewatch \
  --ref main \
  -f owner=1Kelv \
  -f repository=sentinel \
  -f revision=main \
  -f ref=main \
  -f default_branch=main \
  -f trigger=manual
```

List and watch the newest `Forgewatch scan` run:

```sh
gh run list \
  --repo 1Kelv/forgewatch \
  --workflow "Forgewatch scan" \
  --limit 5

gh run watch RUN_ID --repo 1Kelv/forgewatch --exit-status
```

The workflow now treats a completed scan with findings as a successful run with a warning. It uploads the report so the findings can be reviewed. A red workflow means the scan was incomplete or another operational step failed. Download the artifact and inspect `scan.md`; `scan.json` distinguishes `findings` from `incomplete`.

### 4. Start the webhook receiver

Set these values in the host's secrets manager:

```sh
export GITHUB_APP_ID='YOUR_APP_ID'
export GITHUB_APP_INSTALLATION_ID='INSTALLATION_ID_WITH_ACCESS_TO_FORGEWATCH'
export GITHUB_APP_PRIVATE_KEY_PATH='/absolute/private/path/to/forgewatch-app.pem'
export GITHUB_WEBHOOK_SECRET='THE_SAME_SECRET_CONFIGURED_IN_GITHUB'
```

Start the receiver behind an HTTPS reverse proxy:

```sh
cd /absolute/path/to/forgewatch
. .venv/bin/activate
forgewatch \
  --root /absolute/path/to/forgewatch \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  serve \
  --host 127.0.0.1 \
  --port 8787
```

Expose only `POST /github/webhook`. Configure an HTTPS request-size limit and rate limit at the proxy.

### 5. Verify monitoring before calling it active

1. Redeliver a signed test webhook from the GitHub App settings and confirm HTTP `202`.
2. Push a harmless commit to a test branch and confirm exactly one workflow starts for that commit.
3. Open or update a test pull request and confirm its head commit is scanned.
4. Confirm a repeated delivery ID is rejected.
5. Confirm the daily job runs after `03:17 UTC` and scans the configured default target.
6. Confirm the report records the expected repository, full commit SHA, tool versions, coverage, and status for every check.
7. Break a scanner path in a test configuration and confirm the result is `incomplete`, not clean.
8. Keep automatic pull-request publication disabled for Sentinel until its repository working agreement explicitly permits Forgewatch to commit and push.

Monitoring is not active until those checks pass in GitHub.

## How another repository owner tries Forgewatch

For the internal MVP, another owner has three options:

1. Local use: clone Forgewatch, clone any repository they are allowed to read, add its folder in the dashboard, and run a manual or recurring local scan.
2. Self-host: clone or fork Forgewatch, create their own GitHub App, install it only on selected repositories, configure the allow-list and secrets, and run the same workflows.
3. Manual Pervigil onboarding: install Pervigil's App on selected repositories, then have Pervigil add the full `OWNER/REPOSITORY` name to the server allow-list and scheduled-target configuration.

After onboarding, their normal workflow is simple:

1. Push code or open a pull request.
2. Wait for the Forgewatch scan.
3. Read `scan.md`, starting with Important or Urgent items.
4. Review any proposed patch and its before-and-after checks.
5. Merge only after a person approves it.

The MVP is not yet a self-service public product. A public customer version still needs an installation page, organisation sign-in, tenant-safe storage, billing, and GitHub Check results or a report link that does not require access to Pervigil's private Actions repository.

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

For the Forgewatch repository itself or a public target, no App secret is required. For a different private target, confirm either that the App is installed and its App ID and private-key secrets match, or that `FORGEWATCH_TARGET_TOKEN` contains a read-only fine-grained token with access to that repository. Also confirm the manual inputs use the correct owner and repository name.

GitHub may say `repository not found` even when a private repository exists. This is how GitHub hides private repositories from credentials that cannot read them. The workflow checks for this situation before checkout and explains which credential is missing.

### Every scheduled GitHub scan is red

Open the failed job and read the first error. `appId option is required` means the old workflow tried to use a GitHub App even though its secrets were absent. The repaired workflow skips that token step when no App is configured. Push the current changes to `main`, then run the workflow again.

After this repair, completed scans with findings are shown as successful runs with warnings and an uploaded report. Red is reserved for incomplete scans and operational failures.

## Documentation

- [How someone uses Forgewatch with GitHub](docs/USING_WITH_GITHUB.md)
- [Sentinel discovery](docs/SENTINEL_DISCOVERY.md)
- [Architecture and threat model](docs/ARCHITECTURE.md)
- [Coverage, scanner choices, and licences](docs/COVERAGE.md)
- [GitHub App setup and deployment](docs/GITHUB_APP.md)
- [Operations, scheduling, and costs](docs/OPERATIONS.md)
- [Current limitations](docs/LIMITATIONS.md)
