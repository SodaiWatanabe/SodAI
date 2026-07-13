import type { KeyboardEvent } from "react";

import {
  matchesMessageSendShortcut,
  type MessageSendPreference,
} from "@/lib/preferences/message-send";

export function handleMessageSubmitKeyDown(
  event: KeyboardEvent<HTMLTextAreaElement>,
  preference: MessageSendPreference,
) {
  const shouldSubmit = matchesMessageSendShortcut(
    {
      ctrlKey: event.ctrlKey,
      isComposing: event.nativeEvent.isComposing,
      key: event.key,
      keyCode: event.nativeEvent.keyCode,
      metaKey: event.metaKey,
      shiftKey: event.shiftKey,
    },
    preference,
  );
  if (!shouldSubmit) return;

  event.preventDefault();
  event.currentTarget.form?.requestSubmit();
}
