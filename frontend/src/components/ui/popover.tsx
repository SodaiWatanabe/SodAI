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

export type PopoverPlacement =
  | "bottom-end"
  | "bottom-start"
  | "left-end"
  | "left-start"
  | "right-end"
  | "right-start"
  | "top-end"
  | "top-start";

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

    const triggerRect = trigger.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = document.documentElement.clientHeight;
    const style = content.style;

    for (const property of ["top", "right", "bottom", "left"]) {
      style.removeProperty(property);
    }

    if (matchTriggerWidth) {
      style.width = `${triggerRect.width}px`;
    } else {
      style.removeProperty("width");
    }

    if (placement.startsWith("top")) {
      style.bottom = `${viewportHeight - triggerRect.top + gutter}px`;
    } else if (placement.startsWith("bottom")) {
      style.top = `${triggerRect.bottom + gutter}px`;
    } else if (placement.startsWith("right")) {
      style.left = `${triggerRect.right + gutter}px`;
    } else {
      style.right = `${viewportWidth - triggerRect.left + gutter}px`;
    }

    if (placement.endsWith("start")) {
      if (placement.startsWith("top") || placement.startsWith("bottom")) {
        style.left = `${triggerRect.left}px`;
      } else {
        style.top = `${triggerRect.top}px`;
      }
    } else if (
      placement.startsWith("top") ||
      placement.startsWith("bottom")
    ) {
      style.right = `${viewportWidth - triggerRect.right}px`;
    } else {
      style.bottom = `${viewportHeight - triggerRect.bottom}px`;
    }

    if (!content.matches(":popover-open")) {
      return;
    }

    const contentRect = content.getBoundingClientRect();
    const left = Math.min(
      Math.max(contentRect.left, collisionPadding),
      Math.max(
        collisionPadding,
        viewportWidth - collisionPadding - contentRect.width,
      ),
    );
    const top = Math.min(
      Math.max(contentRect.top, collisionPadding),
      Math.max(
        collisionPadding,
        viewportHeight - collisionPadding - contentRect.height,
      ),
    );

    if (left !== contentRect.left || top !== contentRect.top) {
      style.removeProperty("right");
      style.removeProperty("bottom");
      style.left = `${left}px`;
      style.top = `${top}px`;
    }
  }, [collisionPadding, gutter, matchTriggerWidth, placement]);

  useEffect(() => {
    if (!open) {
      return;
    }

    positionContent();
    window.addEventListener("resize", positionContent);
    window.addEventListener("scroll", positionContent, true);

    return () => {
      window.removeEventListener("resize", positionContent);
      window.removeEventListener("scroll", positionContent, true);
    };
  }, [open, positionContent]);

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

  return (
    <div
      {...props}
      ref={(element) => {
        contentRef.current = element;
        assignRef(forwardedRef, element);
      }}
      id={contentId}
      popover="auto"
      data-placement={placement}
      className={`ui-popover fixed inset-auto z-50 m-0 max-h-[calc(100dvh-1.5rem)] max-w-[calc(100vw-1.5rem)] overflow-y-auto rounded-2xl border border-black/[0.08] bg-white/95 p-1.5 text-[#1d1d1f] shadow-[0_16px_48px_rgba(0,0,0,0.16)] backdrop-blur-xl outline-none ${className}`}
      onBeforeToggle={(event) => {
        if (event.newState === "open") {
          positionContent();
        }
        onBeforeToggle?.(event);
      }}
      onToggle={(event) => {
        setOpen(event.newState === "open");
        onToggle?.(event);
      }}
    >
      {children}
    </div>
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
