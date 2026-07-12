import Link from "next/link";

export function SiteLogo() {
  return (
    <Link
      href="/"
      className="group inline-flex items-center gap-3 font-semibold tracking-tight text-slate-950"
      aria-label="SodAI トップへ"
    >
      <span className="grid size-10 place-items-center rounded-2xl bg-slate-950 text-sm text-white shadow-lg shadow-slate-300 transition-transform group-hover:-rotate-3">
        S
      </span>
      <span className="text-lg">SodAI</span>
    </Link>
  );
}
