"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  canonicalizeKeyboardShortcut,
  createKeyboardShortcutCookie,
  DEFAULT_KEYBOARD_SHORTCUTS,
  type KeyboardShortcut,
  type KeyboardShortcutAction,
  type KeyboardShortcutAssignmentResult,
  type KeyboardShortcuts,
  validateKeyboardShortcut,
} from "@/lib/preferences/keyboard-shortcuts";

type KeyboardShortcutsContextValue = {
  assignShortcut: (
    action: KeyboardShortcutAction,
    shortcut: KeyboardShortcut,
  ) => KeyboardShortcutAssignmentResult;
  cancelRecording: (action: KeyboardShortcutAction) => void;
  recordingAction: KeyboardShortcutAction | null;
  resetShortcut: (
    action: KeyboardShortcutAction,
  ) => KeyboardShortcutAssignmentResult;
  shortcuts: KeyboardShortcuts;
  startRecording: (action: KeyboardShortcutAction) => void;
};

type KeyboardShortcutsProviderProps = {
  children: ReactNode;
  initialShortcuts: KeyboardShortcuts;
};

const KeyboardShortcutsContext =
  createContext<KeyboardShortcutsContextValue | null>(null);

export function KeyboardShortcutsProvider({
  children,
  initialShortcuts,
}: KeyboardShortcutsProviderProps) {
  const shortcutsRef = useRef(initialShortcuts);
  const [shortcuts, setShortcuts] = useState(initialShortcuts);
  const [recordingAction, setRecordingAction] =
    useState<KeyboardShortcutAction | null>(null);

  const updateShortcut = useCallback(
    (action: KeyboardShortcutAction, shortcut: KeyboardShortcut | null) => {
      const nextShortcuts = { ...shortcutsRef.current, [action]: shortcut };
      shortcutsRef.current = nextShortcuts;
      setShortcuts(nextShortcuts);
    },
    [],
  );

  const writeShortcutCookie = useCallback(
    (action: KeyboardShortcutAction, shortcut: KeyboardShortcut | null) => {
      document.cookie = createKeyboardShortcutCookie(
        action,
        shortcut,
        window.location.protocol === "https:",
      );
    },
    [],
  );

  const assignShortcut = useCallback(
    (action: KeyboardShortcutAction, shortcut: KeyboardShortcut) => {
      const canonicalShortcut = canonicalizeKeyboardShortcut(action, shortcut);
      const result = validateKeyboardShortcut(
        shortcutsRef.current,
        action,
        canonicalShortcut,
      );
      if (!result.ok) return result;
      updateShortcut(action, canonicalShortcut);
      writeShortcutCookie(action, canonicalShortcut);
      setRecordingAction(null);
      return result;
    },
    [updateShortcut, writeShortcutCookie],
  );

  const resetShortcut = useCallback(
    (action: KeyboardShortcutAction) => {
      const defaultShortcut = DEFAULT_KEYBOARD_SHORTCUTS[action];
      const result: KeyboardShortcutAssignmentResult = defaultShortcut
        ? validateKeyboardShortcut(
            shortcutsRef.current,
            action,
            defaultShortcut,
          )
        : { ok: true };
      if (!result.ok) return result;
      updateShortcut(action, defaultShortcut);
      writeShortcutCookie(action, null);
      setRecordingAction((current) => (current === action ? null : current));
      return result;
    },
    [updateShortcut, writeShortcutCookie],
  );

  const startRecording = useCallback((action: KeyboardShortcutAction) => {
    setRecordingAction(action);
  }, []);

  const cancelRecording = useCallback((action: KeyboardShortcutAction) => {
    setRecordingAction((current) => (current === action ? null : current));
  }, []);

  const context = useMemo(
    () => ({
      assignShortcut,
      cancelRecording,
      recordingAction,
      resetShortcut,
      shortcuts,
      startRecording,
    }),
    [
      assignShortcut,
      cancelRecording,
      recordingAction,
      resetShortcut,
      shortcuts,
      startRecording,
    ],
  );

  return (
    <KeyboardShortcutsContext.Provider value={context}>
      {children}
    </KeyboardShortcutsContext.Provider>
  );
}

export function useKeyboardShortcuts() {
  const context = useContext(KeyboardShortcutsContext);
  if (!context) {
    throw new Error(
      "useKeyboardShortcuts must be used inside KeyboardShortcutsProvider.",
    );
  }
  return context;
}
