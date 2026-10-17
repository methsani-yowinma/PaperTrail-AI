import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { authEnabled, supabaseAnonKey, supabaseUrl } from "@/lib/config";

let client: SupabaseClient | null = null;

/** Browser Supabase client (auth only), or null in local development mode. */
export function getBrowserSupabase(): SupabaseClient | null {
  if (!authEnabled) return null;
  client ??= createBrowserClient(supabaseUrl, supabaseAnonKey);
  return client;
}
