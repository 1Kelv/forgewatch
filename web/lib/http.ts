import { appUrl } from "@/lib/env";

export function requireSameOrigin(request: Request): void {
  const origin = request.headers.get("origin");
  if (!origin || origin !== new URL(appUrl()).origin) {
    throw new Error("The request did not come from the Forgewatch dashboard.");
  }
}

export function errorResponse(error: unknown, fallbackStatus = 400): Response {
  const message = error instanceof Error ? error.message : "The request could not be completed.";
  const status = /sign in|session expired|not allowed/i.test(message) ? 401 : fallbackStatus;
  return Response.json({ error: message }, { status });
}
