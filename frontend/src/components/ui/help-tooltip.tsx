"use client";

import { CircleHelp } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";

import {
  Popover,
  PopoverContent,
  type PopoverPlacement,
  PopoverTrigger,
} from "@/components/ui/popover";

const CLOSE_DELAY_MS = 120;

export function HelpTooltip({
  children,
  label,
  placement = "top-end",
}: {
  children: ReactNode;
  label: string;
  placement?: PopoverPlacement;
}) {
  const contentRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastPointerTypeRef = useRef("");

  function clearCloseTimer() {
    if (closeTimerRef.current === null) return;
    clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  }

  function setOpen(open: boolean) {
    const content = contentRef.current;
    if (!content) return;
    const currentlyOpen = content.matches(":popover-open");
    if (open && !currentlyOpen) content.showPopover();
    if (!open && currentlyOpen) content.hidePopover();
  }

  function openOnHover(pointerType: string) {
    if (pointerType !== "mouse") return;
    clearCloseTimer();
    setOpen(true);
  }

  function closeAfterHover(pointerType: string) {
    if (pointerType !== "mouse") return;
    clearCloseTimer();
    closeTimerRef.current = setTimeout(() => {
      setOpen(false);
      closeTimerRef.current = null;
    }, CLOSE_DELAY_MS);
  }

  useEffect(() => () => clearCloseTimer(), []);

  return (
    <Popover collisionPadding={8} gutter={6} placement={placement}>
      <span
        className="inline-flex"
        onPointerEnter={(event) => openOnHover(event.pointerType)}
        onPointerLeave={(event) => closeAfterHover(event.pointerType)}
      >
        <PopoverTrigger
          aria-label={label}
          className="grid size-6 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
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
          <CircleHelp aria-hidden="true" className="size-4" />
        </PopoverTrigger>
        <PopoverContent
          ref={contentRef}
          role="tooltip"
          className="w-64 px-3 py-2.5 text-sm leading-5"
          onPointerEnter={(event) => openOnHover(event.pointerType)}
          onPointerLeave={(event) => closeAfterHover(event.pointerType)}
        >
          {children}
        </PopoverContent>
      </span>
    </Popover>
  );
}
