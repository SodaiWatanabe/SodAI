import type { ReactNode } from "react";

import { SiteLogo } from "@/components/site-logo";

type AuthShellProps = {
  children: ReactNode;
  description: string;
  footer: ReactNode;
  title: string;
};

export function AuthShell({ children, description, footer, title }: AuthShellProps) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-50 px-5 py-8 sm:px-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.10),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(15,23,42,0.08),transparent_40%)]" />
      <div className="relative mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl flex-col">
        <header>
          <SiteLogo />
        </header>

        <div className="grid flex-1 items-center gap-12 py-12 lg:grid-cols-[0.9fr_1.1fr] lg:py-16">
          <section className="hidden max-w-lg lg:block">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-blue-600">
              Sovereign intelligence
            </p>
            <h2 className="mt-5 text-5xl font-semibold leading-[1.08] tracking-[-0.045em] text-slate-950">
              あなたの対話が、
              <br />
              次の知性を育てる。
            </h2>
            <p className="mt-7 max-w-md text-base leading-8 text-slate-600">
              SodAIは、モデル・会話・アカウントを自ら管理するAIプラットフォームです。
              認証情報はSodAIのPostgreSQLから外へ預けません。
            </p>
          </section>

          <section className="mx-auto w-full max-w-lg rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-[0_32px_90px_-38px_rgba(15,23,42,0.35)] backdrop-blur sm:p-10">
            <div className="mb-8">
              <p className="text-sm font-medium text-blue-600">SodAI Account</p>
              <h1 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-slate-950">
                {title}
              </h1>
              <p className="mt-3 text-sm leading-6 text-slate-500">{description}</p>
            </div>

            {children}

            <div className="mt-8 border-t border-slate-100 pt-6 text-center text-sm text-slate-500">
              {footer}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
