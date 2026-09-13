# Current limitations

- Code scanning rules cover only two JavaScript and TypeScript issue types. The deterministic fixer supports only reverse tabnabbing.
- Semgrep Community Edition lacks the deeper cross-file and cross-function analysis of commercial engines.
- Gitleaks history scanning is off in the example configuration. The current working tree is covered, not deleted secrets in earlier commits.
- OSV-Scanner reports known vulnerable dependencies. It cannot identify an unknown vulnerability or prove an advisory is reachable in Sentinel.
- GitLab and Bitbucket webhook and merge-request adapters are not implemented. Their local checkouts can still be scanned.
- SQLite plus Actions cache is an MVP persistence mechanism, not a high-availability hosted datastore.
- The Docker validator expects target dependencies to be preinstalled without lifecycle scripts. Native dependency differences between the host and container can block validation.
- There is no general automated regression-test generator. The deterministic issue has a before-and-after security regression check and a real Semgrep rerun; AI may suggest tests, but they remain subject to scope and validation gates.
- AI patch generation is implemented through the OpenAI Responses API but was not externally verified because no API credential was available.
- GitHub App webhook dispatch, scheduled monitoring and pull-request publication are implemented and documented but are not active or externally verified because the App, standalone remote repository, secrets and hosted dispatcher do not yet exist.
- Hosted operation currently uses an explicit repository allow-list and one configured dispatcher installation. There is no customer self-service installation, billing, tenant database or web dashboard yet.
- Reports are stored as artifacts in the Forgewatch Actions repository. A commercial multi-customer version needs GitHub Check results or a tenant-safe report link so an external repository owner does not need access to Pervigil's private automation repository.
- Automatic PR publication must remain disabled for Sentinel while its repository instructions reserve commits and pushes for Kelvin.
- Forgewatch does not merge, enable auto-merge, deploy, rotate credentials, rewrite Git history or modify production infrastructure.
