"use client";

import {
  type RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
} from "react";

export function useTextareaAutosize(
  ref: RefObject<HTMLTextAreaElement | null>,
  value: string,
  mountKey?: unknown,
) {
  const resize = useCallback(() => {
    const textarea = ref.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    const styles = window.getComputedStyle(textarea);
    const borderHeight =
      Number.parseFloat(styles.borderTopWidth) +
      Number.parseFloat(styles.borderBottomWidth);
    const contentHeight = textarea.scrollHeight + borderHeight;
    textarea.style.height = `${contentHeight}px`;
    const renderedHeight = textarea.getBoundingClientRect().height;
    textarea.style.overflowY =
      contentHeight > renderedHeight + 1 ? "auto" : "hidden";
  }, [ref]);

  useLayoutEffect(resize, [mountKey, resize, value]);

  useEffect(() => {
    const textarea = ref.current;
    if (!textarea || typeof ResizeObserver === "undefined") return;

    let width = textarea.clientWidth;
    const viewport = window.visualViewport;
    let animationFrameId: number | null = null;
    const scheduleResize = () => {
      if (animationFrameId !== null) return;
      animationFrameId = window.requestAnimationFrame(() => {
        animationFrameId = null;
        resize();
      });
    };
    const observer = new ResizeObserver(() => {
      const nextWidth = textarea.clientWidth;
      if (Math.abs(nextWidth - width) < 1) return;
      width = nextWidth;
      scheduleResize();
    });
    observer.observe(textarea);
    window.addEventListener("resize", scheduleResize);
    viewport?.addEventListener("resize", scheduleResize);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", scheduleResize);
      viewport?.removeEventListener("resize", scheduleResize);
      if (animationFrameId !== null) {
        window.cancelAnimationFrame(animationFrameId);
      }
    };
  }, [mountKey, ref, resize]);
}
