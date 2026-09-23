import { createPrivateKey } from "node:crypto";

import { SignJWT } from "jose";

import { automationRepository, githubAppEnv } from "@/lib/env";

const API = "https://api.github.com";
const API_VERSION = "2026-03-10";

type GitHubRepository = {
  id: number;
  full_name: string;
  private: boolean;
  default_branch: string;
  html_url: string;
  owner: { login: string; avatar_url: string };
};

export type AvailableRepository = {
  id: number;
  installationId: number;
  fullName: string;
  private: boolean;
  defaultBranch: string;
  url: string;
  ownerAvatarUrl: string;
};

type WorkflowRun = {
  id: number;
  status: string;
  conclusion: string | null;
  html_url: string;
  created_at: string;
  updated_at: string;
};

async function githubFetch<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": API_VERSION,
      "User-Agent": "Forgewatch",
      ...(init.headers || {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `GitHub returned ${response.status}.`;
    try {
      const value = (await response.json()) as { message?: string };
      if (value.message) message = value.message;
    } catch {
      // Keep the status-based message when GitHub does not return JSON.
    }
    throw new Error(`GitHub could not complete the request: ${message}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function getGitHubUser(token: string) {
  return githubFetch<{ id: number; login: string; name: string | null; avatar_url: string }>(
    "/user",
    token,
  );
}

export async function listAvailableRepositories(userToken: string): Promise<AvailableRepository[]> {
  const installations = await githubFetch<{ installations: Array<{ id: number }> }>(
    "/user/installations?per_page=100",
    userToken,
  );
  const groups = await Promise.all(
    installations.installations.map(async (installation) => {
      const value = await githubFetch<{ repositories: GitHubRepository[] }>(
        `/user/installations/${installation.id}/repositories?per_page=100`,
        userToken,
      );
      return value.repositories.map((repository) => ({
        id: repository.id,
        installationId: installation.id,
        fullName: repository.full_name,
        private: repository.private,
        defaultBranch: repository.default_branch,
        url: repository.html_url,
        ownerAvatarUrl: repository.owner.avatar_url,
      }));
    }),
  );
  return groups.flat().sort((left, right) => left.fullName.localeCompare(right.fullName));
}

export async function findAvailableRepository(
  userToken: string,
  fullName: string,
): Promise<AvailableRepository> {
  const repositories = await listAvailableRepositories(userToken);
  const repository = repositories.find(
    (item) => item.fullName.toLowerCase() === fullName.toLowerCase(),
  );
  if (!repository) {
    throw new Error(
      "Forgewatch is not installed on that repository, or your GitHub account cannot access it.",
    );
  }
  return repository;
}

async function appJwt(): Promise<string> {
  const env = githubAppEnv();
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({})
    .setProtectedHeader({ alg: "RS256" })
    .setIssuedAt(now - 60)
    .setExpirationTime(now + 9 * 60)
    .setIssuer(env.appId)
    .sign(createPrivateKey(env.privateKey));
}

export async function createInstallationToken(
  installationId: number,
  repositoryIds?: number[],
  permissions?: Record<string, "read" | "write">,
): Promise<string> {
  const token = await appJwt();
  const value = await githubFetch<{ token: string }>(
    `/app/installations/${installationId}/access_tokens`,
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...(repositoryIds?.length ? { repository_ids: repositoryIds } : {}),
        ...(permissions ? { permissions } : {}),
      }),
    },
  );
  return value.token;
}

export async function automationToken(): Promise<string> {
  const automation = automationRepository();
  const jwt = await appJwt();
  const installation = await githubFetch<{ id: number }>(
    `/repos/${automation.owner}/${automation.repository}/installation`,
    jwt,
  );
  const value = await githubFetch<{ token: string }>(
    `/app/installations/${installation.id}/access_tokens`,
    jwt,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repositories: [automation.repository],
        permissions: { actions: "write", metadata: "read" },
      }),
    },
  );
  return value.token;
}

export async function resolveCommit(
  fullName: string,
  branch: string,
  token: string,
): Promise<string> {
  const value = await githubFetch<{ sha: string }>(
    `/repos/${fullName}/commits/${encodeURIComponent(branch)}`,
    token,
  );
  if (!/^[0-9a-f]{40}$/.test(value.sha)) throw new Error("GitHub returned an invalid commit ID.");
  return value.sha;
}

export async function dispatchScan(input: {
  repository: AvailableRepository;
  branch: string;
  commit: string;
  trigger: "manual" | "schedule";
}): Promise<{ runId: number; runUrl: string }> {
  const automation = automationRepository();
  const token = await automationToken();
  const [owner, repository] = input.repository.fullName.split("/");
  const result = await githubFetch<{
    workflow_run_id: number;
    html_url: string;
  }>(
    `/repos/${automation.owner}/${automation.repository}/actions/workflows/scan.yml/dispatches`,
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ref: automation.ref,
        inputs: {
          owner,
          repository,
          revision: input.commit,
          ref: input.branch,
          default_branch: input.repository.defaultBranch,
          trigger: input.trigger,
        },
      }),
    },
  );
  if (!Number.isSafeInteger(result.workflow_run_id) || !result.html_url) {
    throw new Error("GitHub accepted the scan but did not return its run details.");
  }
  return { runId: result.workflow_run_id, runUrl: result.html_url };
}

export async function getWorkflowRun(runId: number, token: string): Promise<WorkflowRun> {
  const automation = automationRepository();
  return githubFetch<WorkflowRun>(
    `/repos/${automation.owner}/${automation.repository}/actions/runs/${runId}`,
    token,
  );
}

export async function downloadReport(runId: number, token: string): Promise<ArrayBuffer> {
  const automation = automationRepository();
  const artifacts = await githubFetch<{
    artifacts: Array<{ id: number; name: string; expired: boolean }>;
  }>(
    `/repos/${automation.owner}/${automation.repository}/actions/runs/${runId}/artifacts?per_page=100`,
    token,
  );
  const artifact = artifacts.artifacts.find(
    (item) => item.name.startsWith("forgewatch-") && !item.expired,
  );
  if (!artifact) throw new Error("The report is not ready yet, or its artifact has expired.");
  const response = await fetch(
    `${API}/repos/${automation.owner}/${automation.repository}/actions/artifacts/${artifact.id}/zip`,
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "Forgewatch",
      },
      cache: "no-store",
    },
  );
  if (!response.ok) throw new Error("GitHub could not download the scan report.");
  return response.arrayBuffer();
}
