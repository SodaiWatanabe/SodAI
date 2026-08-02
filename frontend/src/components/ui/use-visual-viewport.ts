"use client";

import { useLayoutEffect, useState } from "react";

import {
  readVisualViewportFrame,
  type VisualViewportFrame,
  visualViewportFramesEqual,
} from "@/components/ui/visual-viewport";

export function useVisualViewport() {
  const [frame, setFrame] = useState<VisualViewportFrame | null>(null);

  useLayoutEffect(() => {
    let animationFrameId: number | null = null;

    function update() {
      animationFrameId = null;
      const nextFrame = readVisualViewportFrame();
      setFrame((current) =>
        visualViewportFramesEqual(current, nextFrame) ? current : nextFrame,
      );
    }

    function scheduleUpdate() {
      if (animationFrameId !== null) return;
      animationFrameId = window.requestAnimationFrame(update);
    }

    update();
    window.addEventListener("resize", scheduleUpdate);
    window.visualViewport?.addEventListener("resize", scheduleUpdate);
    window.visualViewport?.addEventListener("scroll", scheduleUpdate);

    return () => {
      window.removeEventListener("resize", scheduleUpdate);
      window.visualViewport?.removeEventListener("resize", scheduleUpdate);
      window.visualViewport?.removeEventListener("scroll", scheduleUpdate);
      if (animationFrameId !== null) {
        window.cancelAnimationFrame(animationFrameId);
      }
    };
  }, []);

  return frame;
}
