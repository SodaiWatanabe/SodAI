"use client";

import { Check, ChevronDown } from "lucide-react";

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { AvailableModel } from "@/lib/chat/types";

type ModelSelectorProps = {
  disabled?: boolean;
  model: AvailableModel["id"];
  models: AvailableModel[];
  onChange: (model: AvailableModel["id"]) => void;
  showPseudoBadge?: boolean;
};

const archiveFallback: AvailableModel = {
  id: "archive",
  name: "Archive",
  description: "SodAIのアーカイブモデル",
};

export function ModelSelector({
  disabled = false,
  model,
  models,
  onChange,
  showPseudoBadge = false,
}: ModelSelectorProps) {
  const options = models.length > 0 ? models : [archiveFallback];
  const selected = options.find((option) => option.id === model) ?? options[0];

  return (
    <Popover placement="bottom-start" gutter={6}>
      <PopoverTrigger
        disabled={disabled}
        aria-label={`モデル: ${selected.name}`}
        className="group flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-[13px] font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:cursor-default disabled:opacity-50"
      >
        <span>{selected.name}</span>
        {showPseudoBadge ? (
          <span className="rounded-full bg-[var(--control-background)] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[var(--muted)]">
            Pseudo
          </span>
        ) : null}
        <ChevronDown
          aria-hidden="true"
          className="size-3.5 text-[var(--muted)] transition-transform group-aria-expanded:rotate-180"
        />
      </PopoverTrigger>

      <PopoverContent
        role="radiogroup"
        aria-label="モデル"
        className="w-[min(19rem,calc(100vw-1.5rem))] rounded-[18px] p-1.5"
      >
        {options.map((option) => {
          const checked = option.id === selected.id;
          return (
            <PopoverClose
              key={option.id}
              role="radio"
              aria-checked={checked}
              className={`flex w-full items-start gap-3 rounded-[13px] px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] ${
                checked ? "bg-[var(--hover)]" : "hover:bg-[var(--hover-soft)]"
              }`}
              onClick={() => onChange(option.id)}
            >
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-medium text-[var(--text)]">
                  {option.name}
                </span>
                <span className="mt-0.5 block text-[11px] leading-4 text-[var(--muted)]">
                  {option.description}
                </span>
              </span>
              <span className="grid size-5 shrink-0 place-items-center text-[var(--text)]">
                {checked ? <Check aria-hidden="true" className="size-3.5" /> : null}
              </span>
            </PopoverClose>
          );
        })}
      </PopoverContent>
    </Popover>
  );
}
