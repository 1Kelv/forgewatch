# Sentinel discovery

Discovery was performed against private repository `1Kelv/sentinel` at commit `4fb42700d20fa2d9edaf9c7dcdf12532249cece1` on 13 September 2026.

## Actual application

- React 18.2 with TypeScript and Vite 4.
- Hand-written CSS and React hooks. No CSS or component framework.
- A scripted browser-only demo. There is no backend, server API, live audio path or detection model in this repository.
- Runtime dependencies are only `react` and `react-dom`. Build dependencies include TypeScript, Vite, the Vite React plugin and React type packages.
- No authentication, authorisation, database access, session handling, server-side secrets or production API credentials were found.
- No CI workflow, automated tests or test script existed in the inspected commit.
- The repository documentation describes two Vercel projects: the Vite application at the repository root and a static, self-contained company page under `site/`.

## Reusable security behaviour

The company site already adds `rel="noopener"` to its external `target="_blank"` links. No `dangerouslySetInnerHTML`, dynamic evaluation, network client, environment-variable access or browser credential storage was found. Theme preferences are the only local-storage use.

There was no existing scanner integration, finding store, approval system, webhook receiver, remediation service or CI security workflow to reuse. Forgewatch therefore remains a separate project and treats Sentinel only as an external target.

## Verified baseline

- `npm ci` completed.
- `npm run build` passed with Vite 4.5.14.
- `npm audit` reported 13 affected package nodes: 4 low, 2 moderate and 7 high.
- Forgewatch's pinned OSV-Scanner 2.5.1 run produced 17 package-advisory findings: 3 low, 6 medium and 8 high. The difference is expected because npm and OSV group dependency paths and advisories differently.
- Semgrep 1.177.0 scanned 24 JavaScript and TypeScript source files with the committed MVP rules and returned no supported code finding.
- Gitleaks 8.30.1 scanned the working tree with full redaction and returned no secret finding.
- The scan recorded a clean worktree and verified that the scanned SHA matched `origin/main` before state reconciliation.

These results cover only the capabilities documented in `COVERAGE.md`. They are not a claim that Sentinel has no vulnerabilities. In particular, the Semgrep Community Edition rules are deliberately narrow and do not provide cross-file or cross-function analysis.
