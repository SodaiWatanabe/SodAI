"use client";

import { Check, ChevronDown, ChevronRight } from "lucide-react";
import Image from "next/image";
import { useRef, useState } from "react";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useHoverPopover } from "@/components/ui/use-hover-popover";
import type { AvailableAnswerer } from "@/lib/chat/types";

type AnswererSelectorProps = {
  answerer?: AvailableAnswerer["id"];
  answerers: AvailableAnswerer[];
  onChange: (answerer: AvailableAnswerer["id"]) => void;
};

function AnswererOption({
  checked,
  onSelect,
  option,
}: {
  checked: boolean;
  onSelect: () => void;
  option: AvailableAnswerer;
}) {
  return (
    <PopoverClose
      role="menuitemradio"
      aria-checked={checked}
      className={`flex w-full items-start gap-3 rounded-[13px] px-3 py-2.5 text-left transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)] ${
        checked ? "bg-[var(--hover)]" : ""
      }`}
      onClick={onSelect}
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
}

function AnswererSubmenu({
  description,
  emphasizeLabel = false,
  label,
  onSelect,
  options,
  selectedId,
}: {
  description?: string;
  emphasizeLabel?: boolean;
  label: string;
  onSelect: (answerer: AvailableAnswerer["id"]) => void;
  options: AvailableAnswerer[];
  selectedId?: AvailableAnswerer["id"];
}) {
  const lastPointerTypeRef = useRef("");
  const {
    clearCloseTimer,
    closeAfterHover,
    open,
    openOnHover,
    setOpen,
  } = useHoverPopover(140);

  return (
    <Popover
      collisionPadding={6}
      gutter={6}
      open={open}
      placement="right-start"
      onOpenChange={setOpen}
    >
      <div
        onPointerEnter={(event) => openOnHover(event.pointerType)}
        onPointerLeave={(event) => closeAfterHover(event.pointerType)}
      >
        <PopoverTrigger
          role="menuitem"
          aria-haspopup="menu"
          className="flex min-h-9 w-full items-center rounded-xl px-3 py-2 text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--focus)]"
          onClick={(event) => {
            if (
              event.detail > 0 &&
              lastPointerTypeRef.current === "mouse"
            ) {
              event.preventDefault();
              clearCloseTimer();
              setOpen(true);
            }
          }}
          onPointerDown={(event) => {
            lastPointerTypeRef.current = event.pointerType;
          }}
        >
          <span className="min-w-0 flex-1">
            <span className={emphasizeLabel ? "block font-medium" : "block"}>
              {label}
            </span>
            {description ? (
              <span className="mt-0.5 block text-xs leading-4 text-[var(--muted)]">
                {description}
              </span>
            ) : null}
          </span>
          <ChevronRight
            aria-hidden="true"
            className="size-4 shrink-0 text-[var(--muted)]"
          />
        </PopoverTrigger>
        <PopoverContent
          role="menu"
          aria-label={label}
          className="w-52"
          onPointerEnter={(event) => openOnHover(event.pointerType)}
          onPointerLeave={(event) => closeAfterHover(event.pointerType)}
        >
          <div className="grid gap-0.5">
            {options.map((option) => (
              <AnswererOption
                key={option.id}
                checked={option.id === selectedId}
                option={option}
                onSelect={() => onSelect(option.id)}
              />
            ))}
          </div>
        </PopoverContent>
      </div>
    </Popover>
  );
}

export function AnswererSelector({
  answerer,
  answerers,
  onChange,
}: AnswererSelectorProps) {
  const { authenticated, openAuth } = useChatAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const selected = answerers.find((option) => option.id === answerer);
  const currentAnswerers = answerers.filter(
    (option) => option.kind === "ai" && !option.is_legacy,
  );
  const humanAnswerers = answerers.filter(
    (option) => option.kind === "human" && !option.is_legacy,
  );
  const pastAnswerers = answerers.filter((option) => option.is_legacy);
  const label = selected?.name ?? "モデル";

  return (
    <Popover
      gutter={6}
      open={menuOpen}
      placement="bottom-start"
      onOpenChange={setMenuOpen}
    >
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
                <AnswererOption
                  key={option.id}
                  checked={checked}
                  option={option}
                  onSelect={() => onChange(option.id)}
                />
              );
            })}
            {humanAnswerers.length > 0 || pastAnswerers.length > 0 ? (
              <div className="mx-2 my-1 h-px bg-[var(--divider)]" />
            ) : null}
            {pastAnswerers.length > 0 ? (
              <AnswererSubmenu
                label="過去のAIモデル"
                options={pastAnswerers}
                selectedId={selected?.id}
                onSelect={(id) => {
                  onChange(id);
                  setMenuOpen(false);
                }}
              />
            ) : null}
            {pastAnswerers.length > 0 && humanAnswerers.length > 0 ? (
              <div className="mx-2 my-1 h-px bg-[var(--divider)]" />
            ) : null}
            {humanAnswerers.length > 0 ? (
              <AnswererSubmenu
                description="人類の底力。"
                emphasizeLabel
                label="ヒト"
                options={humanAnswerers}
                selectedId={selected?.id}
                onSelect={(id) => {
                  onChange(id);
                  setMenuOpen(false);
                }}
              />
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
