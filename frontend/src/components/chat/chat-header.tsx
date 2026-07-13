"use client";

import { AnswererSelector } from "@/components/chat/answerer-selector";
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
  return (
    <header className="sticky top-0 z-10 h-12 shrink-0 border-b border-[var(--separator)] bg-[var(--canvas)]">
      <div className="mx-auto flex h-full w-full max-w-[760px] items-center px-12 sm:px-8 lg:mx-0 lg:max-w-none lg:px-1.5">
        <AnswererSelector
          answerer={answerer}
          answerers={answerers}
          onChange={onAnswererChange}
        />
      </div>
    </header>
  );
}
