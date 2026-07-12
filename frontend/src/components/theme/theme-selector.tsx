"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useId } from "react";

import { useTheme } from "@/components/theme/theme-provider";
import type { ThemePreference } from "@/lib/preferences/theme";

type ThemeOption = {
  icon: LucideIcon;
  label: string;
  value: ThemePreference;
};

const options: ThemeOption[] = [
  { icon: Monitor, label: "システム設定", value: "system" },
  { icon: Sun, label: "ライト", value: "light" },
  { icon: Moon, label: "ダーク", value: "dark" },
];

export function ThemeSelector() {
  const labelId = useId();
  const { preference, setPreference } = useTheme();

  return (
    <div className="px-1.5 py-1">
      <span id={labelId} className="sr-only">
        テーマ
      </span>
      <div
        role="radiogroup"
        aria-labelledby={labelId}
        className="grid grid-cols-3 gap-0.5 rounded-xl bg-[var(--control-background)] p-0.5"
      >
        {options.map(({ icon: Icon, label, value }) => {
          const selected = preference === value;

          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={label}
              title={label}
              className={`grid h-8 place-items-center rounded-[10px] transition-[background-color,color,box-shadow] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] ${
                selected
                  ? "bg-[var(--surface-elevated)] text-[var(--text)] shadow-[0_1px_3px_var(--control-shadow)]"
                  : "text-[var(--muted)] hover:bg-[var(--hover)] hover:text-[var(--text)]"
              }`}
              onClick={() => setPreference(value)}
            >
              <Icon aria-hidden="true" className="size-[16px]" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
