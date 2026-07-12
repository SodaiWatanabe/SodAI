"use client";

import { Archive, Ellipsis, Pencil } from "lucide-react";
import {
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useToast } from "@/components/ui/toast-provider";
import type { ConversationSummary } from "@/lib/chat/types";

type ConversationListItemProps = {
  active: boolean;
  conversation: ConversationSummary;
  onArchive: () => void;
  onSelect: () => void;
};

type MenuView = "actions" | "archive" | "rename";

export function ConversationListItem({
  active,
  conversation,
  onArchive,
  onSelect,
}: ConversationListItemProps) {
  const { archiveConversation, renameConversation } = useChatData();
  const { showToast } = useToast();
  const contentRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [menuView, setMenuView] = useState<MenuView>("actions");
  const [title, setTitle] = useState(conversation.title);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (menuView !== "rename") return;
    const frame = requestAnimationFrame(() => {
      inputRef.current?.focus({ preventScroll: true });
      inputRef.current?.select();
    });
    return () => cancelAnimationFrame(frame);
  }, [menuView]);

  function closePopover() {
    contentRef.current?.hidePopover();
  }

  function showRename() {
    setTitle(conversation.title);
    setMenuView("rename");
  }

  async function submitRename(event: FormEvent) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle || nextTitle === conversation.title || submitting) {
      if (nextTitle === conversation.title) closePopover();
      return;
    }
    setSubmitting(true);
    try {
      await renameConversation(conversation.id, nextTitle);
      closePopover();
    } catch {
      showToast({
        id: `conversation-rename-${conversation.id}`,
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
      await archiveConversation(conversation.id);
      closePopover();
      onArchive();
    } catch {
      showToast({
        id: `conversation-archive-${conversation.id}`,
        message: "会話をアーカイブできませんでした。",
        tone: "error",
      });
      setSubmitting(false);
    }
  }

  function handleRenameKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    setMenuView("actions");
  }

  const rowTone = active
    ? "bg-[var(--hover)] text-[var(--text)]"
    : "text-[var(--muted)] hover:bg-[var(--hover)] hover:text-[var(--text)] focus-within:bg-[var(--hover)] focus-within:text-[var(--text)]";

  return (
    <div className={`group relative flex h-9 items-center rounded-xl ${rowTone}`}>
      <button
        type="button"
        aria-current={active ? "page" : undefined}
        className="h-full min-w-0 flex-1 truncate rounded-xl pl-2.5 pr-10 text-left text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
        onClick={onSelect}
      >
        {conversation.title}
      </button>

      <Popover
        collisionPadding={8}
        gutter={6}
        placement="bottom-start"
        onOpenChange={(open) => {
          if (open) return;
          setMenuView("actions");
          setTitle(conversation.title);
        }}
      >
        <PopoverTrigger
          aria-label={`${conversation.title}の操作`}
          className="absolute right-0.5 grid size-8 place-items-center rounded-[10px] text-[var(--muted)] opacity-100 transition-[color,opacity] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] aria-expanded:text-[var(--text)] lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100 lg:aria-expanded:opacity-100"
        >
          <Ellipsis aria-hidden="true" className="size-[18px]" />
        </PopoverTrigger>

        <PopoverContent
          ref={contentRef}
          role="dialog"
          aria-label={`${conversation.title}の操作`}
          className="w-56 rounded-[16px]"
        >
          {menuView === "actions" ? (
            <div className="grid gap-0.5">
              <button
                type="button"
                className="flex h-9 w-full items-center rounded-xl text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
                onClick={showRename}
              >
                <span className="grid w-9 shrink-0 place-items-center">
                  <Pencil aria-hidden="true" className="size-4" />
                </span>
                <span>名前を変更</span>
              </button>
              <button
                type="button"
                className="flex h-9 w-full items-center rounded-xl text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
                onClick={() => setMenuView("archive")}
              >
                <span className="grid w-9 shrink-0 place-items-center">
                  <Archive aria-hidden="true" className="size-4" />
                </span>
                <span>会話をアーカイブ</span>
              </button>
            </div>
          ) : null}

          {menuView === "rename" ? (
            <form className="p-1" onSubmit={submitRename}>
              <label
                htmlFor={`conversation-title-${conversation.id}`}
                className="mb-2 block px-1 text-xs font-medium text-[var(--muted)]"
              >
                会話の名前
              </label>
              <input
                ref={inputRef}
                id={`conversation-title-${conversation.id}`}
                value={title}
                maxLength={120}
                disabled={submitting}
                autoComplete="off"
                className="h-9 w-full rounded-[10px] border border-[var(--field-border)] bg-[var(--surface)] px-3 text-sm text-[var(--text)] outline-none focus:border-[var(--focus)]"
                onChange={(event) => setTitle(event.target.value)}
                onKeyDown={handleRenameKeyDown}
              />
              <div className="mt-2 flex justify-end gap-1">
                <button
                  type="button"
                  className="h-8 rounded-[10px] px-3 text-xs font-medium text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
                  onClick={() => setMenuView("actions")}
                >
                  戻る
                </button>
                <button
                  type="submit"
                  disabled={!title.trim() || submitting}
                  className="h-8 rounded-[10px] bg-[var(--primary)] px-3 text-xs font-medium text-[var(--on-primary)] transition-opacity disabled:opacity-35"
                >
                  {submitting ? "保存中…" : "保存"}
                </button>
              </div>
            </form>
          ) : null}

          {menuView === "archive" ? (
            <div className="p-2">
              <p className="text-sm font-medium text-[var(--text)]">
                この会話をアーカイブしますか？
              </p>
              <p className="mt-1 text-xs leading-5 text-[var(--muted)]">
                会話一覧から非表示になります。
              </p>
              <div className="mt-3 flex justify-end gap-1">
                <button
                  type="button"
                  disabled={submitting}
                  className="h-8 rounded-[10px] px-3 text-xs font-medium text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:opacity-35"
                  onClick={() => setMenuView("actions")}
                >
                  戻る
                </button>
                <button
                  type="button"
                  disabled={submitting}
                  className="h-8 rounded-[10px] bg-[var(--primary)] px-3 text-xs font-medium text-[var(--on-primary)] transition-opacity disabled:opacity-35"
                  onClick={() => void archive()}
                >
                  {submitting ? "処理中…" : "アーカイブ"}
                </button>
              </div>
            </div>
          ) : null}
        </PopoverContent>
      </Popover>
    </div>
  );
}
