import { KeyboardShortcutControl } from "@/components/settings/keyboard-shortcut-control";
import type { KeyboardShortcutAction } from "@/lib/preferences/keyboard-shortcuts";

const keyboardSettings: readonly {
  action: KeyboardShortcutAction;
  label: string;
}[] = [
  { action: "messageSend", label: "メッセージを送信" },
  { action: "newChat", label: "新しい会話" },
];

export function KeyboardSettings() {
  return (
    <div className="w-full px-5 pb-7 pt-2 sm:px-6 sm:pb-8 sm:pt-2">
      {keyboardSettings.map((setting, index) => (
        <div
          key={setting.action}
          className={`flex min-h-14 items-center ${index > 0 ? "border-t border-[var(--separator)]" : ""}`}
        >
          <span className="min-w-0 flex-1 text-sm font-medium text-[var(--text)]">
            {setting.label}
          </span>
          <KeyboardShortcutControl
            action={setting.action}
            label={setting.label}
          />
        </div>
      ))}
    </div>
  );
}
