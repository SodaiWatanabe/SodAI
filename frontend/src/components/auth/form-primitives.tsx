import type { ComponentProps, ReactNode } from "react";

export function FormField({
  hint,
  label,
  ...inputProps
}: ComponentProps<"input"> & { hint?: string; label: string }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input
        {...inputProps}
        className="mt-2 block w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-base text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 disabled:cursor-not-allowed disabled:bg-slate-50"
      />
      {hint ? (
        <span className="mt-2 block text-xs font-normal leading-5 text-slate-400">
          {hint}
        </span>
      ) : null}
    </label>
  );
}

export function SubmitButton({
  children,
  pending,
}: {
  children: ReactNode;
  pending: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex w-full items-center justify-center rounded-xl bg-slate-950 px-4 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-200 transition hover:bg-slate-800 focus:outline-none focus:ring-4 focus:ring-slate-950/15 disabled:cursor-wait disabled:opacity-60"
    >
      {pending ? "処理中…" : children}
    </button>
  );
}

export function FormNotice({
  children,
  kind,
}: {
  children: ReactNode;
  kind: "error" | "success";
}) {
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`rounded-xl border px-4 py-3 text-sm leading-6 ${
        kind === "error"
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : "border-emerald-200 bg-emerald-50 text-emerald-700"
      }`}
    >
      {children}
    </div>
  );
}
