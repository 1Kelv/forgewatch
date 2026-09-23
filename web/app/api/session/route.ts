import { requireSession } from "@/lib/session";

export async function GET() {
  try {
    const session = await requireSession();
    return Response.json({
      authenticated: true,
      user: { login: session.login, name: session.name, avatarUrl: session.avatarUrl },
    });
  } catch {
    return Response.json({ authenticated: false });
  }
}
