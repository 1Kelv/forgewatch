"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

type User = { login: string; name: string; avatarUrl: string };
type Repository = {
  id: number;
  installationId: number;
  fullName: string;
  private: boolean;
  defaultBranch: string;
  url: string;
  ownerAvatarUrl: string;
};
type Frequency = "manual" | "daily" | "weekly";
type Monitor = {
  repositoryId: string;
  repositoryFullName: string;
  defaultBranch: string;
  scanBranch: string;
  frequency: Frequency;
  nextScanAt: string | null;
  lastRunId: string | null;
  lastRunUrl: string | null;
  lastStartedAt: string | null;
  lastError: string | null;
  run: null | {
    status: string;
    conclusion: string | null;
    url: string;
    createdAt: string;
    updatedAt: string;
  };
};

const frequencyLabels: Record<Frequency, string> = {
  manual: "Manual only",
  daily: "Every day",
  weekly: "Every week",
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...(init.headers || {}) } : init?.headers,
    cache: "no-store",
  });
  const value = (await response.json()) as T & { error?: string };
  if (!response.ok) throw new Error(value.error || "The request could not be completed.");
  return value;
}

function readableDate(value: string | null): string {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusLabel(monitor: Monitor): { label: string; tone: string } {
  if (monitor.lastError) return { label: "Needs attention", tone: "bad" };
  if (!monitor.run) return { label: "Waiting", tone: "quiet" };
  if (monitor.run.status !== "completed") return { label: "Scanning", tone: "working" };
  if (monitor.run.conclusion === "success") return { label: "Completed", tone: "good" };
  return { label: "Could not finish", tone: "bad" };
}

export function Dashboard({ appSlug }: { appSlug: string }) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [monitors, setMonitors] = useState<Monitor[]>([]);
  const [repository, setRepository] = useState("");
  const [branch, setBranch] = useState("main");
  const [frequency, setFrequency] = useState<Frequency>("manual");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [repositoriesLoading, setRepositoriesLoading] = useState(false);
  const [monitorsOpen, setMonitorsOpen] = useState(false);
  const previousMonitorAttention = useRef(false);
  const [report, setReport] = useState<{ name: string; text: string } | null>(null);

  const loadMonitors = useCallback(async () => {
    const value = await api<{ monitors: Monitor[] }>("/api/scans");
    setMonitors(value.monitors);
  }, []);

  const loadRepositories = useCallback(async () => {
    setRepositoriesLoading(true);
    try {
      const value = await api<{ repositories: Repository[] }>("/api/repositories");
      setRepositories(value.repositories);
    } finally {
      setRepositoriesLoading(false);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const session = await api<{ authenticated: boolean; user?: User }>("/api/session");
      if (!session.authenticated || !session.user) {
        setUser(null);
        return;
      }
      setUser(session.user);
      await Promise.all([loadRepositories(), loadMonitors()]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The dashboard could not load.");
    } finally {
      setLoading(false);
    }
  }, [loadMonitors, loadRepositories]);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const loginError = query.get("error");
    if (loginError) {
      setError(loginError);
      window.history.replaceState({}, "", "/");
    }
    void load();
  }, [load]);

  useEffect(() => {
    if (!user) return;
    const interval = window.setInterval(() => void loadMonitors().catch(() => undefined), 15_000);
    return () => window.clearInterval(interval);
  }, [loadMonitors, user]);

  useEffect(() => {
    if (!user) return;
    const refreshAfterGitHub = () => {
      void loadRepositories().catch((cause) => {
        setError(cause instanceof Error ? cause.message : "The repository list could not be refreshed.");
      });
    };
    window.addEventListener("focus", refreshAfterGitHub);
    return () => window.removeEventListener("focus", refreshAfterGitHub);
  }, [loadRepositories, user]);

  useEffect(() => {
    if (repositories.some((item) => item.url.toLowerCase() === repository.toLowerCase())) return;
    const first = repositories[0];
    setRepository(first?.url || "");
    setBranch(first?.defaultBranch || "main");
  }, [repositories, repository]);

  useEffect(() => {
    const needsAttention = monitors.some((item) => {
      if (item.lastError || !item.run) return true;
      return item.run.status !== "completed" || item.run.conclusion !== "success";
    });
    if (needsAttention && !previousMonitorAttention.current) setMonitorsOpen(true);
    if (!needsAttention && previousMonitorAttention.current) setMonitorsOpen(false);
    previousMonitorAttention.current = needsAttention;
  }, [monitors]);

  const matchingRepository = useMemo(
    () =>
      repositories.find(
        (item) =>
          item.url.toLowerCase() === repository.toLowerCase() ||
          item.fullName.toLowerCase() === repository.toLowerCase(),
      ),
    [repositories, repository],
  );

  function chooseRepository(value: string) {
    setRepository(value);
    const selected = repositories.find(
      (item) => item.url.toLowerCase() === value.toLowerCase(),
    );
    if (selected) setBranch(selected.defaultBranch);
  }

  async function queueScan(selectedRepository: string, selectedBranch: string, selectedFrequency: Frequency) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const value = await api<{ message: string; run: { url: string } }>("/api/scans", {
        method: "POST",
        body: JSON.stringify({
          repository: selectedRepository,
          branch: selectedBranch,
          frequency: selectedFrequency,
        }),
      });
      setNotice(value.message);
      await loadMonitors();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The scan could not start.");
    } finally {
      setBusy(false);
    }
  }

  async function startScan(event: FormEvent) {
    event.preventDefault();
    await queueScan(repository, branch, frequency);
  }

  async function changeFrequency(item: Monitor, value: Frequency) {
    setError("");
    try {
      await api(`/api/monitors/${item.repositoryId}`, {
        method: "PATCH",
        body: JSON.stringify({ frequency: value }),
      });
      setNotice(`${item.repositoryFullName} now uses ${frequencyLabels[value].toLowerCase()}.`);
      await loadMonitors();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The frequency could not be changed.");
    }
  }

  async function remove(item: Monitor) {
    if (!window.confirm(`Stop monitoring ${item.repositoryFullName}?`)) return;
    setError("");
    try {
      await api(`/api/monitors/${item.repositoryId}`, { method: "DELETE" });
      setNotice(`${item.repositoryFullName} was removed from this dashboard.`);
      await loadMonitors();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The repository could not be removed.");
    }
  }

  async function viewReport(item: Monitor) {
    if (!item.lastRunId) return;
    setBusy(true);
    setError("");
    try {
      const value = await api<{ report: string }>(`/api/scans/${item.lastRunId}/report`);
      setReport({ name: item.repositoryFullName, text: value.report });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The report could not be opened.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <main className="shell"><div className="loading">Loading Forgewatch</div></main>;
  }

  if (!user) {
    return (
      <main className="shell landing">
        <nav className="nav">
          <a className="brand" href="/" aria-label="Forgewatch home"><span className="brandMark">F</span><span>Forgewatch</span></a>
          <span className="productTag">Repository security</span>
        </nav>
        <section className="hero">
          <p className="eyebrow">Repository security, explained clearly</p>
          <h1>Know what needs fixing without decoding security jargon.</h1>
          <p className="heroCopy">
            Connect GitHub, choose a repository, and let Forgewatch run its checks in GitHub Actions. Your report tells you what matters, why it matters, and what to do next.
          </p>
          {error && <div className="message error" role="alert">{error}</div>}
          <div className="heroActions">
            <a className="button primary" href="/api/auth/github">Continue with GitHub</a>
            {appSlug && <a className="button secondary" href={`https://github.com/apps/${appSlug}/installations/new`}>Install Forgewatch</a>}
          </div>
          <div className="trustRow">
            <span>Read access is limited to repositories you approve</span>
            <span>Scans run in temporary GitHub workers</span>
            <span>Reports use plain English</span>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <nav className="nav">
        <a className="brand" href="/"><span className="brandMark">F</span><span>Forgewatch</span></a>
        <div className="account">
          <img src={user.avatarUrl} alt="" />
          <span>{user.login}</span>
          <form action="/api/auth/logout" method="post"><button className="textButton">Sign out</button></form>
        </div>
      </nav>

      <header className="pageHeader">
        <div><p className="eyebrow">Security overview</p><h1>Repository dashboard</h1><p>Start a scan, change a schedule, or open the latest plain-English report.</p></div>
        {appSlug && <a className="button secondary compact" href={`https://github.com/apps/${appSlug}/installations/new`} target="_blank" rel="noreferrer">Manage repository access</a>}
      </header>

      {error && <div className="message error" role="alert">{error}</div>}
      {notice && <div className="message success" role="status">{notice}</div>}

      <section className="panel scanPanel">
        <div className="panelHeading"><div><p className="step">New scan</p><h2>Choose a GitHub repository</h2></div><span className="safeNote">Only approved repositories are available</span></div>
        {repositories.length ? (
          <form className="scanForm" onSubmit={startScan}>
            <label className="wide">Repository
              <select value={repository} onChange={(event) => chooseRepository(event.target.value)} required>
                <option value="" disabled>Select an approved repository</option>
                {repositories.map((item) => <option key={item.id} value={item.url}>{item.fullName} ({item.private ? "private" : "public"})</option>)}
              </select>
              <span className="fieldHelp">
                <small>{matchingRepository ? `${matchingRepository.private ? "Private" : "Public"} repository connected` : "Choose a repository approved in GitHub"}</small>
                <button className="textButton" type="button" disabled={repositoriesLoading} onClick={() => void loadRepositories().catch((cause) => setError(cause instanceof Error ? cause.message : "The repository list could not be refreshed."))}>{repositoriesLoading ? "Refreshing" : "Refresh list"}</button>
              </span>
            </label>
            <label>Branch<input value={branch} onChange={(event) => setBranch(event.target.value)} required /></label>
            <label>Scan frequency<select value={frequency} onChange={(event) => setFrequency(event.target.value as Frequency)}>{Object.entries(frequencyLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <button className="button primary scanButton" disabled={busy}>{busy ? "Starting scan" : "Run scan"}</button>
          </form>
        ) : (
          <div className="empty"><h3>No scan targets are connected yet</h3><p>Choose repositories in GitHub, then return to this tab. The private Forgewatch worker is intentionally hidden from this list.</p>{appSlug && <a className="button primary" href={`https://github.com/apps/${appSlug}/installations/new`} target="_blank" rel="noreferrer">Choose repositories</a>}</div>
        )}
      </section>

      <section className="repositorySection">
        {monitors.length ? (
          <details className="repositoryDrawer" open={monitorsOpen} onToggle={(event) => setMonitorsOpen(event.currentTarget.open)}>
            <summary>
              <div><p className="step">Monitoring</p><h2>Scanned repositories</h2></div>
              <span className="drawerMeta">{monitors.length} connected <span className="drawerAction">Show or hide</span></span>
            </summary>
            <div className="cards">
              {monitors.map((item) => {
                const status = statusLabel(item);
                return (
                  <article className="repoCard" key={item.repositoryId}>
                    <div className="repoTop"><div><p className="repoName">{item.repositoryFullName}</p><p className="branch">Branch: {item.scanBranch}</p></div><span className={`status ${status.tone}`}>{status.label}</span></div>
                    <div className="facts"><div><span>Last started</span><strong>{readableDate(item.lastStartedAt)}</strong></div><div><span>Next scan</span><strong>{readableDate(item.nextScanAt)}</strong></div></div>
                    {item.lastError && <p className="inlineError">{item.lastError}</p>}
                    <label className="frequencyField">Frequency<select value={item.frequency} onChange={(event) => void changeFrequency(item, event.target.value as Frequency)}>{Object.entries(frequencyLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                    <div className="cardActions">
                      <button className="button primary compact" disabled={busy} onClick={() => void queueScan(`https://github.com/${item.repositoryFullName}`, item.scanBranch, item.frequency)}>Scan again</button>
                      {item.run?.status === "completed" && <button className="button secondary compact" disabled={busy} onClick={() => void viewReport(item)}>View report</button>}
                      {item.lastRunUrl && <a className="textLink" href={item.lastRunUrl} target="_blank" rel="noreferrer">Open in GitHub</a>}
                      <button className="textButton danger" onClick={() => void remove(item)}>Remove</button>
                    </div>
                  </article>
                );
              })}
            </div>
          </details>
        ) : (
          <div className="empty repositoryEmpty"><h3>No scans have been started</h3><p>Choose a repository above. It will appear here as soon as its first scan is queued.</p></div>
        )}
      </section>

      {report && <div className="modalBackdrop" role="presentation" onMouseDown={() => setReport(null)}><section className="reportModal" role="dialog" aria-modal="true" aria-labelledby="report-title" onMouseDown={(event) => event.stopPropagation()}><div className="reportHeader"><div><p className="step">Latest report</p><h2 id="report-title">{report.name}</h2></div><button className="button secondary compact" onClick={() => setReport(null)}>Close</button></div><pre>{report.text}</pre></section></div>}
    </main>
  );
}
