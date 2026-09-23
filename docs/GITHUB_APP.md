# GitHub App setup and deployment

The GitHub App lets the hosted dashboard authenticate users, list only repositories they approved, resolve an exact commit, start the target repository's workflow, and read its status and report artifact. The App does not receive source-code write access for scanning.

## 1. Create the Forgewatch repository

Create a separate repository for Forgewatch, for example `OWNER/forgewatch`. Do not add Forgewatch files to repositories being scanned.

The central repository must contain `.github/workflows/reusable-scan.yml` and be public before unrelated GitHub accounts can call it. Each target adds the small caller from [INSTALL_REPOSITORY.md](INSTALL_REPOSITORY.md). No per-target Actions variable or secret is required.

## 2. Register a GitHub App

Create a GitHub App and let repository owners install it only on targets they approve.

Repository permissions required for the complete workflow:

- Metadata: read-only, implicit.
- Contents: read-only. This resolves the requested branch to an exact commit.
- Actions: read and write when the hosted controller starts and inspects workflow runs.

The hosted manual and scheduled dashboard flow does not require webhook subscriptions. If the separate webhook service is enabled later, subscribe only to the events it actually handles and set a high-entropy webhook secret.

GitHub documents that Apps start with no permissions and should request the minimum required permissions. See [choosing GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app).

Use a separate publisher App if optional fix branches and pull requests are enabled later. Do not expand the scanning App to Contents write or Pull requests write merely for convenience.

## 3. Configure secrets

Store the App ID, client ID, client secret, and private key only in the Vercel project's environment variables described in [HOSTED_DASHBOARD.md](HOSTED_DASHBOARD.md). Target repositories need no Forgewatch secret and no personal access token.

Webhook dispatcher secrets, stored in the host's secrets manager:

- `GITHUB_APP_ID`
- `GITHUB_APP_INSTALLATION_ID`
- `GITHUB_APP_PRIVATE_KEY_PATH`
- `GITHUB_WEBHOOK_SECRET`

Optional controller secrets:

- `SECURITY_APPROVAL_KEY`
- `OPENAI_API_KEY`

Never put private keys or tokens in `forgewatch.json`, source control, workflow inputs, issue text, pull-request text or scanner configuration.

## 4. Run the dispatcher

The dispatcher requires OpenSSL to sign the GitHub App JWT.

```sh
forgewatch --root /path/to/any/git/checkout --config /etc/forgewatch/forgewatch.json \
  serve --host 127.0.0.1 --port 8787
```

Place it behind an HTTPS reverse proxy with a request-body limit and rate limit. Expose only `POST /github/webhook`. The service validates the raw payload signature with constant-time comparison before parsing it, rejects duplicate delivery IDs and dispatches only allow-listed repositories.

[GitHub's webhook validation documentation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries) defines the `sha256=` HMAC format implemented here.

## 5. Verify hosted scanning

1. Add `.github/workflows/forgewatch.yml` to a test target and start it through the hosted dashboard.
2. Confirm `scan.json` contains the expected target SHA and all three scanner versions and statuses.
3. Confirm the workflow run appears in the target repository rather than the central Forgewatch repository.
4. Enable a daily schedule and confirm the Vercel cron starts the target workflow when due.
5. Confirm the scheduled workflow runs after 03:17 UTC and scans the selected target.
6. Confirm a deliberately broken scanner produces `incomplete`, a failed check and a report artifact.

Do not call monitoring active before these checks pass in the real repositories.

## 6. Pull requests and merge controls

Keep `publish-pr` outside the validation container. Give it only a short-lived installation token. It rejects blocked or failed validation and a stale default branch. Enable branch protection or repository rules requiring Kelvin's review and the Forgewatch check. Forgewatch has no code path for merge, auto-merge or deployment.

Respect each target repository's contribution rules. When commits and pushes are reserved for its maintainers, use generated patch artifacts for manual application and do not enable automatic pull-request publication.
