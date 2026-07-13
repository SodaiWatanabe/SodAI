"use client";

export function SettingsReloadButton() {
  return (
    <button
      type="button"
      className="mt-5 inline-flex h-10 items-center rounded-full border border-[var(--border)] px-4 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
      onClick={() => window.location.reload()}
    >
      再読み込み
    </button>
  );
}
