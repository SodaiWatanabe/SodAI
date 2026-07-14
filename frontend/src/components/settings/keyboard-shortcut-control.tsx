"use client";

import { RotateCcw } from "lucide-react";
import { type KeyboardEvent, useEffect, useState } from "react";

import { useKeyboardShortcuts } from "@/components/preferences/keyboard-shortcuts-provider";
import {
  formatKeyboardShortcut,
  isDefaultKeyboardShortcut,
  keyboardShortcutFromKey,
  type KeyboardShortcutAction,
  type KeyboardShortcutAssignmentResult,
} from "@/lib/preferences/keyboard-shortcuts";

const conflictLabels: Readonly<Record<KeyboardShortcutAction, string>> = {
  messageSend: "送信で使用中",
  newChat: "新しい会話で使用中",
};

function feedbackFor(result: KeyboardShortcutAssignmentResult) {
  if (result.ok) return null;
  return result.reason === "conflict"
    ? conflictLabels[result.conflictingAction]
    : "修飾キーを含める";
}

export function KeyboardShortcutControl({
  action,
  label,
}: {
  action: KeyboardShortcutAction;
  label: string;
}) {
  const {
    assignShortcut,
    cancelRecording,
    recordingAction,
    resetShortcut,
    shortcuts,
    startRecording,
  } = useKeyboardShortcuts();
  const [feedback, setFeedback] = useState<string | null>(null);
  const shortcut = shortcuts[action];
  const recording = recordingAction === action;
  const customized = !isDefaultKeyboardShortcut(action, shortcut);
  const valueLabel = shortcut ? formatKeyboardShortcut(shortcut) : "なし";
  const visibleLabel = feedback ?? (recording ? "キーを入力" : valueLabel);
  const ariaLabel = feedback
    ? `${label}: ${feedback}`
    : recording
      ? `${label}のショートカットキーを入力`
      : `${label}のショートカットを変更: ${valueLabel}`;

  useEffect(() => {
    return () => {
      cancelRecording(action);
    };
  }, [action, cancelRecording]);

  function recordShortcut(event: KeyboardEvent<HTMLButtonElement>) {
    if (!recording) return;
    if (event.key === "Tab") return;
    if (event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    setFeedback(null);
    if (event.key === "Escape") {
      cancelRecording(action);
      return;
    }
    const candidate = keyboardShortcutFromKey({
      altKey: event.altKey,
      ctrlKey: event.ctrlKey,
      isComposing: event.nativeEvent.isComposing,
      key: event.key,
      keyCode: event.nativeEvent.keyCode,
      metaKey: event.metaKey,
      shiftKey: event.shiftKey,
    });
    if (!candidate) return;
    const result = assignShortcut(action, candidate);
    if (result.ok) return;
    setFeedback(feedbackFor(result));
  }

  return (
    <div className="flex shrink-0 items-center gap-0.5">
      {customized ? (
        <button
          type="button"
          aria-label={`${label}のショートカットをリセット`}
          title="リセット"
          className="grid size-9 place-items-center rounded-xl text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none"
          onClick={() => {
            setFeedback(feedbackFor(resetShortcut(action)));
          }}
        >
          <RotateCcw aria-hidden="true" className="size-4" />
        </button>
      ) : null}
      <button
        type="button"
        aria-label={ariaLabel}
        aria-live="polite"
        className={`h-9 min-w-16 rounded-xl px-2.5 text-sm font-medium transition-colors focus-visible:outline-none ${
          recording
            ? "bg-[var(--field)] text-[var(--muted)]"
            : "text-[var(--text)] hover:bg-[var(--hover)]"
        }`}
        onBlur={() => {
          setFeedback(null);
          cancelRecording(action);
        }}
        onClick={() => {
          if (recording) return;
          setFeedback(null);
          startRecording(action);
        }}
        onKeyDown={recordShortcut}
      >
        {visibleLabel}
      </button>
    </div>
  );
}
