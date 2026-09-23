import type { Metadata } from "next";

import { CopyWorkflowButton } from "@/components/copy-workflow-button";
import { targetWorkflow } from "@/lib/setup-workflow";

export const metadata: Metadata = {
  title: "Set up a repository | Forgewatch",
  description: "Add the small GitHub Actions workflow required to scan a repository with Forgewatch.",
};

export default function SetupPage() {
  return (
    <main className="shell setupPage">
      <nav className="nav">
        <a className="brand" href="/"><span className="brandMark">F</span><span>Forgewatch</span></a>
        <a className="textLink" href="/">Back to dashboard</a>
      </nav>

      <header className="setupHeader">
        <p className="eyebrow">One-time repository setup</p>
        <h1>Let the repository run its own scan</h1>
        <p>
          Add one small workflow file to every repository you want to scan. Reports and GitHub Actions usage then stay with that repository.
        </p>
      </header>

      <section className="setupGrid">
        <ol className="setupSteps">
          <li><strong>Open the target repository on GitHub.</strong><span>This is the project you want Forgewatch to check.</span></li>
          <li><strong>Select Add file, then Create new file.</strong><span>You can do this from a phone or computer. No terminal is required.</span></li>
          <li><strong>Name the file <code>.github/workflows/forgewatch.yml</code>.</strong><span>Use that exact name and folder path.</span></li>
          <li><strong>Copy and paste the workflow shown here.</strong><span>It grants read access only. It does not give Forgewatch permission to change your code.</span></li>
          <li><strong>Select Commit changes.</strong><span>Return to Forgewatch, refresh the repository list, and run the scan again.</span></li>
        </ol>

        <section className="codePanel" aria-labelledby="workflow-title">
          <div className="codePanelHeader">
            <div><p className="step">File contents</p><h2 id="workflow-title">forgewatch.yml</h2></div>
            <CopyWorkflowButton value={targetWorkflow} />
          </div>
          <pre>{targetWorkflow}</pre>
        </section>
      </section>

      <aside className="setupNote">
        <strong>Why this file is needed</strong>
        <p>GitHub requires a repository to approve its own automated jobs. The Forgewatch dashboard can then start that approved workflow, but it cannot add or edit the file itself.</p>
      </aside>
    </main>
  );
}
