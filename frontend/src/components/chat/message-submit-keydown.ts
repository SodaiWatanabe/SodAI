import type { KeyboardEvent } from "react";

import {
  matchesKeyboardShortcut,
  type KeyboardShortcut,
} from "@/lib/preferences/keyboard-shortcuts";
import { shouldSubmitMessageFromKeyboard } from "@/components/chat/message-submit-keydown-policy";

function hasCoarsePrimaryPointer() {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(pointer: coarse)").matches
  );
}

export function handleMessageSubmitKeyDown(
  event: KeyboardEvent<HTMLTextAreaElement>,
  shortcut: KeyboardShortcut,
  enabled = true,
) {
  const shortcutMatches = matchesKeyboardShortcut(
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
  const shouldSubmit = shouldSubmitMessageFromKeyboard({
    coarsePrimaryPointer: hasCoarsePrimaryPointer(),
    enabled,
    shortcutMatches,
  });
  if (!shouldSubmit) return;

  event.preventDefault();
  event.currentTarget.form?.requestSubmit();
}
