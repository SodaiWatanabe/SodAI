"use client";

import {
  type UIEventHandler,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

const STICK_TO_BOTTOM_THRESHOLD = 120;

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
  const pinnedRef = useRef(true);
  const animationFrameRef = useRef<number | null>(null);
  const animatedScrollRef = useRef(false);
  const [detachedKey, setDetachedKey] = useState<string | null>(null);
  const showScrollToBottom = detachedKey === resetKey;

  const followBottom = useCallback(() => {
    if (!pinnedRef.current || animationFrameRef.current !== null) return;

    animationFrameRef.current = requestAnimationFrame(() => {
      animationFrameRef.current = null;
      const container = containerRef.current;
      if (!container || !pinnedRef.current) return;
      container.scrollTop = container.scrollHeight;
    });
  }, []);

  const pinToBottom = useCallback(() => {
    pinnedRef.current = true;
    animatedScrollRef.current = false;
    setDetachedKey(null);
    followBottom();
  }, [followBottom]);

  const scrollToBottom = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    pinnedRef.current = true;
    animatedScrollRef.current = true;
    setDetachedKey(null);
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, []);

  const handleScroll = useCallback<UIEventHandler<HTMLDivElement>>((event) => {
    const nearBottom = isNearBottom(event.currentTarget);
    if (animatedScrollRef.current) {
      if (nearBottom) animatedScrollRef.current = false;
      return;
    }
    pinnedRef.current = nearBottom;
    setDetachedKey((current) => {
      const next = nearBottom ? null : resetKey;
      return current === next ? current : next;
    });
  }, [resetKey]);

  const cancelAnimatedScroll = useCallback(() => {
    animatedScrollRef.current = false;
  }, []);

  useLayoutEffect(() => {
    pinnedRef.current = true;
    animatedScrollRef.current = false;

    const container = containerRef.current;
    if (!container || !ready) return;
    container.scrollTop = container.scrollHeight;
  }, [ready, resetKey]);

  useEffect(() => {
    if (!ready || typeof ResizeObserver === "undefined") return;

    const observedElements = [
      containerRef.current,
      contentRef.current,
      footerRef.current,
    ].filter((element): element is HTMLDivElement => element !== null);
    const observer = new ResizeObserver(followBottom);
    for (const element of observedElements) observer.observe(element);

    return () => observer.disconnect();
  }, [followBottom, ready, resetKey]);

  useEffect(
    () => () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    },
    [],
  );

  return {
    cancelAnimatedScroll,
    containerRef,
    contentRef,
    footerRef,
    handleScroll,
    pinToBottom,
    scrollToBottom,
    showScrollToBottom,
  };
}
