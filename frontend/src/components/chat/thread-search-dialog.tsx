"use client";

import { Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { SearchHighlight } from "@/components/chat/search-highlight";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import {
  ModalDialog,
  type ModalDialogHandle,
} from "@/components/ui/modal-dialog";
import type { ThreadSearchHit } from "@/lib/chat/types";
import { useChatApi } from "@/lib/chat/use-chat-api";

const SEARCH_DEBOUNCE_MS = 250;
const ACTIVITY_DATE_FORMATTER = new Intl.DateTimeFormat("ja-JP", {
  dateStyle: "medium",
});

type ThreadSearchDialogProps = {
  onClose: () => void;
  onSelect: (hit: ThreadSearchHit, query: string) => void;
};

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function formatActivity(value: string) {
  return ACTIVITY_DATE_FORMATTER.format(new Date(value));
}

export function ThreadSearchDialog({
  onClose,
  onSelect,
}: ThreadSearchDialogProps) {
  const { searchThreads } = useChatApi();
  const dialogRef = useRef<ModalDialogHandle>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const inputId = useId();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ThreadSearchHit[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const normalizedQuery = query.trim();

  useEffect(() => {
    const frame = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!normalizedQuery) return;
    const controller = new AbortController();
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(false);
      void searchThreads(normalizedQuery, 20, controller.signal).then(
        (page) => {
          if (cancelled) return;
          setResults(page.items);
          setHasMore(page.has_more);
          setLoading(false);
        },
        (reason: unknown) => {
          if (cancelled || isAbortError(reason)) return;
          setError(true);
          setLoading(false);
        },
      );
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [normalizedQuery, searchThreads]);

  function updateQuery(nextQuery: string) {
    const nextNormalizedQuery = nextQuery.trim();
    setQuery(nextQuery);
    if (nextNormalizedQuery === normalizedQuery) return;
    setResults([]);
    setHasMore(false);
    setLoading(Boolean(nextNormalizedQuery));
    setError(false);
  }

  function closeDialog() {
    dialogRef.current?.close();
  }

  return (
    <ModalDialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className="h-[calc(100dvh-1rem)] w-[calc(100%-1rem)] max-w-[620px] flex-col overflow-hidden open:flex sm:h-[min(520px,calc(100dvh-2rem))] sm:w-[calc(100%-2rem)]"
      onClose={onClose}
    >
      <header className="relative shrink-0 border-b border-[var(--separator)] px-5 pb-4 pt-5 sm:px-6">
        <div className="pr-10">
          <h2
            id={titleId}
            className="text-[15px] font-semibold tracking-[-0.015em]"
          >
            会話を検索
          </h2>
        </div>
        <button
          type="button"
          aria-label="検索を閉じる"
          className="absolute right-3 top-3 grid size-10 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
          onClick={closeDialog}
        >
          <X aria-hidden="true" className="size-[18px]" />
        </button>

        <div className="group mt-4 flex h-11 items-center gap-2.5 rounded-2xl border border-[var(--field-border)] bg-[var(--field)] px-3.5">
          <Search aria-hidden="true" className="size-[18px] shrink-0 text-[var(--muted)] transition-colors group-focus-within:text-[var(--text)]" />
          <label htmlFor={inputId} className="sr-only">
            検索語
          </label>
          <input
            ref={inputRef}
            id={inputId}
            type="text"
            role="searchbox"
            inputMode="search"
            enterKeyHint="search"
            autoFocus
            value={query}
            maxLength={100}
            autoComplete="off"
            placeholder="キーワードを入力"
            className="min-w-0 flex-1 bg-transparent text-[15px] text-[var(--text)] outline-none placeholder:text-[var(--muted)]"
            onChange={(event) => updateQuery(event.target.value)}
          />
          {query ? (
            <button
              type="button"
              aria-label="検索語を消去"
              className="grid size-7 shrink-0 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
              onClick={() => {
                updateQuery("");
                inputRef.current?.focus();
              }}
            >
              <X aria-hidden="true" className="size-4" />
            </button>
          ) : null}
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2">
        {!normalizedQuery ? (
          <p className="grid min-h-48 place-items-center px-6 text-center text-sm text-[var(--muted)]">
            思い出した言葉を入力してください。
          </p>
        ) : loading ? (
          <div className="grid min-h-48 place-items-center text-[var(--muted)]">
            <IOSSpinner label="会話を検索中" />
          </div>
        ) : error ? (
          <p role="alert" className="grid min-h-48 place-items-center px-6 text-center text-sm text-[var(--danger-text)]">
            会話を検索できませんでした。もう一度お試しください。
          </p>
        ) : results.length === 0 ? (
          <p role="status" className="grid min-h-48 place-items-center px-6 text-center text-sm text-[var(--muted)]">
            一致する会話はありません。
          </p>
        ) : (
          <div aria-label="検索結果" className="space-y-1">
            {results.map((hit) => (
              <button
                key={hit.thread.id}
                type="button"
                className="block w-full rounded-2xl px-3.5 py-3 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
                onClick={() => onSelect(hit, normalizedQuery)}
              >
                <span className="flex items-baseline justify-between gap-4">
                  <span className="min-w-0 truncate text-sm font-semibold text-[var(--text)]">
                    <SearchHighlight
                      query={normalizedQuery}
                      text={hit.thread.title}
                    />
                  </span>
                  <time
                    dateTime={hit.thread.last_activity_at}
                    className="shrink-0 text-xs text-[var(--muted)]"
                  >
                    {formatActivity(hit.thread.last_activity_at)}
                  </time>
                </span>
                <span className="mt-1.5 line-clamp-2 block text-sm leading-5 text-[var(--muted)]">
                  {hit.source === "entry"
                    ? <SearchHighlight
                        query={normalizedQuery}
                        text={hit.snippet}
                      />
                    : "会話の名前に一致"}
                </span>
              </button>
            ))}
            {hasMore ? (
              <p className="px-3.5 py-2 text-xs text-[var(--muted)]">
                新しい20件を表示しています。検索語を追加すると絞り込めます。
              </p>
            ) : null}
          </div>
        )}
        <span className="sr-only" role="status" aria-live="polite">
          {loading
            ? "会話を検索中"
            : normalizedQuery && !error
              ? `${results.length}件の会話が見つかりました`
              : ""}
        </span>
      </div>
    </ModalDialog>
  );
}
