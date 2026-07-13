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
  model?: AvailableModel["id"];
  models: AvailableModel[];
  onChange: (model: AvailableModel["id"]) => void;
};

export function ModelSelector({
  model,
  models,
  onChange,
}: ModelSelectorProps) {
  const selected =
    models.find((option) => option.id === model) ??
    models.find((option) => option.is_default) ??
    models[0];
  const label = selected?.name ?? model ?? "モデル";

  return (
    <Popover placement="bottom-start" gutter={6}>
      <PopoverTrigger
        disabled={models.length === 0}
        aria-label={`モデル: ${label}`}
        className="group flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:cursor-default disabled:opacity-50"
      >
        <span>{label}</span>
        <ChevronDown
          aria-hidden="true"
          className="size-3.5 text-[var(--muted)] transition-transform group-aria-expanded:rotate-180"
        />
      </PopoverTrigger>

      <PopoverContent
        role="radiogroup"
        aria-label="モデル"
        className="w-[min(19rem,calc(100vw-1.5rem))] rounded-[18px]"
      >
        <div className="grid gap-0.5">
          {models.map((option) => {
            const checked = option.id === selected?.id;
            return (
              <PopoverClose
                key={option.id}
                role="radio"
                aria-checked={checked}
                className={`flex w-full items-start gap-3 rounded-[13px] px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] ${
                  checked ? "bg-[var(--hover)]" : ""
                }`}
                onClick={() => onChange(option.id)}
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-[var(--text)]">
                    {option.name}
                  </span>
                  <span className="mt-0.5 block text-xs leading-4 text-[var(--muted)]">
                    {option.description}
                  </span>
                </span>
                <span className="grid size-5 shrink-0 place-items-center text-[var(--text)]">
                  {checked ? <Check aria-hidden="true" className="size-3.5" /> : null}
                </span>
              </PopoverClose>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
