# Using Forgewatch with a GitHub repository

Forgewatch's scanner code does not need to be copied into the repository it scans. Hosted targets add only a small GitHub Actions workflow that calls the public reusable scanner. The target's application code remains unchanged unless a reviewed fix is later published as a pull request.

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

The hosted design works like this:

1. The Forgewatch operator keeps the reusable scanner in its own public repository and hosts the controller.
2. A repository owner installs the Forgewatch GitHub App and selects only the repositories they want scanned.
3. The owner adds the small `.github/workflows/forgewatch.yml` file from [the repository installation guide](INSTALL_REPOSITORY.md).
4. Forgewatch verifies that the signed-in user and App installation can access the selected repository. This prevents an unexpected request from starting a scan.
5. The dashboard queues one GitHub Actions job in that target repository for the exact commit.
6. The job checks out its own repository with GitHub's short-lived job token, runs the three security checks, and saves `scan.md` and `scan.json` as a workflow artifact in the target.
7. A developer reads `scan.md`, which leads with simple explanations and practical next steps. Technical scanner details remain available separately.
8. A supported fix can be prepared in a disposable workspace. It becomes eligible for a pull request only after every required check passes. A person must still review and merge it.

There is no `npm run dev` step. `forgewatch dashboard` starts the local interface, while `forgewatch serve` starts only the webhook receiver. Scans can run through the dashboard, the Python command, or GitHub Actions.

## What another GitHub user can do today

When `FORGEWATCH_ALLOWED_GITHUB_LOGINS=*`, any GitHub user can sign in. They still see only repositories made available through App installations their account can access. Monitoring records are filtered by their GitHub user ID.

Public use should still add rate limits, abuse controls, service monitoring, and a clear retention policy. The target-owned workflow prevents one person's scans from consuming the central Forgewatch repository's Actions allowance.
