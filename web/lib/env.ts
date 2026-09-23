function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is not configured.`);
  return value;
}

export function appUrl(): string {
  return required("APP_URL").replace(/\/$/, "");
}

export function githubAppEnv() {
  return {
    appId: required("GITHUB_APP_ID"),
    clientId: required("GITHUB_APP_CLIENT_ID"),
    clientSecret: required("GITHUB_APP_CLIENT_SECRET"),
    privateKey: required("GITHUB_APP_PRIVATE_KEY").replace(/\\n/g, "\n"),
  };
}

export function automationRepository(): { owner: string; repository: string; ref: string } {
  const parts = required("FORGEWATCH_AUTOMATION_REPOSITORY").split("/");
  if (parts.length !== 2 || !parts[0] || !parts[1]) {
    throw new Error("FORGEWATCH_AUTOMATION_REPOSITORY must use owner/repository format.");
  }
  return {
    owner: parts[0],
    repository: parts[1],
    ref: process.env.FORGEWATCH_AUTOMATION_REF?.trim() || "main",
  };
}

export function allowedGitHubLogins(): Set<string> {
  return new Set(
    required("FORGEWATCH_ALLOWED_GITHUB_LOGINS")
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  );
}

export function sessionSecret(): string {
  const value = required("SESSION_SECRET");
  if (value.length < 32) throw new Error("SESSION_SECRET must contain at least 32 characters.");
  return value;
}

export function databaseUrl(): string {
  return required("DATABASE_URL");
}
