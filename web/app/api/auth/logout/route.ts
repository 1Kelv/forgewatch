import { NextResponse } from "next/server";

import { appUrl } from "@/lib/env";
import { requireSameOrigin } from "@/lib/http";
import { clearSession } from "@/lib/session";

export async function POST(request: Request) {
  requireSameOrigin(request);
  await clearSession();
  return NextResponse.redirect(new URL("/", appUrl()), { status: 303 });
}
