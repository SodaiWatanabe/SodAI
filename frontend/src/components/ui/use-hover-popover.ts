"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useHoverPopover(closeDelay = 120) {
  const [open, setOpen] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearCloseTimer = useCallback(() => {
    if (closeTimerRef.current === null) return;
    clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  }, []);

  const openOnHover = useCallback(
    (pointerType: string) => {
      if (pointerType !== "mouse") return;
      clearCloseTimer();
      setOpen(true);
    },
    [clearCloseTimer],
  );

  const closeAfterHover = useCallback(
    (pointerType: string) => {
      if (pointerType !== "mouse") return;
      clearCloseTimer();
      closeTimerRef.current = setTimeout(() => {
        setOpen(false);
        closeTimerRef.current = null;
      }, closeDelay);
    },
    [clearCloseTimer, closeDelay],
  );

  useEffect(() => () => clearCloseTimer(), [clearCloseTimer]);

  return {
    clearCloseTimer,
    closeAfterHover,
    open,
    openOnHover,
    setOpen,
  };
}
