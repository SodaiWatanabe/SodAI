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
    textarea.style.height = `${textarea.scrollHeight + borderHeight}px`;
  }, [ref]);

  useLayoutEffect(resize, [mountKey, resize, value]);

  useEffect(() => {
    const textarea = ref.current;
    if (!textarea || typeof ResizeObserver === "undefined") return;

    let width = textarea.clientWidth;
    const observer = new ResizeObserver(() => {
      const nextWidth = textarea.clientWidth;
      if (Math.abs(nextWidth - width) < 1) return;
      width = nextWidth;
      resize();
    });
    observer.observe(textarea);
    return () => observer.disconnect();
  }, [mountKey, ref, resize]);
}
