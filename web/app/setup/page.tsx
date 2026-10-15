import type { Metadata } from "next";

import { CopyWorkflowButton } from "@/components/copy-workflow-button";
import { ThemeToggle } from "@/components/theme-toggle";
import { parseGitHubRepository, validateBranch, workflowCreationUrl } from "@/lib/repository";
import { targetWorkflow } from "@/lib/setup-workflow";

export const metadata: Metadata = {
  title: "Set up a repository | Forgewatch",
  description: "Copy the scan file, open the correct GitHub page, and enable Forgewatch for your repository.",
};

type SetupSearchParams = {
  repository?: string | string[];
  default_branch?: string | string[];
};

export default async function SetupPage({
  searchParams,
}: {
  searchParams: Promise<SetupSearchParams>;
}) {
  const params = await searchParams;
  let repository = "";
  let defaultBranch = "main";
  let error = "";
  try {
    if (typeof params.repository === "string" && params.repository.trim()) {
      repository = parseGitHubRepository(params.repository);
    }
    if (typeof params.default_branch === "string" && params.default_branch.trim()) {
      defaultBranch = validateBranch(params.default_branch);
    }
  } catch (cause) {
    repository = "";
    error = cause instanceof Error ? cause.message : "Check the repository URL and branch name.";
  }

  const createUrl = repository ? workflowCreationUrl(repository, defaultBranch) : null;
  const dashboardUrl = repository ? `/?${new URLSearchParams({ repository })}` : "/";

  return (
    <main className="shell setupPage">
      <nav className="nav">
        <a className="brand" href="/"><span className="brandMark">F</span><span>Forgewatch</span></a>
        <div className="navActions"><ThemeToggle /><a className="textLink" href={dashboardUrl}>Back to dashboard</a></div>
      </nav>

      <header className="setupHeader">
        <p className="eyebrow">One-time repository setup</p>
        <h1>Enable scanning for {repository || "your repository"}</h1>
        <p>
          Approving a repository gives Forgewatch access. You also need to add a small scan file to that repository. Follow the steps below once, then start scans from the dashboard.
        </p>
      </header>

      {error && <div className="message error" role="alert">{error}</div>}
      {repository ? (
        <section className="setupTarget" aria-label="Repository being set up">
          <div><p className="step">Selected repository</p><a href={`https://github.com/${repository}`} target="_blank" rel="noreferrer">{repository}</a></div>
          <p>Save the file on <strong>{defaultBranch}</strong>, this repository&apos;s default branch.</p>
          <p>This guide is for <strong>{repository}</strong>. The GitHub link below already uses its owner, name, and branch.</p>
        </section>
      ) : (
        <section className="panel setupSelection" aria-labelledby="setup-selection-title">
          <h2 id="setup-selection-title">Which repository do you want to scan?</h2>
          <p>Open this guide from the dashboard to fill these details automatically, or enter your repository here.</p>
          <form method="get" action="/setup" className="setupSelectionForm">
            <label>GitHub repository URL<input name="repository" type="text" placeholder="https://github.com/your-name/your-project" required /></label>
            <label>Default branch<input name="default_branch" defaultValue="main" required /><small>Usually main. Use the default branch shown in your repository.</small></label>
            <button className="button primary" type="submit">Show my setup steps</button>
          </form>
        </section>
      )}

      <section className="setupGrid">
        <ol className="setupSteps">
          <li>
            <strong>Copy the scan file.</strong>
            <span>Click the button below. It copies all the text you need to paste into GitHub.</span>
            <div className="setupStepAction"><CopyWorkflowButton value={targetWorkflow} /></div>
          </li>
          <li>
            <strong>Open the file creation page on GitHub.</strong>
            {createUrl ? (
              <>
                <span>This link opens <strong className="inlineStrong">{repository}</strong> in a new tab with the filename already filled in. Sign in to GitHub if asked.</span>
                <a className="button primary compact setupStepAction" href={createUrl} target="_blank" rel="noreferrer">Create workflow on GitHub</a>
                <a className="setupUrl" href={createUrl} target="_blank" rel="noreferrer">{createUrl}</a>
              </>
            ) : (
              <span>Enter your repository above to get a direct link to the correct GitHub page.</span>
            )}
          </li>
          <li>
            <strong>Paste the copied text into GitHub&apos;s large editor.</strong>
            <span>Keep the filename as <code>.github/workflows/forgewatch.yml</code>. You are adding this file to {repository || "the repository you want to scan"}.</span>
          </li>
          <li>
            <strong>Save the file on {repository ? defaultBranch : "the default branch"}.</strong>
            <span>Click <strong className="inlineStrong">Commit changes</strong>, choose <strong className="inlineStrong">Commit directly to the {repository ? defaultBranch : "default"} branch</strong>, then confirm. If GitHub requires a pull request, merge it before scanning.</span>
          </li>
          <li>
            <strong>Return to Forgewatch and start your scan.</strong>
            <span>Choose {repository || "your repository"} and click <strong className="inlineStrong">Run scan</strong>. You do not need to approve it again.</span>
            <a className="button secondary compact setupStepAction" href={dashboardUrl}>Back to dashboard</a>
          </li>
        </ol>

        <section className="codePanel" aria-labelledby="workflow-title">
          <div className="codePanelHeader">
            <div><p className="step">Text to paste into GitHub</p><h2 id="workflow-title">forgewatch.yml</h2></div>
            <CopyWorkflowButton value={targetWorkflow} />
          </div>
          <pre>{targetWorkflow}</pre>
        </section>
      </section>

      <aside className="setupNote">
        <strong>What this adds</strong>
        <p>The file tells GitHub how to run Forgewatch&apos;s checks in your repository. It needs read access to your code. Once you save it, you can start scans and manage their frequency from Forgewatch.</p>
      </aside>
    </main>
  );
}
