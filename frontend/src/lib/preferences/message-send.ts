export const MESSAGE_SEND_COOKIE_NAME = "sodai_message_send_key";

export const messageSendPreferences = ["enter", "mod-enter"] as const;

export type MessageSendPreference =
  (typeof messageSendPreferences)[number];

type MessageSendKey = {
  ctrlKey: boolean;
  isComposing?: boolean;
  key: string;
  keyCode?: number;
  metaKey: boolean;
};

const DEFAULT_MESSAGE_SEND_PREFERENCE: MessageSendPreference = "enter";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export function parseMessageSendPreference(
  value: string | undefined,
): MessageSendPreference {
  return messageSendPreferences.includes(value as MessageSendPreference)
    ? (value as MessageSendPreference)
    : DEFAULT_MESSAGE_SEND_PREFERENCE;
}

export function createMessageSendCookie(
  preference: MessageSendPreference,
  secure: boolean,
) {
  const attributes = [
    `${MESSAGE_SEND_COOKIE_NAME}=${preference}`,
    "Path=/",
    `Max-Age=${COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ];

  if (secure) attributes.push("Secure");

  return attributes.join("; ");
}

export function matchesMessageSendShortcut(
  event: MessageSendKey,
  preference: MessageSendPreference,
) {
  if (
    event.key !== "Enter" ||
    event.isComposing ||
    event.keyCode === 229
  ) {
    return false;
  }
  if (preference === "enter") return true;
  return event.ctrlKey || event.metaKey;
}
