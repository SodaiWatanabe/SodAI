"use client";

import {
  type KeyboardEventHandler,
  type PointerEventHandler,
  type UIEventHandler,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import {
  calculateTurnScrollLayout,
  type ThreadScrollEvent,
  type ThreadScrollMode,
  transitionThreadScrollMode,
} from "@/components/chat/thread-scroll-state";

const STICK_TO_BOTTOM_THRESHOLD = 120;
const SCROLL_POSITION_TOLERANCE = 1;
const OVERLAY_SCROLLBAR_HIT_WIDTH = 12;
const SCROLL_KEYS = new Set([
  "ArrowDown",
  "ArrowUp",
  "End",
  "Home",
  "PageDown",
  "PageUp",
  " ",
]);

type UseThreadAutoScrollOptions = {
  ready: boolean;
  resetKey: string;
};

function isNearBottom(element: HTMLDivElement) {
  const distance =
    element.scrollHeight - element.scrollTop - element.clientHeight;
  return distance <= STICK_TO_BOTTOM_THRESHOLD;
}

export function useThreadAutoScroll({
  ready,
  resetKey,
}: UseThreadAutoScrollOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const footerRef = useRef<HTMLDivElement>(null);
  const turnAnchorRef = useRef<HTMLElement>(null);
  const turnSpacerRef = useRef<HTMLDivElement>(null);
  const scrollModeRef = useRef<ThreadScrollMode>("bottom");
  const expectedTurnScrollTopRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const animatedScrollRef = useRef(false);
  const [scrollState, setScrollState] = useState<{
    mode: ThreadScrollMode;
    resetKey: string;
  }>({ mode: "bottom", resetKey });
  if (scrollState.resetKey !== resetKey) {
    setScrollState({ mode: "bottom", resetKey });
  }
  const showScrollToBottom =
    scrollState.resetKey === resetKey && scrollState.mode === "detached";

  const applyScrollEvent = useCallback(
    (event: ThreadScrollEvent) => {
      const nextMode = transitionThreadScrollMode(
        scrollModeRef.current,
        event,
      );
      scrollModeRef.current = nextMode;
      setScrollState((current) => {
        if (current.resetKey === resetKey && current.mode === nextMode) {
          return current;
        }
        return { mode: nextMode, resetKey };
      });
    },
    [resetKey],
  );

  const clearTurnLayout = useCallback(() => {
    turnSpacerRef.current?.style.removeProperty("height");
    expectedTurnScrollTopRef.current = null;
  }, []);

  const applyTurnLayout = useCallback((alignToTurn: boolean) => {
    const container = containerRef.current;
    const entry = turnAnchorRef.current;
    const spacer = turnSpacerRef.current;
    if (!container || !entry || !spacer) return false;

    const containerRect = container.getBoundingClientRect();
    const entryRect = entry.getBoundingClientRect();
    const spacerHeight = spacer.getBoundingClientRect().height;
    const parsedScrollMarginTop = Number.parseFloat(
      window.getComputedStyle(entry).scrollMarginTop,
    );
    const layout = calculateTurnScrollLayout({
      containerHeight: container.clientHeight,
      containerScrollTop: container.scrollTop,
      containerTop: containerRect.top,
      entryTop: entryRect.top,
      scrollHeight: container.scrollHeight,
      scrollMarginTop: Number.isFinite(parsedScrollMarginTop)
        ? parsedScrollMarginTop
        : 0,
      spacerHeight,
    });
    const nextSpacerHeight = Math.ceil(layout.spacerHeight);
    if (Math.abs(spacerHeight - nextSpacerHeight) > SCROLL_POSITION_TOLERANCE) {
      spacer.style.height = `${nextSpacerHeight}px`;
    }
    if (alignToTurn) {
      container.scrollTop = layout.scrollTop;
      expectedTurnScrollTopRef.current = container.scrollTop;
    }
    return true;
  }, []);

  const syncScrollPosition = useCallback(() => {
    if (animationFrameRef.current !== null) return;

    animationFrameRef.current = requestAnimationFrame(() => {
      animationFrameRef.current = null;
      const container = containerRef.current;
      if (!container) return;
      if (scrollModeRef.current === "bottom") {
        container.scrollTop = container.scrollHeight;
      } else if (scrollModeRef.current === "turn") {
        applyTurnLayout(true);
      } else if (
        (turnSpacerRef.current?.getBoundingClientRect().height ?? 0) >
        SCROLL_POSITION_TOLERANCE
      ) {
        applyTurnLayout(false);
      }
    });
  }, [applyTurnLayout]);

  const pinToBottom = useCallback(() => {
    animatedScrollRef.current = false;
    clearTurnLayout();
    applyScrollEvent("pin-bottom");
    syncScrollPosition();
  }, [applyScrollEvent, clearTurnLayout, syncScrollPosition]);

  const anchorTurn = useCallback(() => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    animatedScrollRef.current = false;
    applyScrollEvent("anchor-turn");
    return applyTurnLayout(true);
  }, [applyScrollEvent, applyTurnLayout]);

  const scrollToBottom = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    clearTurnLayout();
    applyScrollEvent("pin-bottom");
    animatedScrollRef.current = true;
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [applyScrollEvent, clearTurnLayout]);

  const handleScroll = useCallback<UIEventHandler<HTMLDivElement>>(
    (event) => {
      if (scrollModeRef.current === "turn") {
        const expectedScrollTop = expectedTurnScrollTopRef.current;
        if (
          expectedScrollTop === null ||
          Math.abs(event.currentTarget.scrollTop - expectedScrollTop) <=
            SCROLL_POSITION_TOLERANCE
        ) {
          return;
        }
        syncScrollPosition();
        return;
      }

      if (
        scrollModeRef.current === "detached" &&
        (turnSpacerRef.current?.getBoundingClientRect().height ?? 0) >
          SCROLL_POSITION_TOLERANCE
      ) {
        applyScrollEvent("detach");
        return;
      }
      const nearBottom = isNearBottom(event.currentTarget);
      if (animatedScrollRef.current) {
        if (nearBottom) animatedScrollRef.current = false;
        return;
      }
      applyScrollEvent(nearBottom ? "pin-bottom" : "detach");
    },
    [applyScrollEvent, syncScrollPosition],
  );

  const detachFromTurn = useCallback(() => {
    animatedScrollRef.current = false;
    if (scrollModeRef.current === "turn") {
      expectedTurnScrollTopRef.current = null;
      applyScrollEvent("detach");
    }
  }, [applyScrollEvent]);

  const handleScrollKeyDown = useCallback<KeyboardEventHandler<HTMLDivElement>>(
    (event) => {
      if (!SCROLL_KEYS.has(event.key)) return;
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        target.closest(
          "a, button, input, select, textarea, [contenteditable='true']",
        )
      ) {
        return;
      }
      detachFromTurn();
    },
    [detachFromTurn],
  );

  const handleScrollPointerDown = useCallback<
    PointerEventHandler<HTMLDivElement>
  >(
    (event) => {
      const container = event.currentTarget;
      const rect = container.getBoundingClientRect();
      const scrollbarHitWidth = Math.max(
        container.offsetWidth - container.clientWidth,
        OVERLAY_SCROLLBAR_HIT_WIDTH,
      );
      if (event.clientX >= rect.right - scrollbarHitWidth) {
        detachFromTurn();
      }
    },
    [detachFromTurn],
  );

  const scrollToEntry = useCallback(
    (entry: HTMLElement, scrollTarget: HTMLElement = entry) => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      clearTurnLayout();
      applyScrollEvent("detach");
      animatedScrollRef.current = false;
      const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      scrollTarget.scrollIntoView({
        behavior: reducedMotion ? "auto" : "smooth",
        block: "center",
      });
      entry.focus({ preventScroll: true });
    },
    [applyScrollEvent, clearTurnLayout],
  );

  useLayoutEffect(() => {
    scrollModeRef.current = "bottom";
    expectedTurnScrollTopRef.current = null;
    animatedScrollRef.current = false;
    clearTurnLayout();

    const container = containerRef.current;
    if (!container || !ready) return;
    container.scrollTop = container.scrollHeight;
  }, [clearTurnLayout, ready, resetKey]);

  useEffect(() => {
    if (!ready || typeof ResizeObserver === "undefined") return;

    const observedElements = [
      containerRef.current,
      contentRef.current,
      footerRef.current,
    ].filter((element): element is HTMLDivElement => element !== null);
    const observer = new ResizeObserver(syncScrollPosition);
    for (const element of observedElements) observer.observe(element);

    return () => observer.disconnect();
  }, [ready, resetKey, syncScrollPosition]);

  useEffect(
    () => () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    },
    [],
  );

  return {
    anchorTurn,
    containerRef,
    contentRef,
    footerRef,
    handleScrollKeyDown,
    handleScrollPointerDown,
    handleScroll,
    handleUserScrollIntent: detachFromTurn,
    pinToBottom,
    scrollToEntry,
    scrollToBottom,
    showScrollToBottom,
    turnAnchorRef,
    turnSpacerRef,
  };
}
