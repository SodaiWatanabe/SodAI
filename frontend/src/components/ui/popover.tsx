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
} from "react";
import { createPortal } from "react-dom";

import type { PopoverPlacement } from "@/components/ui/popover-position";
import { usePopoverPosition } from "@/components/ui/use-popover-position";

export type { PopoverPlacement } from "@/components/ui/popover-position";

type PopoverContextValue = {
  contentId: string;
  contentRef: RefObject<HTMLDivElement | null>;
  open: boolean;
  placement: PopoverPlacement;
  popoverTree: string[];
  portalRoot: HTMLElement | null;
  setOpen: (open: boolean) => void;
  setTriggerElement: (element: HTMLButtonElement | null) => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
};

type PopoverProps = {
  children: ReactNode;
  collisionPadding?: number;
  defaultOpen?: boolean;
  gutter?: number;
  matchTriggerWidth?: boolean;
  onOpenChange?: (open: boolean) => void;
  open?: boolean;
  placement?: PopoverPlacement;
};

const PopoverContext = createContext<PopoverContextValue | null>(null);

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

function eventElement(target: EventTarget | null) {
  if (target instanceof Element) return target;
  if (target instanceof Node) return target.parentElement;
  return null;
}

function popoverTreeFor(element: Element | null) {
  return element
    ?.closest<HTMLElement>("[data-popover-tree]")
    ?.dataset.popoverTree?.split(" ") ?? [];
}

function isInsidePopoverTree(target: EventTarget | null, contentId: string) {
  return popoverTreeFor(eventElement(target)).includes(contentId);
}

function hasOpenDescendantPopover(contentId: string) {
  return Array.from(
    document.querySelectorAll<HTMLElement>("[data-popover-tree]"),
  ).some((element) => {
    const tree = element.dataset.popoverTree?.split(" ") ?? [];
    return tree.includes(contentId) && tree.at(-1) !== contentId;
  });
}

export function Popover({
  children,
  collisionPadding = 12,
  defaultOpen = false,
  gutter = 8,
  matchTriggerWidth = false,
  onOpenChange,
  open: controlledOpen,
  placement = "bottom-start",
}: PopoverProps) {
  const parentPopover = useContext(PopoverContext);
  const contentId = `popover-${useId()}`;
  const contentRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const [portalRoot, setPortalRoot] = useState<HTMLElement | null>(null);
  const open = controlledOpen ?? uncontrolledOpen;
  const popoverTree = useMemo(
    () => [...(parentPopover?.popoverTree ?? []), contentId],
    [contentId, parentPopover?.popoverTree],
  );

  const setOpen = useCallback(
    (nextOpen: boolean) => {
      if (nextOpen === open) return;
      if (controlledOpen === undefined) setUncontrolledOpen(nextOpen);
      onOpenChange?.(nextOpen);
    },
    [controlledOpen, onOpenChange, open],
  );

  const setTriggerElement = useCallback(
    (element: HTMLButtonElement | null) => {
      triggerRef.current = element;
      if (!element) return;

      const nextPortalRoot = element.closest("dialog") ?? document.body;
      setPortalRoot((current) =>
        current === nextPortalRoot ? current : nextPortalRoot,
      );
    },
    [],
  );

  usePopoverPosition({
    collisionPadding,
    contentRef,
    gutter,
    matchTriggerWidth,
    open,
    placement,
    portalRoot,
    triggerRef,
  });

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      const trigger = triggerRef.current;
      const target = event.target;
      if (
        (target instanceof Node && trigger?.contains(target)) ||
        isInsidePopoverTree(target, contentId)
      ) {
        return;
      }
      setOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || hasOpenDescendantPopover(contentId)) {
        return;
      }
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus({ preventScroll: true });
    }

    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [contentId, open, setOpen]);

  const context = useMemo(
    () => ({
      contentId,
      contentRef,
      open,
      placement,
      popoverTree,
      portalRoot,
      setOpen,
      setTriggerElement,
      triggerRef,
    }),
    [
      contentId,
      open,
      placement,
      popoverTree,
      portalRoot,
      setOpen,
      setTriggerElement,
    ],
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
>(function PopoverTrigger(
  { children, onClick, ...props },
  forwardedRef,
) {
  const { contentId, open, setOpen, setTriggerElement } = usePopoverContext();
  const setTriggerRef = useCallback(
    (element: HTMLButtonElement | null) => {
      setTriggerElement(element);
      assignRef(forwardedRef, element);
    },
    [forwardedRef, setTriggerElement],
  );

  return (
    <button
      {...props}
      ref={setTriggerRef}
      type={props.type ?? "button"}
      aria-controls={contentId}
      aria-expanded={open}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) setOpen(!open);
      }}
    >
      {children}
    </button>
  );
});

export const PopoverContent = forwardRef<
  HTMLDivElement,
  ComponentPropsWithoutRef<"div">
>(function PopoverContent(
  { children, className = "", ...props },
  forwardedRef,
) {
  const {
    contentId,
    contentRef,
    open,
    placement,
    popoverTree,
    portalRoot,
  } = usePopoverContext();
  const setContentRef = useCallback(
    (element: HTMLDivElement | null) => {
      contentRef.current = element;
      if (element) element.dataset.positioned = "false";
      assignRef(forwardedRef, element);
    },
    [contentRef, forwardedRef],
  );

  if (!open || !portalRoot) return null;

  return createPortal(
    <div
      {...props}
      ref={setContentRef}
      id={contentId}
      data-placement={placement}
      data-popover-tree={popoverTree.join(" ")}
      data-state="open"
      className={`ui-popover fixed inset-auto z-50 m-0 max-h-[calc(100dvh-1.5rem)] max-w-[calc(100vw-1.5rem)] overflow-y-auto rounded-2xl border border-[var(--divider)] bg-[var(--surface-translucent)] p-1.5 text-[var(--text)] shadow-[0_16px_48px_var(--popover-shadow)] backdrop-blur-xl outline-none ${className}`}
    >
      {children}
    </div>,
    portalRoot,
  );
});

export const PopoverClose = forwardRef<
  HTMLButtonElement,
  ComponentPropsWithoutRef<"button">
>(function PopoverClose(
  { children, onClick, ...props },
  forwardedRef,
) {
  const { setOpen } = usePopoverContext();

  return (
    <button
      {...props}
      ref={forwardedRef}
      type={props.type ?? "button"}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) setOpen(false);
      }}
    >
      {children}
    </button>
  );
});
