"use client";

import { useMessageSendPreference } from "@/components/preferences/message-send-preference-provider";
import {
  SettingsPicker,
  type SettingsPickerOption,
} from "@/components/settings/settings-picker";
import type { MessageSendPreference } from "@/lib/preferences/message-send";

const messageSendOptions: readonly SettingsPickerOption<MessageSendPreference>[] =
  [
    { value: "enter", label: "Enter" },
    { value: "mod-enter", label: "Ctrl / ⌘ + Enter" },
  ];

export function KeyboardSettings() {
  const { preference, setPreference } = useMessageSendPreference();

  return (
    <div className="w-full px-5 pb-7 pt-2 sm:px-6 sm:pb-8 sm:pt-2">
      <div className="flex min-h-14 items-center rounded-xl">
        <span className="min-w-0 flex-1 text-sm font-medium text-[var(--text)]">
          メッセージを送信
        </span>
        <SettingsPicker
          label="メッセージを送信"
          options={messageSendOptions}
          value={preference}
          onValueChange={setPreference}
        />
      </div>
    </div>
  );
}
