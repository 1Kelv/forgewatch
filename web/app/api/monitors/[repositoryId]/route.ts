import { z } from "zod";

import { errorResponse, requireSameOrigin } from "@/lib/http";
import { removeMonitor, updateFrequency } from "@/lib/monitors";
import { FREQUENCIES } from "@/lib/repository";
import { requireSession } from "@/lib/session";

const schema = z.object({ frequency: z.enum(FREQUENCIES) });

function repositoryId(value: string): string {
  if (!/^\d+$/.test(value)) throw new Error("The repository ID is invalid.");
  return value;
}

export async function PATCH(
  request: Request,
  context: { params: Promise<{ repositoryId: string }> },
) {
  try {
    requireSameOrigin(request);
    const session = await requireSession();
    const params = await context.params;
    const input = schema.parse(await request.json());
    const monitor = await updateFrequency(
      session.githubUserId,
      repositoryId(params.repositoryId),
      input.frequency,
    );
    return Response.json({ monitor });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function DELETE(
  request: Request,
  context: { params: Promise<{ repositoryId: string }> },
) {
  try {
    requireSameOrigin(request);
    const session = await requireSession();
    const params = await context.params;
    await removeMonitor(session.githubUserId, repositoryId(params.repositoryId));
    return Response.json({ removed: true });
  } catch (error) {
    return errorResponse(error);
  }
}
