# Add Forgewatch to a repository

This is a one-time setup for each repository you want to scan. It works from GitHub on a phone or computer and does not require a local folder or terminal.

## Before you start

The repository owner must:

1. Install the Forgewatch GitHub App and approve the repository.
2. Add the small workflow file below to that repository's default branch.

The workflow runs inside the target repository's own GitHub Actions area. Its logs, report artifact, and Actions usage remain with that repository. Forgewatch receives only the App access that the owner approved.

## Add the workflow using the GitHub website

1. Open the repository you want to scan on GitHub.
2. Open its `Code` tab.
3. Select `Add file`, then `Create new file`.
4. In the filename box, enter exactly:

   ```text
   .github/workflows/forgewatch.yml
   ```

5. Paste the following file contents:

   ```yaml
   name: Forgewatch

   on:
     workflow_dispatch:
       inputs:
         revision:
           description: Exact commit SHA to scan
           required: true
           type: string
         ref:
           description: Branch name recorded in the report
           required: true
           type: string
         default_branch:
           description: Repository default branch
           required: true
           type: string
         trigger:
           description: What started the scan
           required: true
           type: choice
           options:
             - manual
             - schedule

   permissions:
     contents: read

   jobs:
     scan:
       uses: 1Kelv/forgewatch/.github/workflows/reusable-scan.yml@main
       with:
         revision: ${{ inputs.revision }}
         ref: ${{ inputs.ref }}
         default_branch: ${{ inputs.default_branch }}
         trigger: ${{ inputs.trigger }}
   ```

6. Select `Commit changes`.
7. Keep the target repository's default branch selected, enter a short message such as `Add Forgewatch security scan`, and confirm the commit.
8. Return to the [hosted Forgewatch dashboard](https://forgewatch-sepia.vercel.app).
9. Select `Refresh list`, choose the repository, keep `Manual only` for the first run, and select `Run scan`.

The same workflow is also available at [templates/forgewatch.yml](../templates/forgewatch.yml) and in the hosted dashboard's `/setup` page.

## What the file permits

The workflow requests `contents: read`. It may read the exact repository revision selected for the scan. It does not receive permission to edit files, create branches, merge pull requests, deploy, or change repository settings.

The hosted GitHub App separately needs:

- Metadata: read-only.
- Contents: read-only, to confirm the selected branch and exact commit.
- Actions: read and write, to start the repository-approved workflow and read its status and report artifact.

If the App's permissions change, GitHub may ask an installation owner to approve the updated permissions before scans can start again.

## Confirm the first scan

Open the target repository's `Actions` tab. A workflow named `Forgewatch` should appear. A normal first run will:

1. Check out the exact target commit.
2. Load the public Forgewatch scanning code.
3. Run the code, dependency, and exposed-secret checks.
4. Upload a `forgewatch-RUN_ID` artifact containing `scan.md` and `scan.json`.

A green run means every required check finished. It does not mean every possible security issue has been ruled out. A red run means a check or operational step could not finish. Open the run summary or `scan.md` to see the reason.

## Troubleshooting

### The dashboard says the workflow is not installed

Confirm the file exists on the repository's default branch at `.github/workflows/forgewatch.yml`. The filename must be `forgewatch.yml` because the dashboard dispatches that exact workflow.

### The repository is missing from the dashboard

Select `Manage repository access`, approve the repository in the GitHub App installation, return to the dashboard, and select `Refresh list`. The central `1Kelv/forgewatch` repository is intentionally hidden because it supplies the scanner and is not a scan target.

### The scan could not finish

Open `View report` and find the sentence beginning `Why ... did not finish`. That sentence contains the scanner's reason. The result is intentionally not described as clean when any required check fails.

### GitHub says the reusable workflow cannot be found

The central `1Kelv/forgewatch` repository must be public for unrelated GitHub accounts to call its reusable workflow. Before changing visibility, review the repository and its full Git history for credentials, private keys, local environment files, customer data, or other material that should not be public.

The target repository or its organisation must also allow public reusable workflows under `Settings`, `Actions`, `General`. An organisation owner may need to approve that policy.
