import { HealthStatus } from "@/components/health-status";

const layers = [
  {
    name: "Router",
    path: "backend/app/routers",
    description: "HTTP の入口とレスポンス定義を扱います。",
  },
  {
    name: "Service",
    path: "backend/app/services",
    description: "ユースケースとビジネスロジックを集約します。",
  },
  {
    name: "Schema",
    path: "backend/app/schemas",
    description: "API の入出力を型として管理します。",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen px-6 py-8 sm:px-10 lg:px-16">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-16">
        <header className="flex items-center justify-between border-b border-slate-200 pb-6">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl bg-slate-950 text-sm font-semibold text-white">
              S
            </span>
            <span className="font-semibold tracking-tight text-slate-950">SodAI</span>
          </div>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-500 shadow-sm">
            scaffold v0.1
          </span>
        </header>

        <section className="grid items-end gap-10 lg:grid-cols-[1.3fr_0.7fr]">
          <div>
            <p className="mb-5 text-sm font-semibold uppercase tracking-[0.2em] text-blue-600">
              AI application workspace
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-[-0.04em] text-slate-950 sm:text-6xl">
              SodAI のプロダクト開発を、ここから始める。
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">
              FastAPI と Next.js を分離した、機能追加しやすい最小構成です。
              これから定義するプロダクト要件を、API と UI に順番に積み上げていきます。
            </p>
          </div>
          <HealthStatus />
        </section>

        <section>
          <div className="mb-6 flex items-end justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-blue-600">Backend boundaries</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
                責務ごとに分離した API 構成
              </h2>
            </div>
            <a
              className="hidden text-sm font-medium text-slate-500 transition hover:text-slate-950 sm:block"
              href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/docs`}
              target="_blank"
              rel="noreferrer"
            >
              API Docs ↗
            </a>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {layers.map((layer, index) => (
              <article
                key={layer.name}
                className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_12px_40px_-28px_rgba(15,23,42,0.35)]"
              >
                <div className="mb-8 flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-950">{layer.name}</span>
                  <span className="font-mono text-xs text-slate-400">0{index + 1}</span>
                </div>
                <p className="mb-4 text-sm leading-6 text-slate-600">{layer.description}</p>
                <code className="text-xs text-slate-400">{layer.path}</code>
              </article>
            ))}
          </div>
        </section>

        <footer className="border-t border-slate-200 py-6 text-sm text-slate-400">
          FastAPI · Next.js · TypeScript · Tailwind CSS
        </footer>
      </div>
    </main>
  );
}
