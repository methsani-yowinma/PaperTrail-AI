/**
 * Public (browser-visible) configuration. Only NEXT_PUBLIC_* values belong here.
 * The Supabase anon key is designed to be public; it is protected by Row Level Security.
 * Never put the service-role key or the Gemini key in a NEXT_PUBLIC_* variable.
 */
export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** True when Supabase Auth is configured. Otherwise the app runs in explicit local dev mode. */
export const authEnabled = Boolean(supabaseUrl && supabaseAnonKey);
