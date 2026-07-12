"use client";

import { useEffect, useState } from "react";

import { authenticatedApiFetch } from "@/lib/auth/api-client";

type SodAIAccount = {
  id: string;
  status: "active" | "suspended" | "disabled";
  display_name: string | null;
  email: string | null;
  email_verified: boolean;
};

type AccountState =
  | { kind: "loading" }
  | { kind: "ready"; account: SodAIAccount }
  | { kind: "error" };

const statusLabels: Record<SodAIAccount["status"], string> = {
  active: "利用可能",
  suspended: "一時停止中",
  disabled: "無効",
};

export function SodAIAccountPanel() {
  const [state, setState] = useState<AccountState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    authenticatedApiFetch("/api/v1/account/me", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Account API returned ${response.status}`);
        }
        return (await response.json()) as SodAIAccount;
      })
      .then((account) => setState({ kind: "ready", account }))
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        setState({ kind: "error" });
      });

    return () => controller.abort();
  }, []);

  if (state.kind === "loading") {
    return (
      <section className="rounded-[1.75rem] border border-blue-100 bg-blue-50/70 p-6 sm:p-8">
        <p className="text-sm font-semibold text-blue-700">SodAIアカウントを同期中…</p>
      </section>
    );
  }

  if (state.kind === "error") {
    return (
      <section className="rounded-[1.75rem] border border-amber-200 bg-amber-50 p-6 sm:p-8">
        <p className="font-semibold text-amber-900">アカウントAPIへ接続できませんでした</p>
        <p className="mt-2 text-sm leading-6 text-amber-700">
          FastAPIが起動していることを確認してからページを再読み込みしてください。
        </p>
      </section>
    );
  }

  const { account } = state;

  return (
    <section className="rounded-[1.75rem] border border-blue-100 bg-blue-50/70 p-6 sm:p-8">
      <div className="flex items-start justify-between gap-5">
        <div>
          <p className="text-sm font-medium text-blue-700">SodAI内部アカウント</p>
          <code className="mt-3 block break-all text-sm font-semibold text-slate-950">
            {account.id}
          </code>
        </div>
        <span className="shrink-0 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
          {statusLabels[account.status]}
        </span>
      </div>
      <p className="mt-5 text-xs leading-5 text-slate-500">
        このUUIDが会話・クレジット・フィードバックを所有します。認証プロバイダーを変更しても維持されます。
      </p>
    </section>
  );
}
