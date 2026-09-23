import { createPrivateKey } from "node:crypto";

import { SignJWT } from "jose";

import { automationRepository, githubAppEnv } from "@/lib/env";

const API = "https://api.github.com";
const API_VERSION = "2026-03-10";
const PAGE_SIZE = 100;
const MAX_PAGES = 20;
const TARGET_WORKFLOW = "forgewatch.yml";

class GitHubRequestError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

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
    throw new GitHubRequestError(
      response.status,
      `GitHub could not complete the request: ${message}`,
    );
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
  const installations: Array<{ id: number }> = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const value = await githubFetch<{ installations: Array<{ id: number }> }>(
      `/user/installations?per_page=${PAGE_SIZE}&page=${page}`,
      userToken,
    );
    installations.push(...value.installations);
    if (value.installations.length < PAGE_SIZE) break;
    if (page === MAX_PAGES) {
      throw new Error("Too many GitHub App installations were returned. Contact the Forgewatch operator.");
    }
  }
  const groups = await Promise.all(
    installations.map(async (installation) => {
      const repositories: GitHubRepository[] = [];
      for (let page = 1; page <= MAX_PAGES; page += 1) {
        const value = await githubFetch<{ repositories: GitHubRepository[] }>(
          `/user/installations/${installation.id}/repositories?per_page=${PAGE_SIZE}&page=${page}`,
          userToken,
        );
        repositories.push(...value.repositories);
        if (value.repositories.length < PAGE_SIZE) break;
        if (page === MAX_PAGES) {
          throw new Error("Too many approved repositories were returned. Contact the Forgewatch operator.");
        }
      }
      return repositories.map((repository) => ({
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
  const automation = automationRepository();
  const automationName = `${automation.owner}/${automation.repository}`.toLowerCase();
  return groups
    .flat()
    .filter((repository) => repository.fullName.toLowerCase() !== automationName)
    .sort((left, right) => left.fullName.localeCompare(right.fullName));
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
        permissions: { actions: "read", metadata: "read" },
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
}, token: string): Promise<{ runId: number; runUrl: string }> {
  let result: { workflow_run_id: number; html_url: string };
  try {
    result = await githubFetch<{
      workflow_run_id: number;
      html_url: string;
    }>(
      `/repos/${input.repository.fullName}/actions/workflows/${TARGET_WORKFLOW}/dispatches`,
      token,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ref: input.repository.defaultBranch,
          inputs: {
            revision: input.commit,
            ref: input.branch,
            default_branch: input.repository.defaultBranch,
            trigger: input.trigger,
          },
        }),
      },
    );
  } catch (error) {
    if (error instanceof GitHubRequestError && error.status === 404) {
      throw new Error(
        "This repository is approved, but its Forgewatch workflow is not installed yet. Open the setup guide, add .github/workflows/forgewatch.yml, then try again.",
      );
    }
    throw error;
  }
  if (!Number.isSafeInteger(result.workflow_run_id) || !result.html_url) {
    throw new Error("GitHub accepted the scan but did not return its run details.");
  }
  return { runId: result.workflow_run_id, runUrl: result.html_url };
}

export async function getWorkflowRun(
  fullName: string,
  runId: number,
  token: string,
): Promise<WorkflowRun> {
  return githubFetch<WorkflowRun>(
    `/repos/${fullName}/actions/runs/${runId}`,
    token,
  );
}

export async function downloadReport(
  fullName: string,
  runId: number,
  token: string,
): Promise<ArrayBuffer> {
  const artifacts = await githubFetch<{
    artifacts: Array<{ id: number; name: string; expired: boolean }>;
  }>(
    `/repos/${fullName}/actions/runs/${runId}/artifacts?per_page=100`,
    token,
  );
  const artifact = artifacts.artifacts.find(
    (item) => item.name.startsWith("forgewatch-") && !item.expired,
  );
  if (!artifact) throw new Error("The report is not ready yet, or its artifact has expired.");
  const response = await fetch(
    `${API}/repos/${fullName}/actions/artifacts/${artifact.id}/zip`,
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
