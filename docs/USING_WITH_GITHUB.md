# Using Forgewatch with a GitHub repository

Forgewatch does not need to be copied into the repository it scans. The target repository remains unchanged unless a reviewed fix is later published as a pull request.

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

## Automatic scans on GitHub

The current hosted design works like this:

1. Pervigil runs Forgewatch from its own standalone GitHub repository and hosts the small webhook receiver.
2. A repository owner installs the Forgewatch GitHub App and selects only the repositories they want scanned.
3. Pervigil adds each full repository name to the Forgewatch allow-list. This prevents an unexpected webhook from starting a scan.
4. A push or pull request sends a signed message to Forgewatch. Forgewatch checks the signature and queues one GitHub Actions job for the exact commit.
5. The job checks out that commit with a short-lived GitHub App token, runs the three security checks, and saves `scan.md` and `scan.json` as a workflow artifact.
6. A developer reads `scan.md`, which leads with simple explanations and practical next steps. Technical scanner details remain available in a collapsed section.
7. A supported fix can be prepared in a disposable workspace. It becomes eligible for a pull request only after every required check passes. A person must still review and merge it.

There is no `npm run dev` step and no dashboard in this MVP. `forgewatch serve` starts only the webhook receiver. The actual scan runs through the Python command or GitHub Actions.

## What another GitHub user can do today

The MVP is ready for Pervigil's own configured repositories. It is not yet a self-service public product. Another user can use it by running their own Forgewatch deployment, or by having Pervigil install and configure their repository manually.

A public customer flow still needs an installation page, organisation sign-in, tenant storage, billing, and a GitHub Check or safe report link that the customer can see without access to Pervigil's private Actions repository. Those are deliberately listed as later product work rather than presented as already available.
