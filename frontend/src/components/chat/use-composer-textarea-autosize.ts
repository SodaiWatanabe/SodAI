"use client";

import {
  type RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

const COMPOSER_MAX_HEIGHT = 160;

export function useComposerTextareaAutosize(
  ref: RefObject<HTMLTextAreaElement | null>,
  value: string,
) {
  const [multiline, setMultiline] = useState(false);
  const animationFrameRef = useRef<number | null>(null);

  const resize = useCallback(() => {
    const textarea = ref.current;
    if (!textarea) return;

    const previousHeight = textarea.getBoundingClientRect().height;
    const transition = textarea.style.transition;
    textarea.style.transition = "none";
    const paddingRight = textarea.style.paddingRight;
    textarea.style.paddingRight = "56px";
    textarea.style.height = "auto";
    const styles = window.getComputedStyle(textarea);
    const singleLineHeight =
      Number.parseFloat(styles.lineHeight) +
      Number.parseFloat(styles.paddingTop) +
      Number.parseFloat(styles.paddingBottom);
    const compactContentHeight = textarea.scrollHeight;

    textarea.style.paddingRight = paddingRight;
    textarea.style.height = "auto";
    const contentHeight = textarea.scrollHeight;
    const height = Math.min(contentHeight, COMPOSER_MAX_HEIGHT);
    textarea.style.overflowY =
      contentHeight > COMPOSER_MAX_HEIGHT ? "auto" : "hidden";
    setMultiline(compactContentHeight > singleLineHeight + 1);

    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    textarea.style.height = `${previousHeight}px`;
    void textarea.offsetHeight;
    textarea.style.transition = transition;

    if (Math.abs(previousHeight - height) < 1) {
      textarea.style.height = `${height}px`;
      animationFrameRef.current = null;
      return;
    }

    animationFrameRef.current = requestAnimationFrame(() => {
      textarea.style.height = `${height}px`;
      animationFrameRef.current = null;
    });
  }, [ref]);

  useLayoutEffect(resize, [multiline, resize, value]);

  useEffect(() => {
    const textarea = ref.current;
    if (!textarea) return;

    let observer: ResizeObserver | undefined;
    if (typeof ResizeObserver !== "undefined") {
      let width = textarea.clientWidth;
      observer = new ResizeObserver(() => {
        const nextWidth = textarea.clientWidth;
        if (Math.abs(nextWidth - width) < 1) return;
        width = nextWidth;
        resize();
      });
      observer.observe(textarea);
    }

    return () => {
      observer?.disconnect();
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [ref, resize]);

  return multiline;
}
