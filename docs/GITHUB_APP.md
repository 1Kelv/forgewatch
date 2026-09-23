# GitHub App setup and deployment

The GitHub App is needed for webhook-triggered scans and for checking out a different private repository. It is not needed for a scheduled scan of Forgewatch itself or a public target. Do not call App-based monitoring active until every step below is completed and a signed test delivery plus workflow run are verified.

## 1. Create the Forgewatch repository

Create a new private repository for this standalone project, for example `1Kelv/forgewatch`. Push the implementation branch there after review. Do not add any Forgewatch file to Sentinel.

Set these Actions variables in the Forgewatch repository:

- `FORGEWATCH_TARGET_OWNER=1Kelv`
- `FORGEWATCH_TARGET_REPOSITORY=sentinel`
- `FORGEWATCH_TARGET_DEFAULT_BRANCH=main`

If Sentinel moves to an organisation, install the app on that organisation, update the owner and repository variables, and update the configuration allow-list. No scanner code needs to change. Webhook-triggered runs carry the installed repository owner, name, exact commit and default branch into the scan instead of labelling every target as Sentinel.

## 2. Register a GitHub App

Create a private GitHub App and install it only on the Forgewatch and Sentinel repositories.

Repository permissions required for the complete workflow:

- Metadata: read-only, implicit.
- Contents: read and write. Read is used to check out targets. Write is required by GitHub's repository-dispatch endpoint and by optional fix branches.
- Pull requests: read and write. Read enables pull-request webhook payloads. Write is used only by the explicit `publish-pr` controller command.
- Actions: read and write when the hosted controller starts and inspects workflow runs.

Subscribe to `push` and `pull_request` events. Set a high-entropy webhook secret and the webhook URL to `https://YOUR_HOST/github/webhook`.

GitHub documents that Apps start with no permissions and should request the minimum required permissions. The repository-dispatch endpoint specifically requires Contents write. See [choosing GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app) and [creating a repository dispatch event](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event).

For stricter separation, use one read-only App for webhook and checkout plus a second publisher App with Contents and Pull requests write. The MVP supports the single-App setup but never exposes its token to repository code execution.

## 3. Configure secrets

Forgewatch Actions repository secrets:

- `FORGEWATCH_APP_ID`
- `FORGEWATCH_APP_PRIVATE_KEY`

As a simpler checkout-only alternative, a read-only fine-grained token for the private target can be stored as `FORGEWATCH_TARGET_TOKEN`. That token does not provide webhook dispatch or pull-request publication. Do not configure both approaches unless the fallback is intentional and documented.

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

## 5. Verify each trigger

1. Run `Forgewatch scan` manually with the workflow's Run workflow button.
2. Confirm `scan.json` contains the expected target SHA and all three scanner versions and statuses.
3. Send a GitHub webhook test delivery and confirm the dispatcher returns HTTP 202.
4. Push a harmless branch commit and confirm one `repository_dispatch` run starts.
5. Open or synchronize a test pull request and confirm its head SHA is scanned.
6. Confirm a duplicate delivery ID is rejected.
7. Confirm the scheduled workflow runs after 03:17 UTC and scans the default target.
8. Confirm a deliberately broken scanner produces `incomplete`, a failed check and a report artifact.

Do not call monitoring active before these checks pass in the real repositories.

## 6. Pull requests and merge controls

Keep `publish-pr` outside the validation container. Give it only a short-lived installation token. It rejects blocked or failed validation and a stale default branch. Enable branch protection or repository rules requiring Kelvin's review and the Forgewatch check. Forgewatch has no code path for merge, auto-merge or deployment.

Sentinel's current repository instructions reserve commits and pushes for Kelvin. Until those instructions are deliberately updated, use generated patch artifacts for manual application and do not enable automatic PR publication for Sentinel.
