"use client";

import { ArrowUp, Square } from "lucide-react";
import type {
  FocusEventHandler,
  FormEventHandler,
  RefObject,
} from "react";

import { handleMessageSubmitKeyDown } from "@/components/chat/message-submit-keydown";
import { useComposerTextareaAutosize } from "@/components/chat/use-composer-textarea-autosize";
import type { KeyboardShortcut } from "@/lib/preferences/keyboard-shortcuts";

type MessageComposerProps = {
  action: MessageComposerAction;
  ariaLabel?: string;
  autoFocus?: boolean;
  className: string;
  inputId: string;
  inputLabel: string;
  onBlur?: FocusEventHandler<HTMLTextAreaElement>;
  onChange: (value: string) => void;
  onFocus?: FocusEventHandler<HTMLTextAreaElement>;
  onSubmit: FormEventHandler<HTMLFormElement>;
  placeholder: string;
  sendShortcut: KeyboardShortcut;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
};

export type MessageComposerAction =
  | { kind: "send"; disabled: boolean }
  | { kind: "stop"; onStop: () => void; pending: boolean };

export function MessageComposer({
  action,
  ariaLabel,
  autoFocus = false,
  className,
  inputId,
  inputLabel,
  onBlur,
  onChange,
  onFocus,
  onSubmit,
  placeholder,
  sendShortcut,
  textareaRef,
  value,
}: MessageComposerProps) {
  const { multiline, scrollEdges } = useComposerTextareaAutosize(
    textareaRef,
    value,
  );
  const actionButton = action.kind === "send" ? (
    <button
      type="submit"
      aria-label="送信"
      disabled={action.disabled}
      className="grid size-10 shrink-0 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-opacity disabled:opacity-25"
    >
      <ArrowUp aria-hidden="true" className="size-[18px]" strokeWidth={2.2} />
    </button>
  ) : (
    <button
      type="button"
      aria-label={action.pending ? "応答を停止しています" : "応答を停止"}
      disabled={action.pending}
      className="grid size-10 shrink-0 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-opacity disabled:opacity-60"
      onClick={action.onStop}
    >
      <Square
        aria-hidden="true"
        className="size-[13px] fill-current"
        strokeWidth={1.8}
      />
    </button>
  );

  return (
    <form className={className} onSubmit={onSubmit} aria-label={ariaLabel}>
      <div className="chat-input relative min-h-14 w-full overflow-hidden rounded-[28px] border border-[var(--field-border)] bg-[var(--surface)] text-[var(--text)] shadow-[0_8px_30px_var(--input-shadow)] transition-shadow focus-within:shadow-[0_10px_38px_var(--input-shadow)]">
        <label htmlFor={inputId} className="sr-only">
          {inputLabel}
        </label>
        <div className="relative">
          <textarea
            ref={textareaRef}
            id={inputId}
            rows={1}
            value={value}
            autoFocus={autoFocus}
            placeholder={placeholder}
            autoComplete="off"
            spellCheck="true"
            wrap="soft"
            className={`block max-h-[208px] w-full resize-none overflow-y-hidden border-0 bg-transparent text-[16px] leading-6 text-[var(--text)] outline-none transition-[height] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] placeholder:text-[var(--muted)] motion-reduce:transition-none ${
              multiline
                ? "px-6 pb-1.5 pt-[15px]"
                : "py-[15px] pl-6 pr-14"
            }`}
            onBlur={onBlur}
            onChange={(event) => onChange(event.target.value)}
            onFocus={onFocus}
            onKeyDown={(event) =>
              handleMessageSubmitKeyDown(
                event,
                sendShortcut,
                action.kind === "send",
              )
            }
          />
          <div
            aria-hidden="true"
            className={`composer-edge-blur composer-edge-blur-top pointer-events-none absolute inset-x-0 top-0 z-10 h-4 transition-opacity duration-150 motion-reduce:transition-none ${
              scrollEdges.top ? "opacity-100" : "opacity-0"
            }`}
          />
          <div
            aria-hidden="true"
            className={`composer-edge-blur composer-edge-blur-bottom pointer-events-none absolute inset-x-0 bottom-0 z-10 h-4 transition-opacity duration-150 motion-reduce:transition-none ${
              scrollEdges.bottom ? "opacity-100" : "opacity-0"
            }`}
          />
        </div>
        <div
          aria-hidden="true"
          className={`transition-[height] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${
            multiline ? "h-12" : "h-0"
          }`}
        />
        <div className="absolute bottom-2 right-2">{actionButton}</div>
      </div>
    </form>
  );
}
