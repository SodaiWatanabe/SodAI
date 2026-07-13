"use client";

import { Check, ChevronDown } from "lucide-react";
import Image from "next/image";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { AvailableModel } from "@/lib/chat/types";

type ModelSelectorProps = {
  model?: AvailableModel["id"];
  models: AvailableModel[];
  onChange: (model: AvailableModel["id"]) => void;
};

export function ModelSelector({
  model,
  models,
  onChange,
}: ModelSelectorProps) {
  const { authenticated, openAuth } = useChatAuth();
  const selected = models.find((option) => option.id === model);
  const label = selected?.name ?? "モデル";

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
        role={authenticated ? "radiogroup" : "dialog"}
        aria-label={authenticated ? "モデル" : "よりスマートな回答"}
        className={authenticated ? "" : "overflow-hidden"}
        style={authenticated ? undefined : { padding: 0 }}
      >
        {authenticated ? (
          <div className="grid gap-0.5">
            {models.map((option) => {
              const checked = option.id === selected?.id;
              return (
                <PopoverClose
                  key={option.id}
                  role="radio"
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
