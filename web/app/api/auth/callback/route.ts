import { NextRequest, NextResponse } from "next/server";

import { appUrl, githubAppEnv, isGitHubLoginAllowed } from "@/lib/env";
import { getGitHubUser } from "@/lib/github";
import { consumeOAuthState, saveSession } from "@/lib/session";

export async function GET(request: NextRequest) {
  const destination = new URL("/", appUrl());
  try {
    const code = request.nextUrl.searchParams.get("code");
    const state = request.nextUrl.searchParams.get("state");
    if (!(await consumeOAuthState(state))) throw new Error("GitHub sign-in could not be verified.");
    if (!code) throw new Error("GitHub did not return an authorization code.");

    const env = githubAppEnv();
    const response = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: env.clientId,
        client_secret: env.clientSecret,
        code,
        redirect_uri: `${appUrl()}/api/auth/callback`,
      }),
      cache: "no-store",
    });
    const token = (await response.json()) as {
      access_token?: string;
      expires_in?: number;
      refresh_token?: string;
      error_description?: string;
    };
    if (!response.ok || !token.access_token) {
      throw new Error(token.error_description || "GitHub sign-in failed.");
    }
    const user = await getGitHubUser(token.access_token);
    if (!isGitHubLoginAllowed(user.login)) {
      throw new Error("This GitHub account is not allowed to use this Forgewatch dashboard.");
    }
    await saveSession({
      githubUserId: user.id,
      login: user.login,
      name: user.name || user.login,
      avatarUrl: user.avatar_url,
      accessToken: token.access_token,
      refreshToken: token.refresh_token,
      accessTokenExpiresAt: Date.now() + (token.expires_in || 8 * 60 * 60) * 1000,
    });
  } catch (error) {
    destination.searchParams.set(
      "error",
      error instanceof Error ? error.message : "GitHub sign-in failed.",
    );
  }
  return NextResponse.redirect(destination);
}
