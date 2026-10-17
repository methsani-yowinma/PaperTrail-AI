import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { authEnabled, supabaseAnonKey, supabaseUrl } from "@/lib/config";

/** Server-side Supabase client bound to the request cookies (route handlers only). */
export async function getServerSupabase() {
  if (!authEnabled) return null;
  const cookieStore = await cookies();
  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) cookieStore.set(name, value, options);
        } catch {
          // Called from a context where cookies are read-only; proxy.ts refreshes sessions.
        }
      },
    },
  });
}
