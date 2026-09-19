# Coverage, scanners and licences

## Code vulnerabilities

Forgewatch uses Semgrep Community Edition 1.177.0 with locally committed rules. The MVP rules detect:

- Reverse tabnabbing in JSX and TSX links opened with `_blank` without `noopener` or `noreferrer`.
- React `dangerouslySetInnerHTML` sites requiring manual data-flow review.

The deterministic fixer supports only the first rule. It adds `rel="noopener noreferrer"` to the single matched anchor. The second rule and all other code issue types are report-only unless the optional AI path is explicitly requested.

Semgrep supports many languages, but the committed MVP rules cover JavaScript, TypeScript, JSX and TSX only. A repository with zero covered source files records this check as `not_applicable`; it does not pretend those files were code-scanned and does not turn an otherwise completed run into an operational failure. Semgrep Community Edition is single-file and mostly single-function analysis, so it will miss findings that require broader data flow.

[Semgrep's repository](https://github.com/semgrep/semgrep) documents local analysis, language support, Community Edition limitations and the LGPL-2.1 licence. Forgewatch uses its own rules and turns metrics off, so private source is scanned locally rather than uploaded to Semgrep.

## Vulnerable dependencies

OSV-Scanner 2.5.1 recursively discovers supported manifests and lockfiles, including npm `package-lock.json`. Each affected package and advisory becomes a finding. Forgewatch does not invoke OSV guided remediation because the official documentation warns that it may execute package managers against untrusted projects.

OSV queries disclose package coordinates and versions to the OSV service by default, not repository source. Offline databases can be configured later for stricter environments. Unsupported or absent manifests are recorded as not applicable rather than as a scanner failure.

- [Supported OSV artifacts and lockfiles](https://google.github.io/osv-scanner/supported-languages-and-lockfiles/)
- [OSV-Scanner 2.5.1 Apache-2.0 licence](https://github.com/google/osv-scanner/blob/v2.5.1/LICENSE)
- [OSV guided remediation warning](https://google.github.io/osv-scanner/experimental/guided-remediation/)

## Exposed secrets

Gitleaks CLI 8.30.1 scans working-tree files by default. Git history scanning is configurable but disabled in the example configuration to control first-run cost. Reports use `--redact=100`, and Forgewatch replaces sensitive JSON keys and common credential patterns again before persistence.

Forgewatch uses the open-source Gitleaks CLI, not `gitleaks-action`. The CLI is MIT-licensed. The separate GitHub Action has different commercial terms for organisation-owned repositories, which is why it was not selected.

- [Gitleaks CLI and redaction documentation](https://github.com/gitleaks/gitleaks)
- [Gitleaks 8.30.1 MIT licence](https://github.com/gitleaks/gitleaks/blob/v8.30.1/LICENSE)
- [Gitleaks Action licence distinction](https://github.com/gitleaks/gitleaks-action/blob/master/README.md#license-change)

## Private repositories and other providers

All three scanner binaries operate on a local checkout, so they do not care who owns the repository or which Git server supplied it. Forgewatch can scan an authorised private checkout and any public checkout. It cannot and must not bypass access controls. The GitHub App installation is limited to repositories explicitly selected by their owner.

GitLab and Bitbucket webhook and merge-request adapters are not implemented. Their checkouts can still be scanned manually or by an external scheduler.

## Commercial-use caution

The scanner choices are suitable for an internal MVP based on the linked upstream licences and local/private scanning behaviour. Before redistributing scanner binaries or offering Forgewatch commercially, obtain legal review of notices, distribution obligations, trademark use, hosted-service terms and the then-current licences. Do not assume today's licence terms will remain unchanged.
