import { createHash, randomBytes } from "node:crypto";

import { cookies } from "next/headers";
import { EncryptJWT, jwtDecrypt } from "jose";

import { allowedGitHubLogins, githubAppEnv, sessionSecret } from "@/lib/env";

const SESSION_COOKIE = "forgewatch_session";
const STATE_COOKIE = "forgewatch_oauth_state";

export type Session = {
  githubUserId: number;
  login: string;
  name: string;
  avatarUrl: string;
  accessToken: string;
  refreshToken?: string;
  accessTokenExpiresAt: number;
};

function key(): Uint8Array {
  return createHash("sha256").update(sessionSecret()).digest();
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}

export async function saveSession(session: Session): Promise<void> {
  const encrypted = await new EncryptJWT({ ...session })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    .setExpirationTime("180d")
    .encrypt(key());
  (await cookies()).set(SESSION_COOKIE, encrypted, cookieOptions(180 * 24 * 60 * 60));
}

export async function clearSession(): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, "", cookieOptions(0));
}

async function readSession(): Promise<Session | null> {
  const value = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!value) return null;
  try {
    const { payload } = await jwtDecrypt(value, key());
    const session = payload as unknown as Session;
    if (
      !Number.isSafeInteger(session.githubUserId) ||
      !session.login ||
      !session.accessToken ||
      !Number.isFinite(session.accessTokenExpiresAt)
    ) {
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

async function refreshSession(session: Session): Promise<Session | null> {
  if (!session.refreshToken) return null;
  const env = githubAppEnv();
  const response = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: env.clientId,
      client_secret: env.clientSecret,
      grant_type: "refresh_token",
      refresh_token: session.refreshToken,
    }),
    cache: "no-store",
  });
  const value = (await response.json()) as {
    access_token?: string;
    expires_in?: number;
    refresh_token?: string;
    error_description?: string;
  };
  if (!response.ok || !value.access_token) return null;
  const refreshed: Session = {
    ...session,
    accessToken: value.access_token,
    refreshToken: value.refresh_token || session.refreshToken,
    accessTokenExpiresAt: Date.now() + (value.expires_in || 8 * 60 * 60) * 1000,
  };
  await saveSession(refreshed);
  return refreshed;
}

export async function requireSession(): Promise<Session> {
  let session = await readSession();
  if (!session) throw new Error("Sign in with GitHub to continue.");
  if (session.accessTokenExpiresAt <= Date.now() + 60_000) {
    session = await refreshSession(session);
    if (!session) {
      await clearSession();
      throw new Error("Your GitHub session expired. Sign in again.");
    }
  }
  if (!allowedGitHubLogins().has(session.login.toLowerCase())) {
    await clearSession();
    throw new Error("This GitHub account is not allowed to use this Forgewatch dashboard.");
  }
  return session;
}

export async function createOAuthState(): Promise<string> {
  const state = randomBytes(32).toString("base64url");
  (await cookies()).set(STATE_COOKIE, state, cookieOptions(10 * 60));
  return state;
}

export async function consumeOAuthState(received: string | null): Promise<boolean> {
  const store = await cookies();
  const expected = store.get(STATE_COOKIE)?.value;
  store.set(STATE_COOKIE, "", cookieOptions(0));
  if (!received || !expected || received.length !== expected.length) return false;
  return Buffer.from(received).equals(Buffer.from(expected));
}
