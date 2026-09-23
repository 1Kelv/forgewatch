# Architecture and threat model

## Separation

Forgewatch has its own Git repository, runtime, configuration and state. Local scans receive a target checkout through `--root`. Hosted targets add only a small GitHub Actions caller workflow; scanner source is loaded from the standalone Forgewatch repository.

```text
Forgewatch dashboard or schedule
          |
          v
  Vercel dispatcher  <---- GitHub App private key
          |
          | workflow_dispatch with exact SHA and ref
          v
  target repository's disposable Actions job
          |
          +--> target checkout using GitHub's job token
          |       contents read-only; token is not persisted
          |
          +--> public Forgewatch reusable workflow
          +--> Semgrep + OSV-Scanner + Gitleaks
          |       no GitHub, approval or AI credentials
          |
          +--> SQLite state + redacted reports
          |
          +--> disposable Git worktree for one finding
                  |
                  +--> deterministic or bounded AI patch
                  +--> regression check
                  +--> relevant security scanner rerun
                  +--> Docker validation, no network or credentials
                  +--> patch artifact

credential-bearing controller
          |
          +--> recheck default branch
          +--> publish focused pull request
          +--> never merge or deploy
```

## Trust boundaries

Untrusted inputs include every repository file and filename, Git history and metadata, scanner stdout and stderr, AI output, webhook payload and issue or pull-request text. They are handled as data and never interpolated into executable scanner commands. Subprocess scanner arguments are arrays. Validation commands come only from trusted Forgewatch configuration.

The hosted dispatcher accepts only authenticated users, validates same-origin state-changing requests, checks that the selected repository belongs to an App installation visible to that user, resolves the requested branch to an exact commit, and uses a repository-scoped installation token. Monitor queries include the signed-in GitHub user ID. The separate webhook service validates `X-Hub-Signature-256` with HMAC-SHA256 and constant-time comparison before parsing the body.

## Execution controls

- Scanner, GitHub and AI calls have explicit timeouts.
- Scanner processes receive an environment with GitHub, approval and OpenAI credentials removed.
- Semgrep metrics and version checks are disabled when using local rules.
- Gitleaks reports use full redaction and Forgewatch discards `Secret` and `Match` values.
- Patch scope is checked against approved affected files.
- Security suppression markers are rejected.
- Docker validation uses no network, a read-only container filesystem, dropped capabilities, `no-new-privileges`, bounded CPU, memory and process count, and a timeout.
- Missing isolation produces `blocked`, not a fabricated validation pass.
- AI usage is bounded by provider, model, maximum output tokens and requests per fix.

## State transitions

A scanner finding begins as `open`. A human may set it to `dismissed` only with a reason and actor. Continuous re-observation preserves the dismissal. A complete, clean-worktree scan whose commit is verified against the default branch may mark an absent open finding `resolved`. If a dismissed or resolved finding disappears and later recurs, it reopens.

Scanner results and future AI hypotheses carry separate `origin` values. This MVP does not ask AI to discover vulnerabilities, so current detected findings are scanner-origin only. AI is limited to patch proposals.

## Approval model

Patch-generation approval and merge approval are separate. The `require_approval` policy uses a high-entropy shared secret to issue a short-lived HMAC token. The signed payload binds repository, finding fingerprint, full commit SHA, action, actor, nonce, issue time and expiry. Verification is followed by an atomic one-time database consume.

This authenticates local approval by possession of the approval key. A multi-user commercial service should replace shared-key issuance with organisation SSO or a GitHub user authorization flow while keeping the same scope and replay controls.

No Forgewatch module can merge, enable auto-merge or deploy.
