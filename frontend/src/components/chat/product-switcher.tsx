"use client";

import { Check, ChevronDown } from "lucide-react";

import type { SodaiProduct } from "@/components/chat/chat-frame-route";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

export type { SodaiProduct } from "@/components/chat/chat-frame-route";

const products = [
  { id: "chat" as const, label: "Chat", description: "モデルと会話する。" },
  { id: "brain" as const, label: "Brain", description: "思考を引き受ける。" },
];

export function ProductSwitcher({
  contentVisible,
  onChange,
  product,
}: {
  contentVisible: boolean;
  onChange: (product: SodaiProduct) => void;
  product: SodaiProduct;
}) {
  const current = products.find((item) => item.id === product) ?? products[0];

  return (
    <div
      aria-hidden={!contentVisible}
      inert={!contentVisible}
      className={`absolute left-4 flex h-9 items-center whitespace-nowrap text-lg font-semibold tracking-[-0.025em] text-[var(--text)] transition-opacity duration-150 ${
        contentVisible
          ? "opacity-100 delay-100 motion-reduce:delay-0"
          : "pointer-events-none opacity-0"
      }`}
    >
      <span>SodAI</span>
      <Popover placement="bottom-start" gutter={4}>
        <PopoverTrigger
          aria-label={`${current.label}、機能を切り替える`}
          className="group ml-1 flex h-9 items-center gap-1 rounded-xl px-1 text-[var(--muted)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
        >
          <span>{current.label}</span>
          <ChevronDown
            aria-hidden="true"
            className="ml-0.5 size-3.5 transition-transform group-aria-expanded:rotate-180"
          />
        </PopoverTrigger>
        <PopoverContent role="menu" aria-label="SodAIの機能" className="w-56">
          <div className="grid gap-0.5">
            {products.map((item) => {
              const selected = item.id === product;
              return (
                <PopoverClose
                  key={item.id}
                  role="menuitemradio"
                  aria-checked={selected}
                  className={`flex w-full items-start gap-3 rounded-[13px] px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover)] ${
                    selected ? "bg-[var(--hover)]" : ""
                  }`}
                  onClick={() => onChange(item.id)}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-[var(--text)]">
                      {item.label}
                    </span>
                    <span className="mt-0.5 block text-xs leading-4 text-[var(--muted)]">
                      {item.description}
                    </span>
                  </span>
                  <span className="grid size-5 place-items-center text-[var(--text)]">
                    {selected ? (
                      <Check aria-hidden="true" className="size-3.5" />
                    ) : null}
                  </span>
                </PopoverClose>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
