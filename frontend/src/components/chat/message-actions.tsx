"use client";

import {
  Brain,
  Check,
  Copy,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { MessageBrain } from "@/components/chat/message-brain";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useHoverPopover } from "@/components/ui/use-hover-popover";
import { nextResponseEvaluation } from "@/lib/chat/response-evaluation";
import type { ResponseEvaluationValue } from "@/lib/chat/types";

type CopyStatus = "copied" | "failed" | "idle";

type MessageActionsProps = {
  brain: MessageBrain;
  content: string;
  evaluation?: ResponseEvaluationValue | null;
  onEvaluationChange?: (
    value: ResponseEvaluationValue | null,
  ) => Promise<void>;
  onRegenerate?: () => Promise<void>;
  regenerating?: boolean;
};

const COPY_STATUS_DURATION = 1_600;
const actionClassName =
  "grid size-8 place-items-center rounded-xl text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]";

function BrainDisclosure({ brain }: { brain: MessageBrain }) {
  const lastPointerTypeRef = useRef("");
  const {
    clearCloseTimer,
    closeAfterHover,
    open,
    openOnHover,
    setOpen,
  } = useHoverPopover();
  const brainLabel = `使用したモデル: ${brain.name}`;

  return (
    <Popover
      collisionPadding={8}
      gutter={4}
      open={open}
      placement="top-start"
      onOpenChange={setOpen}
    >
      <div
        className="inline-flex"
        onPointerEnter={(event) => openOnHover(event.pointerType)}
        onPointerLeave={(event) => closeAfterHover(event.pointerType)}
      >
        <PopoverTrigger
          aria-label={brainLabel}
          className={actionClassName}
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
          <Brain aria-hidden="true" className="size-4" />
        </PopoverTrigger>
        <PopoverContent
          role="tooltip"
          className="w-max min-w-40 max-w-64 px-3 py-2.5"
          onPointerEnter={(event) => openOnHover(event.pointerType)}
          onPointerLeave={(event) => closeAfterHover(event.pointerType)}
        >
          <p className="text-xs font-medium text-[var(--muted)]">
            使用したモデル
          </p>
          <p className="mt-0.5 text-sm font-medium text-[var(--text)]">
            {brain.name}
          </p>
        </PopoverContent>
      </div>
    </Popover>
  );
}

function CopyAction({ content }: { content: string }) {
  const {
    clearCloseTimer,
    closeAfterHover,
    open,
    openOnHover,
    setOpen,
  } = useHoverPopover();
  const mountedRef = useRef(false);
  const requestSequenceRef = useRef(0);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [copyStatus, setCopyStatus] = useState<CopyStatus>("idle");

  function clearResetTimer() {
    if (resetTimerRef.current === null) return;
    clearTimeout(resetTimerRef.current);
    resetTimerRef.current = null;
  }

  function showCopyStatus(status: Exclude<CopyStatus, "idle">) {
    clearCloseTimer();
    clearResetTimer();
    setCopyStatus(status);
    setOpen(true);
    resetTimerRef.current = setTimeout(() => {
      if (!mountedRef.current) return;
      setCopyStatus("idle");
      setOpen(false);
      resetTimerRef.current = null;
    }, COPY_STATUS_DURATION);
  }

  async function copyContent() {
    const requestSequence = ++requestSequenceRef.current;
    clearCloseTimer();
    clearResetTimer();
    setCopyStatus("idle");
    setOpen(true);

    try {
      await navigator.clipboard.writeText(content);
      if (
        !mountedRef.current ||
        requestSequence !== requestSequenceRef.current
      ) {
        return;
      }
      showCopyStatus("copied");
    } catch {
      if (
        !mountedRef.current ||
        requestSequence !== requestSequenceRef.current
      ) {
        return;
      }
      showCopyStatus("failed");
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      requestSequenceRef.current += 1;
      clearResetTimer();
    };
  }, []);

  const copyLabel =
    copyStatus === "copied"
      ? "コピーしました"
      : copyStatus === "failed"
        ? "コピーできませんでした"
        : "本文をコピー";

  return (
    <Popover
      collisionPadding={8}
      gutter={4}
      open={open}
      placement="top-start"
      onOpenChange={setOpen}
    >
      <div
        className="inline-flex"
        onPointerEnter={(event) => openOnHover(event.pointerType)}
        onPointerLeave={(event) => {
          if (copyStatus === "idle") closeAfterHover(event.pointerType);
        }}
      >
        <PopoverTrigger
          aria-label={copyLabel}
          className={`${actionClassName} ${copyStatus === "failed" ? "text-[var(--danger-text)]" : ""}`}
          onClick={(event) => {
            event.preventDefault();
            void copyContent();
          }}
        >
          {copyStatus === "copied" ? (
            <Check aria-hidden="true" className="size-4" />
          ) : (
            <Copy aria-hidden="true" className="size-4" />
          )}
        </PopoverTrigger>
        <PopoverContent
          role="tooltip"
          className={`w-max px-3 py-2 text-xs font-medium ${copyStatus === "failed" ? "text-[var(--danger-text)]" : ""}`}
          onPointerEnter={(event) => openOnHover(event.pointerType)}
          onPointerLeave={(event) => {
            if (copyStatus === "idle") closeAfterHover(event.pointerType);
          }}
        >
          {copyLabel}
        </PopoverContent>
        <span role="status" aria-live="polite" className="sr-only">
          {copyStatus === "idle" ? "" : copyLabel}
        </span>
      </div>
    </Popover>
  );
}

function EvaluationActions({
  evaluation,
  onChange,
}: {
  evaluation: ResponseEvaluationValue | null;
  onChange: (value: ResponseEvaluationValue | null) => Promise<void>;
}) {
  const [pending, setPending] = useState(false);

  async function toggle(value: ResponseEvaluationValue) {
    if (pending) return;
    setPending(true);
    try {
      await onChange(nextResponseEvaluation(evaluation, value));
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <EvaluationAction
        active={evaluation === "positive"}
        disabled={pending}
        label="良い回答"
        value="positive"
        onSelect={toggle}
      />
      <EvaluationAction
        active={evaluation === "negative"}
        disabled={pending}
        label="良くない回答"
        value="negative"
        onSelect={toggle}
      />
    </>
  );
}

function EvaluationAction({
  active,
  disabled,
  label,
  onSelect,
  value,
}: {
  active: boolean;
  disabled: boolean;
  label: string;
  onSelect: (value: ResponseEvaluationValue) => Promise<void>;
  value: ResponseEvaluationValue;
}) {
  const {
    clearCloseTimer,
    closeAfterHover,
    open,
    openOnHover,
    setOpen,
  } = useHoverPopover();
  const Icon = value === "positive" ? ThumbsUp : ThumbsDown;

  return (
    <Popover
      collisionPadding={8}
      gutter={4}
      open={open}
      placement="top-start"
      onOpenChange={setOpen}
    >
      <div
        className="inline-flex"
        onPointerEnter={(event) => openOnHover(event.pointerType)}
        onPointerLeave={(event) => closeAfterHover(event.pointerType)}
      >
        <PopoverTrigger
          aria-label={label}
          aria-pressed={active}
          className={`${actionClassName} disabled:pointer-events-none disabled:opacity-50 ${
            active ? "text-[var(--text)]" : ""
          }`}
          disabled={disabled}
          onClick={(event) => {
            event.preventDefault();
            clearCloseTimer();
            void onSelect(value);
          }}
        >
          <Icon
            aria-hidden="true"
            className={`size-4 ${active ? "fill-current" : ""}`}
          />
        </PopoverTrigger>
        <PopoverContent
          role="tooltip"
          className="w-max px-3 py-2 text-xs font-medium"
          onPointerEnter={(event) => openOnHover(event.pointerType)}
          onPointerLeave={(event) => closeAfterHover(event.pointerType)}
        >
          {label}
        </PopoverContent>
      </div>
    </Popover>
  );
}

function RegenerateAction({
  disabled,
  onRegenerate,
}: {
  disabled: boolean;
  onRegenerate: () => Promise<void>;
}) {
  const {
    clearCloseTimer,
    closeAfterHover,
    open,
    openOnHover,
    setOpen,
  } = useHoverPopover();
  const [pending, setPending] = useState(false);
  const unavailable = disabled || pending;

  async function regenerate() {
    if (unavailable) return;
    clearCloseTimer();
    setPending(true);
    try {
      await onRegenerate();
    } finally {
      setPending(false);
    }
  }

  return (
    <Popover
      collisionPadding={8}
      gutter={4}
      open={open}
      placement="top-start"
      onOpenChange={setOpen}
    >
      <div
        className="inline-flex"
        onPointerEnter={(event) => openOnHover(event.pointerType)}
        onPointerLeave={(event) => closeAfterHover(event.pointerType)}
      >
        <PopoverTrigger
          aria-label="回答を再生成"
          className={`${actionClassName} disabled:pointer-events-none disabled:opacity-50`}
          disabled={unavailable}
          onClick={(event) => {
            event.preventDefault();
            void regenerate();
          }}
        >
          <RefreshCw aria-hidden="true" className="size-4" />
        </PopoverTrigger>
        <PopoverContent
          role="tooltip"
          className="w-max px-3 py-2 text-xs font-medium"
          onPointerEnter={(event) => openOnHover(event.pointerType)}
          onPointerLeave={(event) => closeAfterHover(event.pointerType)}
        >
          再生成
        </PopoverContent>
      </div>
    </Popover>
  );
}

export function MessageActions({
  brain,
  content,
  evaluation,
  onEvaluationChange,
  onRegenerate,
  regenerating = false,
}: MessageActionsProps) {
  return (
    <div className="-ml-1.5 mt-1.5 flex h-8 items-center gap-0.5 whitespace-normal leading-none">
      <CopyAction content={content} />
      {onEvaluationChange ? (
        <EvaluationActions
          evaluation={evaluation ?? null}
          onChange={onEvaluationChange}
        />
      ) : null}
      <BrainDisclosure brain={brain} />
      {onRegenerate ? (
        <RegenerateAction
          disabled={regenerating}
          onRegenerate={onRegenerate}
        />
      ) : null}
    </div>
  );
}
