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
- GitHub App webhook dispatch and pull-request publication are implemented and documented but are not active until the App secrets and hosted dispatcher are configured. The GitHub Actions schedule can scan Forgewatch itself or a public repository without an App.
- The local Python dashboard remains single-user and bound to the current computer. The hosted dashboard adds GitHub sign-in and tenant-aware repository selection, but public use still needs account administration, rate limits, usage controls, and billing.
- Reports are stored as artifacts in the Forgewatch Actions repository and displayed to authorised users through the hosted dashboard. A broader public product should also support GitHub Check results or deliberately shared report links.
- Automatic pull-request publication must remain disabled for any target whose repository rules reserve commits and pushes for its maintainers.
- Forgewatch does not merge, enable auto-merge, deploy, rotate credentials, rewrite Git history or modify production infrastructure.
