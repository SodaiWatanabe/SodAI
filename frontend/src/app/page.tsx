import Link from "next/link";

import { HealthStatus } from "@/components/health-status";
import { SiteLogo } from "@/components/site-logo";

const foundations = [
  {
    number: "01",
    title: "自分たちで所有する",
    description:
      "認証・会話・クレジットを自前のPostgreSQLで管理し、サービス事業者にデータの主権を預けません。",
  },
  {
    number: "02",
    title: "対話から育てる",
    description:
      "SodAI Birth 1との対話とフィードバックを、より良いモデルとデータセットへ還元します。",
  },
  {
    number: "03",
    title: "知性をひらく",
    description:
      "将来は多様なモデルをひとつのAPIから利用・公開できるAIプラットフォームへ発展します。",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden bg-slate-50">
      <div className="relative border-b border-slate-200 bg-white">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_70%_10%,rgba(37,99,235,0.10),transparent_34%)]" />
        <div className="relative mx-auto w-full max-w-7xl px-6 sm:px-10 lg:px-16">
          <header className="flex items-center justify-between py-6">
            <SiteLogo />
            <nav className="flex items-center gap-2" aria-label="アカウント">
              <Link
                href="/auth/login"
                className="rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
              >
                ログイン
              </Link>
              <Link
                href="/auth/register"
                className="rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-slate-200 transition hover:bg-slate-800"
              >
                はじめる
              </Link>
            </nav>
          </header>

          <section className="grid items-center gap-14 pb-20 pt-14 lg:grid-cols-[1.25fr_0.75fr] lg:pb-28 lg:pt-24">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700">
                <span className="size-1.5 rounded-full bg-blue-500" />
                SODAI BIRTH 1 · PRIVATE PREVIEW
              </div>
              <h1 className="mt-7 max-w-4xl text-5xl font-semibold leading-[1.02] tracking-[-0.055em] text-slate-950 sm:text-7xl lg:text-[5.5rem]">
                自分たちのデータで、
                <span className="text-blue-600">知性を育てる。</span>
              </h1>
              <p className="mt-8 max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">
                SodAIは、蒼大がゼロから訓練する完全自作LLMと、その周囲に広がるAI・データプラットフォームです。
                まずは、リアルタイムに対話できる場所から始めます。
              </p>
              <div className="mt-10 flex flex-wrap gap-3">
                <Link
                  href="/auth/register"
                  className="rounded-xl bg-blue-600 px-6 py-3.5 text-sm font-semibold text-white shadow-xl shadow-blue-200 transition hover:bg-blue-700"
                >
                  無料でアカウントを作成
                </Link>
                <Link
                  href="/account"
                  className="rounded-xl border border-slate-200 bg-white px-6 py-3.5 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
                >
                  アカウントを見る
                </Link>
              </div>
            </div>
            <HealthStatus />
          </section>
        </div>
      </div>

      <section className="mx-auto w-full max-w-7xl px-6 py-20 sm:px-10 lg:px-16 lg:py-28">
        <div className="max-w-2xl">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-blue-600">
            Principles
          </p>
          <h2 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-slate-950 sm:text-5xl">
            壮大な未来を、小さく確かな基盤から。
          </h2>
        </div>

        <div className="mt-12 grid gap-px overflow-hidden rounded-[2rem] border border-slate-200 bg-slate-200 lg:grid-cols-3">
          {foundations.map((foundation) => (
            <article key={foundation.number} className="bg-white p-7 sm:p-9">
              <span className="font-mono text-xs text-blue-600">{foundation.number}</span>
              <h3 className="mt-10 text-xl font-semibold tracking-tight text-slate-950">
                {foundation.title}
              </h3>
              <p className="mt-4 text-sm leading-7 text-slate-500">
                {foundation.description}
              </p>
            </article>
          ))}
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-6 py-8 text-sm text-slate-400 sm:flex-row sm:items-center sm:justify-between sm:px-10 lg:px-16">
          <span>SodAI · Sovereign AI Platform</span>
          <span>Next.js · Better Auth · FastAPI · PostgreSQL</span>
        </div>
      </footer>
    </main>
  );
}
