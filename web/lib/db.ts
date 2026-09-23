import postgres from "postgres";

import { databaseUrl } from "@/lib/env";

let client: ReturnType<typeof postgres> | undefined;

export function db() {
  if (!client) {
    client = postgres(databaseUrl(), {
      max: 2,
      idle_timeout: 20,
      connect_timeout: 15,
      prepare: false,
    });
  }
  return client;
}
