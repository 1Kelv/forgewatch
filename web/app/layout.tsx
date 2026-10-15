import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { themeBootstrap } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Forgewatch",
  description: "Plain-English security checks for GitHub repositories.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script>{themeBootstrap}</script></head>
      <body>{children}</body>
    </html>
  );
}
