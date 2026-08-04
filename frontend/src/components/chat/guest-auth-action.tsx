"use client";

import type { ReactNode } from "react";

import { PopoverClose } from "@/components/ui/popover";

type GuestAuthActionProps = {
  children: ReactNode;
  className: string;
  closePopover?: boolean;
  onClick: () => void;
  tone: "primary" | "secondary";
};

const TONE_CLASS_NAMES = {
  primary:
    "bg-[var(--primary)] text-[var(--on-primary)] hover:bg-[var(--primary-hover)]",
  secondary:
    "border border-[var(--border)] bg-[var(--button-background)] text-[var(--text)] hover:bg-[var(--button-hover)]",
} as const;

export function GuestAuthAction({
  children,
  className,
  closePopover = false,
  onClick,
  tone,
}: GuestAuthActionProps) {
  const styles = `${className} h-9 items-center justify-center whitespace-nowrap rounded-full px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] ${TONE_CLASS_NAMES[tone]}`;

  if (closePopover) {
    return (
      <PopoverClose className={styles} onClick={onClick}>
        {children}
      </PopoverClose>
    );
  }

  return (
    <button type="button" className={styles} onClick={onClick}>
      {children}
    </button>
  );
}
