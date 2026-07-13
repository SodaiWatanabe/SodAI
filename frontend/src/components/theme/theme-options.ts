import type { ThemePreference } from "@/lib/preferences/theme";

export type ThemeOption = {
  label: string;
  value: ThemePreference;
};

export const themeOptions: readonly ThemeOption[] = [
  {
    label: "自動",
    value: "system",
  },
  {
    label: "ライト",
    value: "light",
  },
  {
    label: "ダーク",
    value: "dark",
  },
] as const;
