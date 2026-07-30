"use client";

import { Check, ChevronDown } from "lucide-react";

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { formatReasoningTimeLimit } from "@/lib/chat/reasoning-effort";
import type {
  AvailableAnswerer,
  ReasoningEffort,
} from "@/lib/chat/types";

type ReasoningEffortSelectorProps = {
  onChange: (effort: ReasoningEffort) => void;
  options: AvailableAnswerer["reasoning_efforts"];
  value: ReasoningEffort;
};

export function ReasoningEffortSelector({
  onChange,
  options,
  value,
}: ReasoningEffortSelectorProps) {
  const selected = options.find((option) => option.id === value);

  return (
    <Popover placement="top-end" gutter={8}>
      <PopoverTrigger
        aria-label={`思考の深さ: ${selected?.name ?? value}`}
        className="group flex h-10 items-center gap-1 rounded-full px-4 text-[16px] font-medium text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
      >
        <span>{selected?.name ?? value}</span>
        <ChevronDown
          aria-hidden="true"
          className="size-3.5 transition-transform group-aria-expanded:rotate-180"
        />
      </PopoverTrigger>
      <PopoverContent
        role="menu"
        aria-label="思考の深さ"
        className="w-56"
      >
        <p className="px-3 pb-1.5 pt-1 text-xs font-medium text-[var(--muted)]">
          思考の深さ
        </p>
        <div className="grid gap-0.5">
          {options.map((option) => {
            const checked = option.id === value;
            return (
              <PopoverClose
                key={option.id}
                role="menuitemradio"
                aria-checked={checked}
                className={`flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] ${
                  checked ? "bg-[var(--hover)]" : ""
                }`}
                onClick={() => onChange(option.id)}
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-[var(--text)]">
                    {option.name}
                  </span>
                  <span className="mt-0.5 block text-xs leading-4 text-[var(--muted)]">
                    {formatReasoningTimeLimit(
                      option.execution_time_limit_seconds,
                    )}
                  </span>
                </span>
                <span className="grid size-5 shrink-0 place-items-center text-[var(--text)]">
                  {checked ? (
                    <Check aria-hidden="true" className="size-3.5" />
                  ) : null}
                </span>
              </PopoverClose>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
