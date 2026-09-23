# Hosted dashboard on Vercel

The hosted dashboard is the phone-friendly way to use Forgewatch. A user signs in with GitHub, selects a repository where the Forgewatch GitHub App is installed, chooses a branch and frequency, and starts a scan. The target repository's own GitHub Actions area performs the scan. Vercel only hosts the interface, schedule records, and workflow dispatcher.

The hosted dashboard never accepts a local folder path. A pasted value must be a `https://github.com/OWNER/REPOSITORY` URL, and the server verifies that the signed-in user and the Forgewatch GitHub App can access it.

## What is included

- GitHub App user sign-in with encrypted, HTTP-only session cookies.
- A repository picker limited to authorised App installations.
- Manual scans of selected branches using an immutable commit ID.
- Manual, daily, and weekly frequencies.
- Scan progress and result links.
- Plain-English `scan.md` reports displayed inside the dashboard.
- A daily scheduler endpoint protected by `CRON_SECRET`.
- PostgreSQL storage for repository choices, schedules, and run IDs.
- A copyable, no-terminal repository setup guide at `/setup`.

The first deployment is restricted to the GitHub names in `FORGEWATCH_ALLOWED_GITHUB_LOGINS`. Use a comma-separated list for invited testers. The special value `*` permits any GitHub user to sign in, but should only be enabled deliberately after reviewing usage limits and the GitHub App's public installation settings.

## 1. Create the initial Vercel project

Commit and push the `web/` folder first. Then:

1. Sign in to Vercel with GitHub.
2. Select `Add New`, then `Project`.
3. Import `1Kelv/forgewatch`.
4. Set the project root directory to `web`.
5. Keep the detected Next.js build settings and deploy the project once.
6. Copy the permanent production address, such as `https://forgewatch-example.vercel.app`.

The initial page can build without credentials. GitHub sign-in and scanning will become active after the remaining setup and a redeployment.

## 2. Create or update the GitHub App

In GitHub, open `Settings`, `Developer settings`, `GitHub Apps`, and create or edit the Forgewatch App.

Use the production address from step 1:

- Homepage URL: `https://YOUR-FORGEWATCH-DOMAIN`
- Callback URL: `https://YOUR-FORGEWATCH-DOMAIN/api/auth/callback`
- Setup URL: `https://YOUR-FORGEWATCH-DOMAIN`

Enable `Request user authorization (OAuth) during installation`. Keep expiring user tokens enabled.

Minimum repository permissions for hosted scanning:

- Metadata: read-only, supplied automatically.
- Contents: read-only, so the worker can check out approved repositories.
- Actions: read and write, so the hosted controller can start and inspect the target repository's approved scan workflow.

Do not grant pull-request or contents write access until reviewed fix pull requests are deliberately enabled. That can use a separate publisher App later.

Install the App on every repository that should appear in the dashboard. The dashboard deliberately hides `1Kelv/forgewatch` from the target list because it supplies the reusable scanner.

To let people outside the App owner's account install it, make the GitHub App public. In the current GitHub interface, open the App's `Advanced` settings and use the visibility control in the danger zone. This replaces the older `Any account` wording. The App does not need to be listed in GitHub Marketplace.

Record these values from the App settings:

- App ID
- Client ID
- A newly generated client secret
- A newly generated private key
- App slug, taken from its public URL

Never commit these values.

## 3. Publish the reusable scanner

The `1Kelv/forgewatch` repository must be public before unrelated GitHub accounts can call `.github/workflows/reusable-scan.yml`. Audit the files and complete Git history for credentials, private keys, local environment files, private customer data, and anything else that must not become public before changing repository visibility.

Each target repository must then add `.github/workflows/forgewatch.yml`. Follow [the repository installation guide](INSTALL_REPOSITORY.md). The user can do this entirely through GitHub's website, including on a phone.

The target workflow requests read-only access to repository contents. No Forgewatch App secret or personal access token is copied into the target repository.

## 4. Create the database

Create a small PostgreSQL database through Neon, Supabase, or another managed provider. Copy its connection string into `DATABASE_URL`.

Run [schema.sql](../web/db/schema.sql) once using the provider's SQL editor. It creates only the `forgewatch_monitors` table and its scheduling index.

## 5. Configure Vercel and redeploy

Open the Vercel project settings and add every variable from [`.env.example`](../web/.env.example).

Generate `SESSION_SECRET` and `CRON_SECRET` locally:

```sh
openssl rand -base64 48
openssl rand -base64 48
```

Use different generated values. Do not paste them into GitHub issues, workflow inputs, or source files.

For the initial internal deployment, set:

```text
FORGEWATCH_AUTOMATION_REPOSITORY=1Kelv/forgewatch
FORGEWATCH_AUTOMATION_REF=main
FORGEWATCH_ALLOWED_GITHUB_LOGINS=1Kelv
```

Set `APP_URL` to the production address from step 1. Enter the GitHub private key as the complete PEM text. Vercel stores environment variables outside the repository.

For an invite-only beta, add GitHub names with commas:

```text
FORGEWATCH_ALLOWED_GITHUB_LOGINS=1Kelv,another-user
```

To permit any GitHub user to sign in, use:

```text
FORGEWATCH_ALLOWED_GITHUB_LOGINS=*
```

Repository choices are still limited to installations and repositories that the signed-in user is explicitly allowed to access. Dashboard monitor records are filtered by the signed-in GitHub user ID. One user does not inherit another user's repository list or monitoring cards. The central automation repository is hidden from the scan target selector.

Redeploy the project. Environment-variable changes do not affect an earlier deployment until a new deployment is created.

## 6. Verify the deployment

1. Open the deployed dashboard on a phone or computer.
2. Select `Continue with GitHub`.
3. If no repositories appear, select `Manage repository access` and add one to the App installation.
4. Add `.github/workflows/forgewatch.yml` by following the dashboard's `Repository setup guide`.
5. Select the repository in the dashboard.
6. Keep `Manual only` for the first test and select `Run scan`.
7. Confirm a new `Forgewatch` run starts in the target repository.
8. Wait for completion and select `View report` in the dashboard.
9. Change the frequency to daily, refresh the page, and confirm the choice remains saved.

Vercel's free Hobby cron schedule runs once per day, so the first hosted version offers manual, daily, and weekly choices. More frequent schedules require a plan or scheduler that supports them.

## Local web development

Copy the example environment file, fill in development credentials, apply the database schema, and run:

```sh
cd /Users/kelvinolasupo/Documents/Codex/forgewatch/web
cp .env.example .env.local
npm install
npm run dev
```

The local callback URL is `http://localhost:3000/api/auth/callback`. Add it as a second callback URL in the GitHub App before testing locally.
