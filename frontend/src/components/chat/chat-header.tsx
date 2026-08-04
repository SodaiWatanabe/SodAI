"use client";

import { AnswererSelector } from "@/components/chat/answerer-selector";
import { useChatAuth } from "@/components/chat/chat-auth-context";
import { GuestAuthAction } from "@/components/chat/guest-auth-action";
import type { AvailableAnswerer } from "@/lib/chat/types";

type ChatHeaderProps = {
  answerer?: AvailableAnswerer["id"];
  answerers: AvailableAnswerer[];
  onAnswererChange: (answerer: AvailableAnswerer["id"]) => void;
};

export function ChatHeader({
  answerer,
  answerers,
  onAnswererChange,
}: ChatHeaderProps) {
  const { authenticated, openAuth } = useChatAuth();

  return (
    <header className="sticky top-0 z-10 h-12 shrink-0 border-b border-[var(--separator)] bg-[var(--canvas)]">
      <div className="mx-auto flex h-full w-full max-w-[760px] items-center pl-12 pr-2.5 sm:px-8 lg:mx-0 lg:max-w-none lg:px-1.5">
        <AnswererSelector
          answerer={answerer}
          answerers={answerers}
          onChange={onAnswererChange}
        />
        {!authenticated ? (
          <div className="ml-auto flex items-center gap-2">
            <GuestAuthAction
              className="inline-flex"
              onClick={openAuth}
              tone="primary"
            >
              ログイン
            </GuestAuthAction>
            <GuestAuthAction
              className="hidden lg:inline-flex"
              onClick={openAuth}
              tone="secondary"
            >
              アカウントを作成
            </GuestAuthAction>
          </div>
        ) : null}
      </div>
    </header>
  );
}
