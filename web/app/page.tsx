import { Dashboard } from "@/components/dashboard";

export default function Home() {
  return <Dashboard appSlug={process.env.NEXT_PUBLIC_GITHUB_APP_SLUG || ""} />;
}
