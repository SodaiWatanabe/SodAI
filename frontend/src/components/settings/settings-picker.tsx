"use client";

import { Check, ChevronDown } from "lucide-react";

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

export type SettingsPickerOption<Value extends string> = {
  label: string;
  value: Value;
};

export function SettingsPicker<Value extends string>({
  label,
  onValueChange,
  options,
  value,
}: {
  label: string;
  onValueChange: (value: Value) => void;
  options: readonly SettingsPickerOption<Value>[];
  value: Value;
}) {
  const selected = options.find((option) => option.value === value) ?? options[0];

  if (!selected) return null;

  return (
    <Popover placement="bottom-end" gutter={6}>
      <PopoverTrigger
        aria-label={`${label}: ${selected.label}`}
        className="group flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
      >
        <span>{selected.label}</span>
        <ChevronDown
          aria-hidden="true"
          className="size-3.5 text-[var(--muted)] transition-transform group-aria-expanded:rotate-180"
        />
      </PopoverTrigger>

      <PopoverContent role="menu" aria-label={label} className="w-52">
        <div className="grid gap-0.5">
          {options.map((option) => {
            const checked = option.value === value;

            return (
              <PopoverClose
                key={option.value}
                role="menuitemradio"
                aria-checked={checked}
                className={`flex w-full items-center gap-3 rounded-[13px] px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] ${
                  checked ? "bg-[var(--hover)]" : ""
                }`}
                onClick={() => onValueChange(option.value)}
              >
                <span className="min-w-0 flex-1 text-sm font-medium text-[var(--text)]">
                  {option.label}
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
