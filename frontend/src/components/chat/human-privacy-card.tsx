import { ShieldAlert } from "lucide-react";

export const HUMAN_PRIVACY_NOTICE =
  "個人情報と機密情報は含めないでください。";

export function HumanPrivacyCard() {
  return (
    <aside
      role="note"
      aria-label="Humanへの送信について"
      className="mt-3 flex items-center gap-3 rounded-2xl border border-[var(--divider)] bg-[var(--surface)] px-4 py-3 text-left"
    >
      <span
        aria-hidden="true"
        className="grid size-8 shrink-0 place-items-center rounded-full bg-[var(--hover)] text-[var(--muted)]"
      >
        <ShieldAlert className="size-4" strokeWidth={1.8} />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-[var(--text)]">
          Humanへの送信
        </span>
        <span className="mt-0.5 block text-xs leading-5 text-[var(--muted)]">
          {HUMAN_PRIVACY_NOTICE}
        </span>
      </span>
    </aside>
  );
}
