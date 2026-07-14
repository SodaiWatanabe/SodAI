"use client";

import { Archive, Ellipsis, Pencil } from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useToast } from "@/components/ui/toast-provider";
import type { ThreadSummary } from "@/lib/chat/types";

type ThreadListItemProps = {
  active: boolean;
  thread: ThreadSummary;
  onArchive: () => void;
  onSelect: () => void;
};

export function ThreadListItem({
  active,
  thread,
  onArchive,
  onSelect,
}: ThreadListItemProps) {
  const { archiveThread, renameThread } = useChatData();
  const { showToast } = useToast();
  const contentRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelBlurSaveRef = useRef(false);
  const [title, setTitle] = useState(thread.title);
  const [editing, setEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!editing || submitting) return;
    const frame = requestAnimationFrame(() => {
      inputRef.current?.focus({ preventScroll: true });
      inputRef.current?.select();
    });
    return () => cancelAnimationFrame(frame);
  }, [editing, submitting]);

  function closePopover() {
    contentRef.current?.hidePopover();
  }

  function startRename() {
    cancelBlurSaveRef.current = false;
    setTitle(thread.title);
    setEditing(true);
    closePopover();
  }

  async function saveRename() {
    const nextTitle = title.trim();
    if (submitting) return;
    if (!nextTitle || nextTitle === thread.title) {
      setTitle(thread.title);
      setEditing(false);
      return;
    }
    setSubmitting(true);
    try {
      await renameThread(thread.id, nextTitle);
      setTitle(nextTitle);
      setEditing(false);
    } catch {
      showToast({
        id: `thread-rename-${thread.id}`,
        message: "会話の名前を変更できませんでした。",
        tone: "error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function archive() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await archiveThread(thread.id);
      closePopover();
      onArchive();
    } catch {
      showToast({
        id: `thread-archive-${thread.id}`,
        message: "会話をアーカイブできませんでした。",
        tone: "error",
      });
      setSubmitting(false);
    }
  }

  function handleRenameKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.blur();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      cancelBlurSaveRef.current = true;
      setTitle(thread.title);
      event.currentTarget.blur();
      setEditing(false);
    }
  }

  const rowTone = active
    ? "bg-[var(--hover)] text-[var(--text)]"
    : "text-[var(--muted)] hover:bg-[var(--hover)] hover:text-[var(--text)] focus-within:bg-[var(--hover)] focus-within:text-[var(--text)]";

  return (
    <div className={`group relative flex h-9 items-center rounded-xl ${rowTone}`}>
      {editing ? (
        <form
          className="h-full min-w-0 flex-1"
          onSubmit={(event) => {
            event.preventDefault();
            inputRef.current?.blur();
          }}
        >
          <label htmlFor={`thread-title-${thread.id}`} className="sr-only">
            会話の名前
          </label>
          <input
            ref={inputRef}
            id={`thread-title-${thread.id}`}
            value={title}
            maxLength={120}
            disabled={submitting}
            autoComplete="off"
            className="h-full w-full rounded-xl bg-transparent px-2.5 text-sm font-medium text-[var(--text)] outline-none disabled:cursor-wait disabled:opacity-60"
            onBlur={() => {
              if (cancelBlurSaveRef.current) {
                cancelBlurSaveRef.current = false;
                return;
              }
              void saveRename();
            }}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={handleRenameKeyDown}
          />
        </form>
      ) : (
        <button
          type="button"
          aria-current={active ? "page" : undefined}
          className="h-full min-w-0 flex-1 truncate rounded-xl pl-2.5 pr-10 text-left text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
          onClick={onSelect}
        >
          {thread.title}
        </button>
      )}

      {!editing ? (
        <Popover collisionPadding={8} gutter={6} placement="bottom-start">
          <PopoverTrigger
            aria-label={`${thread.title}の操作`}
            className="absolute right-0.5 grid size-8 place-items-center rounded-[10px] text-[var(--muted)] opacity-100 transition-[color,opacity] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] aria-expanded:text-[var(--text)] lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100 lg:aria-expanded:opacity-100"
          >
            <Ellipsis aria-hidden="true" className="size-[18px]" />
          </PopoverTrigger>

          <PopoverContent
            ref={contentRef}
            role="dialog"
            aria-label={`${thread.title}の操作`}
          >
            <div className="grid gap-0.5">
              <button
                type="button"
                className="flex h-9 w-full items-center rounded-xl pr-3 text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
                onClick={startRename}
              >
                <span className="grid w-9 shrink-0 place-items-center">
                  <Pencil aria-hidden="true" className="size-4" />
                </span>
                <span>名前を変更</span>
              </button>
              <button
                type="button"
                disabled={submitting}
                className="flex h-9 w-full items-center rounded-xl pr-3 text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
                onClick={() => void archive()}
              >
                <span className="grid w-9 shrink-0 place-items-center">
                  <Archive aria-hidden="true" className="size-4" />
                </span>
                <span>アーカイブ</span>
              </button>
            </div>
          </PopoverContent>
        </Popover>
      ) : null}
    </div>
  );
}
