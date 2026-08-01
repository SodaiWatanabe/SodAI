"use client";

import {
  createContext,
  forwardRef,
  type ComponentPropsWithoutRef,
  type ForwardedRef,
  type ReactNode,
  type RefObject,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";

import {
  availablePopoverSize,
  insetPopoverBoundary,
  type PopoverInsets,
  type PopoverPlacement,
  resolvePopoverPosition,
} from "@/components/ui/popover-position";

export type { PopoverPlacement } from "@/components/ui/popover-position";

const SAFE_AREA_PROPERTIES = {
  bottom: "--safe-area-inset-bottom",
  left: "--safe-area-inset-left",
  right: "--safe-area-inset-right",
  top: "--safe-area-inset-top",
} as const;

type PopoverContextValue = {
  contentId: string;
  contentRef: RefObject<HTMLDivElement | null>;
  open: boolean;
  placement: PopoverPlacement;
  positionContent: () => void;
  setOpen: (open: boolean) => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
};

type PopoverProps = {
  children: ReactNode;
  collisionPadding?: number;
  gutter?: number;
  matchTriggerWidth?: boolean;
  onOpenChange?: (open: boolean) => void;
  placement?: PopoverPlacement;
};

const PopoverContext = createContext<PopoverContextValue | null>(null);

function subscribeToBrowserReady() {
  return () => undefined;
}

function getBrowserSnapshot() {
  return true;
}

function getServerSnapshot() {
  return false;
}

function usePopoverContext() {
  const context = useContext(PopoverContext);

  if (!context) {
    throw new Error("Popover components must be rendered inside Popover.");
  }

  return context;
}

function assignRef<T>(ref: ForwardedRef<T>, value: T | null) {
  if (typeof ref === "function") {
    ref(value);
  } else if (ref) {
    ref.current = value;
  }
}

function readCssPixels(style: CSSStyleDeclaration, property: string) {
  const value = Number.parseFloat(style.getPropertyValue(property));
  return Number.isFinite(value) ? value : 0;
}

function readSafeArea(): PopoverInsets {
  const style = window.getComputedStyle(document.documentElement);
  return {
    bottom: readCssPixels(style, SAFE_AREA_PROPERTIES.bottom),
    left: readCssPixels(style, SAFE_AREA_PROPERTIES.left),
    right: readCssPixels(style, SAFE_AREA_PROPERTIES.right),
    top: readCssPixels(style, SAFE_AREA_PROPERTIES.top),
  };
}

function visualViewportBoundary() {
  const viewport = window.visualViewport;
  const left = viewport?.offsetLeft ?? 0;
  const top = viewport?.offsetTop ?? 0;
  const width = viewport?.width ?? document.documentElement.clientWidth;
  const height = viewport?.height ?? document.documentElement.clientHeight;
  return {
    bottom: top + height,
    left,
    right: left + width,
    top,
  };
}

export function Popover({
  children,
  collisionPadding = 12,
  gutter = 8,
  matchTriggerWidth = false,
  onOpenChange,
  placement = "bottom-start",
}: PopoverProps) {
  const contentId = `popover-${useId()}`;
  const contentRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const positionFrameRef = useRef<number | null>(null);
  const [open, setOpenState] = useState(false);

  const setOpen = useCallback(
    (nextOpen: boolean) => {
      setOpenState(nextOpen);
      onOpenChange?.(nextOpen);
    },
    [onOpenChange],
  );

  const positionContent = useCallback(() => {
    const content = contentRef.current;
    const trigger = triggerRef.current;

    if (!content || !trigger) {
      return;
    }

    if (!content.matches(":popover-open")) return;

    const triggerRect = trigger.getBoundingClientRect();
    const boundary = insetPopoverBoundary(
      visualViewportBoundary(),
      readSafeArea(),
      collisionPadding,
    );
    const availableSize = availablePopoverSize(boundary);
    const style = content.style;

    for (const property of ["top", "right", "bottom", "left"]) {
      style.removeProperty(property);
    }

    style.maxHeight = `${availableSize.height}px`;
    style.maxWidth = `${availableSize.width}px`;

    if (matchTriggerWidth) {
      style.width = `${Math.min(triggerRect.width, availableSize.width)}px`;
    } else {
      style.removeProperty("width");
    }

    style.left = `${boundary.left}px`;
    style.top = `${boundary.top}px`;
    const position = resolvePopoverPosition({
      boundary,
      content: {
        height: content.offsetHeight,
        width: content.offsetWidth,
      },
      gutter,
      placement,
      trigger: triggerRect,
    });
    content.dataset.placement = position.placement;
    style.left = `${position.left}px`;
    style.top = `${position.top}px`;
    content.dataset.positioned = "true";
  }, [collisionPadding, gutter, matchTriggerWidth, placement]);

  const schedulePosition = useCallback(() => {
    if (positionFrameRef.current !== null) return;
    positionFrameRef.current = window.requestAnimationFrame(() => {
      positionFrameRef.current = null;
      positionContent();
    });
  }, [positionContent]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const content = contentRef.current;
    const trigger = triggerRef.current;
    if (!content || !trigger) {
      return;
    }

    positionContent();
    const resizeObserver = new ResizeObserver(positionContent);
    resizeObserver.observe(trigger);
    resizeObserver.observe(content);
    window.addEventListener("resize", schedulePosition);
    window.addEventListener("scroll", schedulePosition, true);
    window.visualViewport?.addEventListener("resize", schedulePosition);
    window.visualViewport?.addEventListener("scroll", schedulePosition);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", schedulePosition);
      window.removeEventListener("scroll", schedulePosition, true);
      window.visualViewport?.removeEventListener("resize", schedulePosition);
      window.visualViewport?.removeEventListener("scroll", schedulePosition);
      if (positionFrameRef.current !== null) {
        window.cancelAnimationFrame(positionFrameRef.current);
        positionFrameRef.current = null;
      }
    };
  }, [open, positionContent, schedulePosition]);

  const context = useMemo(
    () => ({
      contentId,
      contentRef,
      open,
      placement,
      positionContent,
      setOpen,
      triggerRef,
    }),
    [contentId, open, placement, positionContent, setOpen],
  );

  return (
    <PopoverContext.Provider value={context}>
      {children}
    </PopoverContext.Provider>
  );
}

export const PopoverTrigger = forwardRef<
  HTMLButtonElement,
  ComponentPropsWithoutRef<"button">
>(function PopoverTrigger({ children, ...props }, forwardedRef) {
  const { contentId, open, triggerRef } = usePopoverContext();

  return (
    <button
      {...props}
      ref={(element) => {
        triggerRef.current = element;
        assignRef(forwardedRef, element);
      }}
      type={props.type ?? "button"}
      aria-expanded={open}
      popoverTarget={contentId}
      popoverTargetAction="toggle"
    >
      {children}
    </button>
  );
});

export const PopoverContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<"div">
>(function PopoverContent(
  { children, className = "", onBeforeToggle, onToggle, ...props },
  forwardedRef,
) {
  const {
    contentId,
    contentRef,
    placement,
    positionContent,
    setOpen,
  } = usePopoverContext();
  const browserReady = useSyncExternalStore(
    subscribeToBrowserReady,
    getBrowserSnapshot,
    getServerSnapshot,
  );

  if (!browserReady) return null;

  return createPortal(
    <div
      {...props}
      ref={(element) => {
        contentRef.current = element;
        assignRef(forwardedRef, element);
      }}
      id={contentId}
      popover="auto"
      data-placement={placement}
      className={`ui-popover fixed inset-auto z-50 m-0 max-h-[calc(100dvh-1.5rem)] max-w-[calc(100vw-1.5rem)] overflow-y-auto rounded-2xl border border-[var(--divider)] bg-[var(--surface-translucent)] p-1.5 text-[var(--text)] shadow-[0_16px_48px_var(--popover-shadow)] backdrop-blur-xl outline-none ${className}`}
      onBeforeToggle={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.newState === "open") {
          event.currentTarget.dataset.positioned = "false";
        }
        onBeforeToggle?.(event);
      }}
      onToggle={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.newState === "open") {
          positionContent();
        } else {
          event.currentTarget.dataset.positioned = "false";
        }
        setOpen(event.newState === "open");
        onToggle?.(event);
      }}
    >
      {children}
    </div>,
    document.body,
  );
});

export const PopoverClose = forwardRef<
  HTMLButtonElement,
  ComponentPropsWithoutRef<"button">
>(function PopoverClose({ children, ...props }, forwardedRef) {
  const { contentId } = usePopoverContext();

  return (
    <button
      {...props}
      ref={forwardedRef}
      type={props.type ?? "button"}
      popoverTarget={contentId}
      popoverTargetAction="hide"
    >
      {children}
    </button>
  );
});
