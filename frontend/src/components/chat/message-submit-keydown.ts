import type { KeyboardEvent } from "react";

import {
  matchesMessageSendShortcut,
  type MessageSendPreference,
} from "@/lib/preferences/message-send";

export function handleMessageSubmitKeyDown(
  event: KeyboardEvent<HTMLInputElement>,
  preference: MessageSendPreference,
) {
  if (event.key !== "Enter") return;

  event.preventDefault();
  if (
    matchesMessageSendShortcut(
      {
        ctrlKey: event.ctrlKey,
        isComposing: event.nativeEvent.isComposing,
        key: event.key,
        keyCode: event.nativeEvent.keyCode,
        metaKey: event.metaKey,
      },
      preference,
    )
  ) {
    event.currentTarget.form?.requestSubmit();
  }
}
