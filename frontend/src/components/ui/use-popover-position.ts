"use client";

import {
  type RefObject,
  useCallback,
  useEffect,
  useRef,
} from "react";

import {
  availablePopoverSize,
  insetPopoverBoundary,
  intersectPopoverBoundaries,
  type PopoverInsets,
  type PopoverPlacement,
  resolvePopoverPosition,
} from "@/components/ui/popover-position";

const SAFE_AREA_PROPERTIES = {
  bottom: "--safe-area-inset-bottom",
  left: "--safe-area-inset-left",
  right: "--safe-area-inset-right",
  top: "--safe-area-inset-top",
} as const;
const NO_INSETS: PopoverInsets = { bottom: 0, left: 0, right: 0, top: 0 };

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

function collisionBoundary(
  trigger: HTMLButtonElement,
  collisionPadding: number,
) {
  const viewport = insetPopoverBoundary(
    visualViewportBoundary(),
    readSafeArea(),
    collisionPadding,
  );
  const dialog = trigger.closest("dialog");

  if (!dialog?.open) return viewport;

  const dialogBoundary = insetPopoverBoundary(
    dialog.getBoundingClientRect(),
    NO_INSETS,
    collisionPadding,
  );
  return intersectPopoverBoundaries(viewport, dialogBoundary);
}

export function usePopoverPosition({
  collisionPadding,
  contentRef,
  gutter,
  matchTriggerWidth,
  open,
  placement,
  portalRoot,
  triggerRef,
}: {
  collisionPadding: number;
  contentRef: RefObject<HTMLDivElement | null>;
  gutter: number;
  matchTriggerWidth: boolean;
  open: boolean;
  placement: PopoverPlacement;
  portalRoot: HTMLElement | null;
  triggerRef: RefObject<HTMLButtonElement | null>;
}) {
  const positionFrameRef = useRef<number | null>(null);

  const positionContent = useCallback(() => {
    const content = contentRef.current;
    const trigger = triggerRef.current;

    if (!open || !content || !trigger) return;

    const triggerRect = trigger.getBoundingClientRect();
    const boundary = collisionBoundary(trigger, collisionPadding);
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
  }, [
    collisionPadding,
    contentRef,
    gutter,
    matchTriggerWidth,
    open,
    placement,
    triggerRef,
  ]);

  const schedulePosition = useCallback(() => {
    if (positionFrameRef.current !== null) return;
    positionFrameRef.current = window.requestAnimationFrame(() => {
      positionFrameRef.current = null;
      positionContent();
    });
  }, [positionContent]);

  useEffect(() => {
    if (!open || !portalRoot) return;

    const content = contentRef.current;
    const trigger = triggerRef.current;
    if (!content || !trigger) return;

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
  }, [
    contentRef,
    open,
    portalRoot,
    positionContent,
    schedulePosition,
    triggerRef,
  ]);
}
