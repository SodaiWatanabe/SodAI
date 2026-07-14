"use client";

import { ArrowUp } from "lucide-react";
import type {
  FormEventHandler,
  RefObject,
} from "react";

import { handleMessageSubmitKeyDown } from "@/components/chat/message-submit-keydown";
import { useComposerTextareaAutosize } from "@/components/chat/use-composer-textarea-autosize";
import type { KeyboardShortcut } from "@/lib/preferences/keyboard-shortcuts";

type MessageComposerProps = {
  ariaLabel?: string;
  autoFocus?: boolean;
  className: string;
  disabled: boolean;
  inputId: string;
  inputLabel: string;
  onChange: (value: string) => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  placeholder: string;
  sendShortcut: KeyboardShortcut;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
};

export function MessageComposer({
  ariaLabel,
  autoFocus = false,
  className,
  disabled,
  inputId,
  inputLabel,
  onChange,
  onSubmit,
  placeholder,
  sendShortcut,
  textareaRef,
  value,
}: MessageComposerProps) {
  const multiline = useComposerTextareaAutosize(textareaRef, value);
  const sendButton = (
    <button
      type="submit"
      aria-label="送信"
      disabled={disabled}
      className="grid size-10 shrink-0 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)] transition-opacity disabled:opacity-25"
    >
      <ArrowUp aria-hidden="true" className="size-[18px]" strokeWidth={2.2} />
    </button>
  );

  return (
    <form className={className} onSubmit={onSubmit} aria-label={ariaLabel}>
      <div className="chat-input relative min-h-14 w-full overflow-hidden rounded-[28px] border border-[var(--field-border)] bg-[var(--surface)] text-[var(--text)] shadow-[0_8px_30px_var(--input-shadow)] transition-shadow focus-within:shadow-[0_10px_38px_var(--input-shadow)]">
        <label htmlFor={inputId} className="sr-only">
          {inputLabel}
        </label>
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
          className={`block max-h-40 w-full resize-none overflow-y-hidden border-0 bg-transparent text-[16px] leading-6 text-[var(--text)] outline-none transition-[height] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] placeholder:text-[var(--muted)] motion-reduce:transition-none ${
            multiline
              ? "px-6 pb-1.5 pt-[15px]"
              : "py-[15px] pl-6 pr-14"
          }`}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) =>
            handleMessageSubmitKeyDown(event, sendShortcut)
          }
        />
        <div
          aria-hidden="true"
          className={`transition-[height] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${
            multiline ? "h-12" : "h-0"
          }`}
        />
        <div className="absolute bottom-2 right-2">{sendButton}</div>
      </div>
    </form>
  );
}
