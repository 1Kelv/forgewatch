# Current limitations

- Code scanning rules cover only two JavaScript and TypeScript issue types. The deterministic fixer supports only reverse tabnabbing.
- Semgrep Community Edition lacks the deeper cross-file and cross-function analysis of commercial engines.
- Gitleaks history scanning is off in the example configuration. The current working tree is covered, not deleted secrets in earlier commits.
- OSV-Scanner reports known vulnerable dependencies. It cannot identify an unknown vulnerability or prove an advisory is reachable in a particular target application.
- GitLab and Bitbucket webhook and merge-request adapters are not implemented. Their local checkouts can still be scanned.
- SQLite plus Actions cache is an MVP persistence mechanism, not a high-availability hosted datastore.
- The Docker validator expects target dependencies to be preinstalled without lifecycle scripts. Native dependency differences between the host and container can block validation.
- There is no general automated regression-test generator. The deterministic issue has a before-and-after security regression check and a real Semgrep rerun; AI may suggest tests, but they remain subject to scope and validation gates.
- AI patch generation is implemented through the OpenAI Responses API but was not externally verified because no API credential was available.
- GitHub App webhook handling and pull-request publication exist as separate advanced paths but are not enabled by the hosted scan flow. Hosted scheduling uses the protected Vercel cron endpoint and each target's workflow.
- The local Python dashboard remains single-user and bound to the current computer. The hosted dashboard adds GitHub sign-in and tenant-aware repository selection, but public use still needs account administration, rate limits, usage controls, and billing.
- New hosted reports are stored as artifacts in each target repository and displayed to the signed-in owner through the hosted dashboard. Older central-worker reports remain readable during migration. A broader public product should also support GitHub Check results or deliberately shared report links.
- Every hosted target must add `.github/workflows/forgewatch.yml` to its default branch. The GitHub App cannot silently add this file because scanning does not request Contents write permission.
- The first public template follows the reviewed `main` branch of the Forgewatch reusable workflow so fixes reach early testers. A stable release should replace `@main` with a reviewed full commit SHA in the target template.
- Automatic pull-request publication must remain disabled for any target whose repository rules reserve commits and pushes for its maintainers.
- Forgewatch does not merge, enable auto-merge, deploy, rotate credentials, rewrite Git history or modify production infrastructure.
