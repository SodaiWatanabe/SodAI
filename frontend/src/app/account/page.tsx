import Link from "next/link";
import { redirect } from "next/navigation";

import { LogoutButton } from "@/components/auth/logout-button";
import { SodAIAccountPanel } from "@/components/auth/sodai-account-panel";
import { SiteLogo } from "@/components/site-logo";
import { getCurrentSession } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const session = await getCurrentSession();
  if (!session) {
    redirect("/auth/login");
  }

  const { user } = session;

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-8 sm:px-8">
      <div className="mx-auto w-full max-w-6xl">
        <header className="flex items-center justify-between">
          <SiteLogo />
          <LogoutButton />
        </header>

        <div className="mt-14 grid gap-8 lg:grid-cols-[0.7fr_1.3fr]">
          <section>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-600">
              Account
            </p>
            <h1 className="mt-4 text-4xl font-semibold tracking-[-0.045em] text-slate-950">
              {user.name}
            </h1>
            <p className="mt-4 max-w-sm text-base leading-7 text-slate-500">
              ここがSodAIのアカウント基盤です。今後、会話・クレジット・モデルアクセスがこのアカウントに接続されます。
            </p>
            <Link
              href="/"
              className="mt-8 inline-flex text-sm font-semibold text-blue-600 hover:text-blue-700"
            >
              ← トップへ戻る
            </Link>
          </section>

          <div className="space-y-5">
            <section className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-[0_20px_60px_-38px_rgba(15,23,42,0.28)] sm:p-8">
              <div className="flex items-start justify-between gap-6">
                <div>
                  <p className="text-sm font-medium text-slate-500">メールアドレス</p>
                  <p className="mt-2 break-all text-lg font-semibold text-slate-950">
                    {user.email}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                    user.emailVerified
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-amber-50 text-amber-700"
                  }`}
                >
                  {user.emailVerified ? "確認済み" : "未確認"}
                </span>
              </div>
            </section>

            <section className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-[0_20px_60px_-38px_rgba(15,23,42,0.28)] sm:p-8">
              <p className="text-sm font-medium text-slate-500">SodAI認証ID</p>
              <code className="mt-3 block overflow-x-auto rounded-xl bg-slate-950 px-4 py-3 text-xs text-slate-300">
                {user.id}
              </code>
              <p className="mt-4 text-xs leading-5 text-slate-400">
                このIDは認証上の主体を表します。会話やクレジットは別のSodAI内部IDへ関連付けるため、将来の認証基盤移行にも追従できます。
              </p>
            </section>

            <SodAIAccountPanel />
          </div>
        </div>
      </div>
    </main>
  );
}
