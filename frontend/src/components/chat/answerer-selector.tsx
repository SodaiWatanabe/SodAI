"use client";

import { Check, ChevronDown, ChevronRight } from "lucide-react";
import Image from "next/image";
import { useEffect, useRef } from "react";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { AvailableAnswerer } from "@/lib/chat/types";

type AnswererSelectorProps = {
  answerer?: AvailableAnswerer["id"];
  answerers: AvailableAnswerer[];
  onChange: (answerer: AvailableAnswerer["id"]) => void;
};

export function AnswererSelector({
  answerer,
  answerers,
  onChange,
}: AnswererSelectorProps) {
  const { authenticated, openAuth } = useChatAuth();
  const contentRef = useRef<HTMLDivElement>(null);
  const pastContentRef = useRef<HTMLDivElement>(null);
  const pastCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selected = answerers.find((option) => option.id === answerer);
  const currentAnswerers = answerers.filter((option) => option.is_default);
  const pastAnswerers = answerers.filter((option) => !option.is_default);
  const label = selected?.name ?? "モデル";

  function clearPastCloseTimer() {
    if (pastCloseTimerRef.current === null) return;
    clearTimeout(pastCloseTimerRef.current);
    pastCloseTimerRef.current = null;
  }

  function setPastPopoverOpen(open: boolean) {
    const content = pastContentRef.current;
    if (!content) return;
    const currentlyOpen = content.matches(":popover-open");
    if (open && !currentlyOpen) content.showPopover();
    if (!open && currentlyOpen) content.hidePopover();
  }

  function openPastOnHover(pointerType: string) {
    if (pointerType !== "mouse") return;
    clearPastCloseTimer();
    setPastPopoverOpen(true);
  }

  function closePastAfterHover(pointerType: string) {
    if (pointerType !== "mouse") return;
    clearPastCloseTimer();
    pastCloseTimerRef.current = setTimeout(() => {
      setPastPopoverOpen(false);
      pastCloseTimerRef.current = null;
    }, 140);
  }

  useEffect(() => () => clearPastCloseTimer(), []);

  return (
    <Popover placement="bottom-start" gutter={6}>
      <PopoverTrigger
        disabled={!selected}
        aria-label={`モデル: ${label}`}
        className="group flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:cursor-default disabled:opacity-50"
      >
        <span>{label}</span>
        <ChevronDown
          aria-hidden="true"
          className="size-3.5 text-[var(--muted)] transition-transform group-aria-expanded:rotate-180"
        />
      </PopoverTrigger>

      <PopoverContent
        ref={contentRef}
        role={authenticated ? "menu" : "dialog"}
        aria-label={authenticated ? "モデル" : "よりスマートな回答"}
        className={authenticated ? "w-52" : "overflow-hidden"}
        style={authenticated ? undefined : { padding: 0 }}
      >
        {authenticated ? (
          <div className="grid gap-0.5">
            {currentAnswerers.map((option) => {
              const checked = option.id === selected?.id;
              return (
                <PopoverClose
                  key={option.id}
                  role="menuitemradio"
                  aria-checked={checked}
                  className={`flex w-full items-start gap-3 rounded-[13px] px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] ${
                    checked ? "bg-[var(--hover)]" : ""
                  }`}
                  onClick={() => onChange(option.id)}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-[var(--text)]">
                      {option.name}
                    </span>
                    <span className="mt-0.5 block text-xs leading-4 text-[var(--muted)]">
                      {option.description}
                    </span>
                  </span>
                  <span className="grid size-5 shrink-0 place-items-center text-[var(--text)]">
                    {checked ? <Check aria-hidden="true" className="size-3.5" /> : null}
                  </span>
                </PopoverClose>
              );
            })}
            {pastAnswerers.length > 0 ? (
              <>
                <div className="mx-2 my-1 h-px bg-[var(--divider)]" />
                <Popover
                  collisionPadding={6}
                  gutter={6}
                  placement="right-start"
                >
                  <div
                    onPointerEnter={(event) => openPastOnHover(event.pointerType)}
                    onPointerLeave={(event) =>
                      closePastAfterHover(event.pointerType)
                    }
                  >
                    <PopoverTrigger
                      role="menuitem"
                      aria-haspopup="menu"
                      className="flex h-9 w-full items-center rounded-xl px-3 text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
                    >
                      <span className="min-w-0 flex-1">過去のモデル</span>
                      <ChevronRight
                        aria-hidden="true"
                        className="size-4 shrink-0 text-[var(--muted)]"
                      />
                    </PopoverTrigger>
                    <PopoverContent
                      ref={pastContentRef}
                      role="menu"
                      aria-label="過去のモデル"
                      className="w-52"
                      onPointerEnter={(event) =>
                        openPastOnHover(event.pointerType)
                      }
                      onPointerLeave={(event) =>
                        closePastAfterHover(event.pointerType)
                      }
                    >
                      <div className="grid gap-0.5">
                        {pastAnswerers.map((option) => {
                          const checked = option.id === selected?.id;
                          return (
                            <PopoverClose
                              key={option.id}
                              role="menuitemradio"
                              aria-checked={checked}
                              className={`flex w-full items-start gap-3 rounded-[13px] px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] ${
                                checked ? "bg-[var(--hover)]" : ""
                              }`}
                              onClick={() => {
                                onChange(option.id);
                                contentRef.current?.hidePopover();
                              }}
                            >
                              <span className="min-w-0 flex-1">
                                <span className="block text-sm font-medium text-[var(--text)]">
                                  {option.name}
                                </span>
                                <span className="mt-0.5 block text-xs leading-4 text-[var(--muted)]">
                                  {option.description}
                                </span>
                              </span>
                              <span className="grid size-5 shrink-0 place-items-center text-[var(--text)]">
                                {checked ? (
                                  <Check aria-hidden="true" className="size-3.5" />
                                ) : null}
                              </span>
                            </PopoverClose>
                          );
                        })}
                      </div>
                    </PopoverContent>
                  </div>
                </Popover>
              </>
            ) : null}
          </div>
        ) : (
          <div className="w-[min(20rem,calc(100vw-1.5rem))]">
            <Image
              src="/images/model-access-nihonga.png"
              alt=""
              width={640}
              height={244}
              className="h-[122px] w-full object-cover"
            />
            <div className="px-4 pb-4 pt-5">
              <p className="text-lg font-semibold tracking-[-0.02em] text-[var(--text)]">
                よりスマートに回答
              </p>
              <p className="mt-1 text-sm leading-5 text-[var(--muted)]">
                ログインすると、より性能の高いモデルにアクセスできます。
              </p>
              <div className="mt-5 flex gap-2">
                <PopoverClose
                  className="h-9 rounded-full bg-[var(--primary)] px-4 text-xs font-medium text-[var(--on-primary)] transition-colors hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
                  onClick={openAuth}
                >
                  ログイン
                </PopoverClose>
                <PopoverClose
                  className="h-9 rounded-full border border-[var(--border)] bg-[var(--button-background)] px-4 text-xs font-medium text-[var(--text)] transition-colors hover:bg-[var(--button-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
                  onClick={openAuth}
                >
                  アカウントを作成
                </PopoverClose>
              </div>
            </div>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
