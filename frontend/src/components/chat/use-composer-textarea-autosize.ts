"use client";

import {
  type RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

const COMPOSER_MAX_HEIGHT = 208;

type ComposerScrollEdges = {
  bottom: boolean;
  top: boolean;
};

export function useComposerTextareaAutosize(
  ref: RefObject<HTMLTextAreaElement | null>,
  value: string,
) {
  const [multiline, setMultiline] = useState(false);
  const [scrollEdges, setScrollEdges] = useState<ComposerScrollEdges>({
    bottom: false,
    top: false,
  });
  const animationFrameRef = useRef<number | null>(null);

  const updateScrollEdges = useCallback(() => {
    const textarea = ref.current;
    if (!textarea) return;

    const overflowing = textarea.scrollHeight > COMPOSER_MAX_HEIGHT + 1;
    const nextEdges = {
      bottom:
        overflowing &&
        textarea.scrollHeight - textarea.scrollTop - textarea.clientHeight > 1,
      top: overflowing && textarea.scrollTop > 1,
    };

    setScrollEdges((current) =>
      current.bottom === nextEdges.bottom && current.top === nextEdges.top
        ? current
        : nextEdges,
    );
  }, [ref]);

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
      updateScrollEdges();
      return;
    }

    animationFrameRef.current = requestAnimationFrame(() => {
      textarea.style.height = `${height}px`;
      animationFrameRef.current = null;
      updateScrollEdges();
    });
  }, [ref, updateScrollEdges]);

  useLayoutEffect(resize, [multiline, resize, value]);

  useEffect(() => {
    const textarea = ref.current;
    if (!textarea) return;

    let observer: ResizeObserver | undefined;
    if (typeof ResizeObserver !== "undefined") {
      let width = textarea.clientWidth;
      observer = new ResizeObserver(() => {
        updateScrollEdges();
        const nextWidth = textarea.clientWidth;
        if (Math.abs(nextWidth - width) < 1) return;
        width = nextWidth;
        resize();
      });
      observer.observe(textarea);
    }
    textarea.addEventListener("scroll", updateScrollEdges, { passive: true });

    return () => {
      observer?.disconnect();
      textarea.removeEventListener("scroll", updateScrollEdges);
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [ref, resize, updateScrollEdges]);

  return { multiline, scrollEdges };
}
