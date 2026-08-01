"use client";

import type { HumanAnswerSummary } from "@/lib/human/types";

export function HumanAnswerListItem({
  active,
  answer,
  disabled,
  onSelect,
}: {
  active: boolean;
  answer: HumanAnswerSummary;
  disabled: boolean;
  onSelect: () => void;
}) {
  const rowTone = active
    ? "bg-[var(--hover)] text-[var(--text)]"
    : "text-[var(--muted)] hover:bg-[var(--hover)] hover:text-[var(--text)]";

  return (
    <div className={`relative flex h-9 items-center rounded-xl ${rowTone}`}>
      <button
        type="button"
        title={
          disabled
            ? "回答中は履歴を開けません"
            : answer.prompt_preview
        }
        aria-current={active ? "page" : undefined}
        disabled={disabled}
        className="h-full min-w-0 flex-1 truncate rounded-xl px-2.5 text-left text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] disabled:cursor-not-allowed disabled:opacity-50"
        onClick={onSelect}
      >
        {answer.prompt_preview}
      </button>
    </div>
  );
}
