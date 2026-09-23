import { listAvailableRepositories } from "@/lib/github";
import { errorResponse } from "@/lib/http";
import { requireSession } from "@/lib/session";

export async function GET() {
  try {
    const session = await requireSession();
    return Response.json({ repositories: await listAvailableRepositories(session.accessToken) });
  } catch (error) {
    return errorResponse(error);
  }
}
