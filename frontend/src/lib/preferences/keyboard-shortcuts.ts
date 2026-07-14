export const MESSAGE_SEND_SHORTCUT_COOKIE_NAME = "sodai_message_send_key";
export const NEW_CHAT_SHORTCUT_COOKIE_NAME = "sodai_new_chat_key";

export const keyboardShortcutActions = ["messageSend", "newChat"] as const;

export type KeyboardShortcutAction =
  (typeof keyboardShortcutActions)[number];

export type KeyboardShortcut = Readonly<{
  altKey: boolean;
  ctrlKey: boolean;
  key: string;
  metaKey: boolean;
  modifierMode: "exact" | "legacy-enter" | "primary";
  shiftKey: boolean;
}>;

export type KeyboardShortcuts = Readonly<{
  messageSend: KeyboardShortcut;
  newChat: KeyboardShortcut | null;
}>;

export type KeyboardShortcutAssignmentResult =
  | { ok: true }
  | {
      conflictingAction: KeyboardShortcutAction;
      ok: false;
      reason: "conflict";
    }
  | { ok: false; reason: "modifier-required" };

type KeyboardShortcutKey = {
  altKey: boolean;
  ctrlKey: boolean;
  isComposing?: boolean;
  key: string;
  keyCode?: number;
  metaKey: boolean;
  shiftKey: boolean;
};

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;
const SHORTCUT_COOKIE_PATTERN =
  /^v2\.(\d{1,2})\.([0-9a-f]+(?:-[0-9a-f]+)*)$/;
const CTRL_MASK = 1;
const META_MASK = 2;
const ALT_MASK = 4;
const SHIFT_MASK = 8;
const PRIMARY_MODIFIER_MASK = 16;
const MAX_SHORTCUT_MASK =
  CTRL_MASK |
  META_MASK |
  ALT_MASK |
  SHIFT_MASK |
  PRIMARY_MODIFIER_MASK;

const ENTER_SHORTCUT: KeyboardShortcut = Object.freeze({
  altKey: false,
  ctrlKey: false,
  key: "Enter",
  metaKey: false,
  modifierMode: "legacy-enter",
  shiftKey: false,
});

const LEGACY_PRIMARY_ENTER_SHORTCUT: KeyboardShortcut = Object.freeze({
  altKey: false,
  ctrlKey: false,
  key: "Enter",
  metaKey: false,
  modifierMode: "primary",
  shiftKey: false,
});

export const DEFAULT_KEYBOARD_SHORTCUTS: KeyboardShortcuts = Object.freeze({
  messageSend: ENTER_SHORTCUT,
  newChat: null,
});

const SHORTCUT_COOKIE_NAMES: Readonly<
  Record<KeyboardShortcutAction, string>
> = {
  messageSend: MESSAGE_SEND_SHORTCUT_COOKIE_NAME,
  newChat: NEW_CHAT_SHORTCUT_COOKIE_NAME,
};

const UNMODIFIED_KEYS: Readonly<
  Record<KeyboardShortcutAction, ReadonlySet<string>>
> = {
  messageSend: new Set(["Enter"]),
  newChat: new Set(),
};

const MODIFIER_KEYS = new Set(["Alt", "AltGraph", "Control", "Meta", "Shift"]);

const KEY_LABELS: Readonly<Record<string, string>> = {
  ArrowDown: "↓",
  ArrowLeft: "←",
  ArrowRight: "→",
  ArrowUp: "↑",
  Convert: "変換",
  Escape: "Esc",
  NonConvert: "無変換",
  PageDown: "Page Down",
  PageUp: "Page Up",
  " ": "Space",
};

function shortcutMask(shortcut: KeyboardShortcut) {
  return (
    (shortcut.ctrlKey ? CTRL_MASK : 0) |
    (shortcut.metaKey ? META_MASK : 0) |
    (shortcut.altKey ? ALT_MASK : 0) |
    (shortcut.shiftKey ? SHIFT_MASK : 0) |
    (shortcut.modifierMode === "primary" ? PRIMARY_MODIFIER_MASK : 0)
  );
}

function serializeKeyboardShortcut(
  action: KeyboardShortcutAction,
  shortcut: KeyboardShortcut,
) {
  if (action === "messageSend" && shortcut.modifierMode === "legacy-enter") {
    return "enter";
  }
  if (
    action === "messageSend" &&
    shortcut.key === "Enter" &&
    shortcut.modifierMode === "primary"
  ) {
    return "mod-enter";
  }
  const encodedKey = Array.from(shortcut.key, (character) =>
    character.codePointAt(0)!.toString(16),
  ).join("-");
  return `v2.${shortcutMask(shortcut)}.${encodedKey}`;
}

function parseShortcutMask(rawMask: string | undefined) {
  const mask = Number(rawMask);
  if (
    !Number.isInteger(mask) ||
    mask < 0 ||
    mask > MAX_SHORTCUT_MASK ||
    (Boolean(mask & PRIMARY_MODIFIER_MASK) &&
      Boolean(mask & (CTRL_MASK | META_MASK | ALT_MASK | SHIFT_MASK)))
  ) {
    return null;
  }
  return mask;
}

function normalizeKeyboardKey(key: string) {
  return Array.from(key).length === 1 ? key.toLocaleLowerCase("en-US") : key;
}

function isRecordableKey(key: string) {
  const length = Array.from(key).length;
  return (
    length > 0 &&
    length <= 32 &&
    key !== "Unidentified" &&
    !MODIFIER_KEYS.has(key)
  );
}

function parseSerializedKeyboardShortcut(
  value: string | undefined,
): KeyboardShortcut | null {
  if (!value) return null;
  const match = SHORTCUT_COOKIE_PATTERN.exec(value);
  if (!match) return null;
  const mask = parseShortcutMask(match[1]);
  if (mask === null || !match[2]) return null;

  const codePoints = match[2]
    .split("-")
    .map((part) => Number.parseInt(part, 16));
  if (
    codePoints.length > 32 ||
    codePoints.some(
      (codePoint) =>
        !Number.isInteger(codePoint) ||
        codePoint < 0 ||
        codePoint > 0x10ffff ||
        (codePoint >= 0xd800 && codePoint <= 0xdfff),
    )
  ) {
    return null;
  }
  const key = normalizeKeyboardKey(String.fromCodePoint(...codePoints));
  if (!isRecordableKey(key)) return null;

  return {
    altKey: Boolean(mask & ALT_MASK),
    ctrlKey: Boolean(mask & CTRL_MASK),
    key,
    metaKey: Boolean(mask & META_MASK),
    modifierMode: Boolean(mask & PRIMARY_MODIFIER_MASK)
      ? "primary"
      : "exact",
    shiftKey: Boolean(mask & SHIFT_MASK),
  };
}

function hasActionModifier(shortcut: KeyboardShortcut) {
  return (
    shortcut.modifierMode === "primary" ||
    shortcut.ctrlKey ||
    shortcut.metaKey ||
    shortcut.altKey
  );
}

function hasRequiredModifier(
  action: KeyboardShortcutAction,
  shortcut: KeyboardShortcut,
) {
  return (
    UNMODIFIED_KEYS[action].has(shortcut.key) || hasActionModifier(shortcut)
  );
}

export function canonicalizeKeyboardShortcut(
  action: KeyboardShortcutAction,
  shortcut: KeyboardShortcut,
) {
  if (
    action === "messageSend" &&
    shortcut.key === "Enter" &&
    shortcut.modifierMode === "exact" &&
    !shortcut.altKey &&
    !shortcut.ctrlKey &&
    !shortcut.metaKey &&
    !shortcut.shiftKey
  ) {
    return ENTER_SHORTCUT;
  }
  return shortcut;
}

function parseMessageSendShortcut(value: string | undefined) {
  if (!value || value === "enter") return ENTER_SHORTCUT;
  if (value === "mod-enter") return LEGACY_PRIMARY_ENTER_SHORTCUT;
  const parsed = parseSerializedKeyboardShortcut(value);
  if (!parsed || !hasRequiredModifier("messageSend", parsed)) {
    return ENTER_SHORTCUT;
  }
  return canonicalizeKeyboardShortcut("messageSend", parsed);
}

function modifiersMatch(
  event: Pick<
    KeyboardShortcutKey,
    "altKey" | "ctrlKey" | "metaKey" | "shiftKey"
  >,
  shortcut: KeyboardShortcut,
) {
  if (shortcut.modifierMode === "legacy-enter") return !event.shiftKey;
  if (shortcut.modifierMode === "primary") {
    return event.ctrlKey || event.metaKey;
  }
  return (
    event.altKey === shortcut.altKey &&
    event.ctrlKey === shortcut.ctrlKey &&
    event.metaKey === shortcut.metaKey &&
    event.shiftKey === shortcut.shiftKey
  );
}

function keyLabel(key: string) {
  const mapped = KEY_LABELS[key];
  if (mapped) return mapped;
  return Array.from(key).length === 1 ? key.toLocaleUpperCase("en-US") : key;
}

export function parseKeyboardShortcuts({
  messageSend,
  newChat,
}: {
  messageSend: string | undefined;
  newChat: string | undefined;
}): KeyboardShortcuts {
  const parsedMessageSend = parseMessageSendShortcut(messageSend);
  const parsedNewChat = parseSerializedKeyboardShortcut(newChat);
  const candidate: KeyboardShortcuts = {
    messageSend: parsedMessageSend,
    newChat: null,
  };
  const newChatValidation = parsedNewChat
    ? validateKeyboardShortcut(candidate, "newChat", parsedNewChat)
    : null;

  return {
    messageSend: parsedMessageSend,
    newChat: newChatValidation?.ok ? parsedNewChat : null,
  };
}

export function createKeyboardShortcutCookie(
  action: KeyboardShortcutAction,
  shortcut: KeyboardShortcut | null,
  secure: boolean,
) {
  const attributes = [
    `${SHORTCUT_COOKIE_NAMES[action]}=${
      shortcut ? serializeKeyboardShortcut(action, shortcut) : ""
    }`,
    "Path=/",
    `Max-Age=${shortcut ? COOKIE_MAX_AGE_SECONDS : 0}`,
    "SameSite=Lax",
  ];
  if (secure) attributes.push("Secure");
  return attributes.join("; ");
}

export function keyboardShortcutFromKey(
  event: KeyboardShortcutKey,
): KeyboardShortcut | null {
  if (event.isComposing || event.keyCode === 229) return null;
  const key = normalizeKeyboardKey(event.key);
  if (!isRecordableKey(key)) return null;

  return {
    altKey: event.altKey,
    ctrlKey: event.ctrlKey,
    key,
    metaKey: event.metaKey,
    modifierMode: "exact",
    shiftKey: event.shiftKey,
  };
}

export function formatKeyboardShortcut(shortcut: KeyboardShortcut) {
  const labels: string[] = [];
  if (shortcut.modifierMode === "primary") {
    labels.push("Ctrl / ⌘");
  } else if (shortcut.modifierMode === "exact") {
    if (shortcut.ctrlKey) labels.push("Ctrl");
    if (shortcut.altKey) labels.push("Alt");
    if (shortcut.shiftKey) labels.push("Shift");
    if (shortcut.metaKey) labels.push("⌘");
  }
  labels.push(keyLabel(shortcut.key));
  return labels.join(" + ");
}

export function keyboardShortcutsConflict(
  left: KeyboardShortcut,
  right: KeyboardShortcut,
) {
  if (left.key !== right.key) return false;
  for (let mask = 0; mask < 16; mask += 1) {
    const modifiers = {
      altKey: Boolean(mask & ALT_MASK),
      ctrlKey: Boolean(mask & CTRL_MASK),
      metaKey: Boolean(mask & META_MASK),
      shiftKey: Boolean(mask & SHIFT_MASK),
    };
    if (modifiersMatch(modifiers, left) && modifiersMatch(modifiers, right)) {
      return true;
    }
  }
  return false;
}

export function validateKeyboardShortcut(
  shortcuts: KeyboardShortcuts,
  action: KeyboardShortcutAction,
  candidate: KeyboardShortcut,
): KeyboardShortcutAssignmentResult {
  const canonicalCandidate = canonicalizeKeyboardShortcut(action, candidate);
  if (!hasRequiredModifier(action, canonicalCandidate)) {
    return { ok: false, reason: "modifier-required" };
  }
  for (const otherAction of keyboardShortcutActions) {
    if (otherAction === action) continue;
    const otherShortcut = shortcuts[otherAction];
    if (
      otherShortcut &&
      keyboardShortcutsConflict(canonicalCandidate, otherShortcut)
    ) {
      return {
        conflictingAction: otherAction,
        ok: false,
        reason: "conflict",
      };
    }
  }
  return { ok: true };
}

export function isDefaultKeyboardShortcut(
  action: KeyboardShortcutAction,
  shortcut: KeyboardShortcut | null,
) {
  const defaultShortcut = DEFAULT_KEYBOARD_SHORTCUTS[action];
  if (!defaultShortcut || !shortcut) return defaultShortcut === shortcut;
  return (
    shortcut.key === defaultShortcut.key &&
    shortcut.ctrlKey === defaultShortcut.ctrlKey &&
    shortcut.metaKey === defaultShortcut.metaKey &&
    shortcut.altKey === defaultShortcut.altKey &&
    shortcut.shiftKey === defaultShortcut.shiftKey &&
    shortcut.modifierMode === defaultShortcut.modifierMode
  );
}

export function matchesKeyboardShortcut(
  event: KeyboardShortcutKey,
  shortcut: KeyboardShortcut,
) {
  if (
    normalizeKeyboardKey(event.key) !== shortcut.key ||
    event.isComposing ||
    event.keyCode === 229
  ) {
    return false;
  }
  return modifiersMatch(event, shortcut);
}
