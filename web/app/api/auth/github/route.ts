import { NextResponse } from "next/server";

import { appUrl, githubAppEnv } from "@/lib/env";
import { createOAuthState } from "@/lib/session";

export async function GET() {
  const state = await createOAuthState();
  const url = new URL("https://github.com/login/oauth/authorize");
  url.searchParams.set("client_id", githubAppEnv().clientId);
  url.searchParams.set("redirect_uri", `${appUrl()}/api/auth/callback`);
  url.searchParams.set("state", state);
  url.searchParams.set("allow_signup", "false");
  return NextResponse.redirect(url);
}
