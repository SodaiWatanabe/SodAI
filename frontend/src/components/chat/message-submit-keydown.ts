import type { KeyboardEvent } from "react";

import {
  matchesKeyboardShortcut,
  type KeyboardShortcut,
} from "@/lib/preferences/keyboard-shortcuts";

export function handleMessageSubmitKeyDown(
  event: KeyboardEvent<HTMLTextAreaElement>,
  shortcut: KeyboardShortcut,
  enabled = true,
) {
  if (!enabled) return;
  const shouldSubmit = matchesKeyboardShortcut(
    {
      altKey: event.altKey,
      ctrlKey: event.ctrlKey,
      isComposing: event.nativeEvent.isComposing,
      key: event.key,
      keyCode: event.nativeEvent.keyCode,
      metaKey: event.metaKey,
      shiftKey: event.shiftKey,
    },
    shortcut,
  );
  if (!shouldSubmit) return;

  event.preventDefault();
  event.currentTarget.form?.requestSubmit();
}
