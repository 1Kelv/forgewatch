# Using Forgewatch with a GitHub repository

Forgewatch does not need to be copied into the repository it scans. The target repository remains unchanged unless a reviewed fix is later published as a pull request.

## One-time scan

For a one-time scan, clone any repository you are allowed to read and point the Forgewatch command at that checkout:

```sh
git clone https://github.com/OWNER/REPOSITORY.git /tmp/repository-to-scan

forgewatch \
  --root /tmp/repository-to-scan \
  --config /absolute/path/to/forgewatch/forgewatch.json \
  --repository OWNER/REPOSITORY \
  --default-branch main \
  scan --trigger manual --ref main
```

Public repositories need no GitHub App permission for a local clone. Private repositories require the normal read permission of the person or service doing the clone.

## Local dashboard

Start the interface with:

```sh
cd /absolute/path/to/forgewatch
. .venv/bin/activate
forgewatch --config "$PWD/forgewatch.json" dashboard
```

Add the folder of any cloned Git repository, choose a frequency, and select `Run scan`. The dashboard shows the same plain-English results as `scan.md`. Manual, six-hourly, daily, and weekly frequencies are available. Local schedules run only while the dashboard process remains open.

## Automatic scans on GitHub

The current hosted design works like this:

1. The Forgewatch operator runs it from its own standalone GitHub repository and hosts the controller.
2. A repository owner installs the Forgewatch GitHub App and selects only the repositories they want scanned.
3. Forgewatch verifies that the signed-in user and App installation can access the selected repository. This prevents an unexpected request from starting a scan.
4. A push or pull request sends a signed message to Forgewatch. Forgewatch checks the signature and queues one GitHub Actions job for the exact commit.
5. The job checks out that commit with a short-lived GitHub App token, runs the three security checks, and saves `scan.md` and `scan.json` as a workflow artifact.
6. A developer reads `scan.md`, which leads with simple explanations and practical next steps. Technical scanner details remain available in a collapsed section.
7. A supported fix can be prepared in a disposable workspace. It becomes eligible for a pull request only after every required check passes. A person must still review and merge it.

There is no `npm run dev` step. `forgewatch dashboard` starts the local interface, while `forgewatch serve` starts only the webhook receiver. Scans can run through the dashboard, the Python command, or GitHub Actions.

## What another GitHub user can do today

The hosted dashboard supports self-service repository selection for allow-listed GitHub users. Another user can also run their own Forgewatch deployment and GitHub App.

Wider public use still needs account administration, rate limits, usage controls, billing, and GitHub Check results or a deliberately shared report link. Those are later product features rather than capabilities claimed by the current release.
