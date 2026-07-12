"use client";

import { useEffect, useState } from "react";

import { getHealth, type HealthResponse } from "@/lib/api";

type HealthState =
  | { kind: "checking" }
  | { kind: "online"; data: HealthResponse }
  | { kind: "offline" };

export function HealthStatus() {
  const [state, setState] = useState<HealthState>({ kind: "checking" });

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then((data) => setState({ kind: "online", data }))
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        setState({ kind: "offline" });
      });

    return () => controller.abort();
  }, []);

  const isOnline = state.kind === "online";
  const label =
    state.kind === "checking"
      ? "接続確認中"
      : isOnline
        ? "API Online"
        : "API Offline";

  return (
    <aside className="rounded-2xl border border-slate-200 bg-slate-950 p-6 text-white shadow-xl shadow-slate-200/60">
      <div className="mb-10 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-300">Backend status</span>
        <span className="flex items-center gap-2 text-xs text-slate-300">
          <span
            className={`size-2 rounded-full ${
              state.kind === "checking"
                ? "animate-pulse bg-amber-400"
                : isOnline
                  ? "bg-emerald-400"
                  : "bg-rose-400"
            }`}
          />
          {label}
        </span>
      </div>
      <p className="text-2xl font-semibold tracking-tight">
        {isOnline ? state.data.service : "SodAI API"}
      </p>
      <p className="mt-2 text-sm leading-6 text-slate-400">
        {isOnline
          ? `${state.data.environment} 環境へ接続しています。`
          : "backend を起動すると接続状態が表示されます。"}
      </p>
      <code className="mt-8 block rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-400">
        GET /api/v1/health
      </code>
    </aside>
  );
}
