"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";

interface Options<T> {
  /** Re-fetch every N ms while `pollWhile(data)` returns true. */
  pollMs?: number;
  pollWhile?: (data: T) => boolean;
  enabled?: boolean;
}

export interface ApiState<T> {
  data: T | undefined;
  error: ApiError | null;
  /** True until the request for the current dependencies has settled. */
  loading: boolean;
  reload: () => Promise<void>;
  setData: (data: T) => void;
}

/** Minimal fetch-on-mount hook with optional status polling (no external data library). */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[], options: Options<T> = {}): ApiState<T> {
  const { pollMs, pollWhile, enabled = true } = options;
  const key = JSON.stringify(deps);
  const [data, setData] = useState<T>();
  const [error, setError] = useState<ApiError | null>(null);
  const [settledKey, setSettledKey] = useState<string | null>(null);
  const fetcherRef = useRef(fetcher);
  const latestRequest = useRef(0);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const run = useCallback(async (forKey: string) => {
    const id = ++latestRequest.current;
    try {
      const result = await fetcherRef.current();
      if (id !== latestRequest.current) return;
      setData(result);
      setError(null);
    } catch (err) {
      if (id !== latestRequest.current) return;
      setError(err instanceof ApiError ? err : new ApiError("Unexpected error.", 0, "unknown"));
    } finally {
      if (id === latestRequest.current) setSettledKey(forKey);
    }
  }, []);

  useEffect(() => {
    if (enabled) void run(key);
  }, [enabled, key, run]);

  useEffect(() => {
    if (!pollMs || !pollWhile || data === undefined || !pollWhile(data)) return;
    const timer = window.setTimeout(() => void run(key), pollMs);
    return () => window.clearTimeout(timer);
  }, [data, key, pollMs, pollWhile, run]);

  const reload = useCallback(() => run(key), [key, run]);
  return { data, error, loading: enabled && settledKey !== key, reload, setData };
}
