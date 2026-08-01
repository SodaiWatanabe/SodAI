"use client";

import { CircleHelp } from "lucide-react";
import { type ReactNode, useRef } from "react";

import {
  Popover,
  PopoverContent,
  type PopoverPlacement,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useHoverPopover } from "@/components/ui/use-hover-popover";

export function HelpTooltip({
  children,
  label,
  placement = "top-end",
}: {
  children: ReactNode;
  label: string;
  placement?: PopoverPlacement;
}) {
  const lastPointerTypeRef = useRef("");
  const {
    clearCloseTimer,
    closeAfterHover,
    open,
    openOnHover,
    setOpen,
  } = useHoverPopover();

  return (
    <Popover
      collisionPadding={8}
      gutter={6}
      open={open}
      placement={placement}
      onOpenChange={setOpen}
    >
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
