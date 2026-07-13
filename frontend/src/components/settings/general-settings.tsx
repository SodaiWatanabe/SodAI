"use client";

import { SettingsPicker } from "@/components/settings/settings-picker";
import { themeOptions } from "@/components/theme/theme-options";
import { useTheme } from "@/components/theme/theme-provider";

export function GeneralSettings() {
  const { preference, setPreference } = useTheme();

  return (
    <div className="w-full px-5 pb-7 pt-2 sm:px-6 sm:pb-8 sm:pt-2">
      <div className="flex min-h-14 items-center rounded-xl">
        <span className="min-w-0 flex-1 text-sm font-medium text-[var(--text)]">
          外観
        </span>
        <SettingsPicker
          label="外観"
          options={themeOptions}
          value={preference}
          onValueChange={setPreference}
        />
      </div>
    </div>
  );
}
