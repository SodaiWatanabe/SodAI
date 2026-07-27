"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";

import {
  createBrainStarfield,
  resolveBrainStarAlpha,
  type BrainStar,
} from "@/components/human/brain-starfield-model";

const STARFIELD_SEED = 0x57a2f13d;
const MAX_DEVICE_PIXEL_RATIO = 1.5;
const FRAME_INTERVAL = 1000 / 30;

function createGlowSprite() {
  const sprite = document.createElement("canvas");
  const size = 48;
  sprite.width = size;
  sprite.height = size;
  const context = sprite.getContext("2d");
  if (!context) return sprite;

  const center = size / 2;
  const gradient = context.createRadialGradient(
    center,
    center,
    0,
    center,
    center,
    center,
  );
  gradient.addColorStop(0, "rgb(255 255 255 / 82%)");
  gradient.addColorStop(0.16, "rgb(255 255 255 / 30%)");
  gradient.addColorStop(0.48, "rgb(255 255 255 / 8%)");
  gradient.addColorStop(1, "transparent");
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  return sprite;
}

function wrap(value: number, extent: number) {
  return ((value % extent) + extent) % extent;
}

function drawStarfield(
  context: CanvasRenderingContext2D,
  stars: BrainStar[],
  glowSprite: HTMLCanvasElement,
  width: number,
  height: number,
  elapsedSeconds: number,
) {
  context.clearRect(0, 0, width, height);

  for (const star of stars) {
    const x = wrap(star.x * width + elapsedSeconds * star.driftX, width);
    const y = wrap(star.y * height + elapsedSeconds * star.driftY, height);
    const alpha = resolveBrainStarAlpha(star, elapsedSeconds);

    if (star.glow) {
      const glowSize = star.radius * 12;
      context.globalAlpha = alpha * 0.42;
      context.drawImage(
        glowSprite,
        x - glowSize / 2,
        y - glowSize / 2,
        glowSize,
        glowSize,
      );
    }

    context.globalAlpha = alpha;
    context.fillStyle = "#ffffff";
    context.beginPath();
    context.arc(x, y, star.radius, 0, Math.PI * 2);
    context.fill();
  }

  context.globalAlpha = 1;
}

export function BrainSpaceBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [nebulaVisible, setNebulaVisible] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = canvas?.parentElement;
    const context = canvas?.getContext("2d");
    if (!canvas || !host || !context) return;

    const colorMedia = window.matchMedia("(prefers-color-scheme: dark)");
    const motionMedia = window.matchMedia("(prefers-reduced-motion: reduce)");
    const glowSprite = createGlowSprite();
    let stars: BrainStar[] = [];
    let width = 1;
    let height = 1;
    let elapsedSeconds = 0;
    let lastFrame = performance.now();
    let frameId: number | undefined;
    let resizeFrameId: number | undefined;
    let darkMode = false;

    function resolveDarkMode() {
      const theme = document.documentElement.dataset.theme;
      return (
        theme === "dark" ||
        ((theme === "system" || !theme) && colorMedia.matches)
      );
    }

    function draw() {
      if (!darkMode) return;
      drawStarfield(
        context!,
        stars,
        glowSprite,
        width,
        height,
        elapsedSeconds,
      );
    }

    function stopAnimation() {
      if (frameId !== undefined) {
        window.cancelAnimationFrame(frameId);
      }
      frameId = undefined;
    }

    function animate(now: number) {
      const frameElapsed = now - lastFrame;
      if (frameElapsed < FRAME_INTERVAL) {
        frameId = window.requestAnimationFrame(animate);
        return;
      }

      elapsedSeconds += Math.min(frameElapsed / 1000, 0.1);
      lastFrame = now - (frameElapsed % FRAME_INTERVAL);
      draw();
      frameId = window.requestAnimationFrame(animate);
    }

    function startAnimation() {
      stopAnimation();
      if (!darkMode) return;
      lastFrame = performance.now();
      if (motionMedia.matches || document.hidden) {
        draw();
        return;
      }
      frameId = window.requestAnimationFrame(animate);
    }

    function resize() {
      const bounds = host!.getBoundingClientRect();
      width = Math.max(1, Math.round(bounds.width));
      height = Math.max(1, Math.round(bounds.height));
      const pixelRatio = Math.min(
        window.devicePixelRatio || 1,
        MAX_DEVICE_PIXEL_RATIO,
      );
      canvas!.width = Math.round(width * pixelRatio);
      canvas!.height = Math.round(height * pixelRatio);
      context!.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      stars = createBrainStarfield(width, height, STARFIELD_SEED);
      draw();
    }

    function scheduleResize() {
      if (resizeFrameId !== undefined) return;
      resizeFrameId = window.requestAnimationFrame(() => {
        resizeFrameId = undefined;
        resize();
      });
    }

    function applyTheme() {
      darkMode = resolveDarkMode();
      setNebulaVisible(darkMode);
      canvas!.dataset.visible = darkMode ? "true" : "false";
      if (!darkMode) {
        stopAnimation();
        context!.clearRect(0, 0, width, height);
        return;
      }
      draw();
      startAnimation();
    }

    function handleVisibilityChange() {
      if (document.hidden) {
        stopAnimation();
      } else {
        startAnimation();
      }
    }

    const resizeObserver = new ResizeObserver(scheduleResize);
    const themeObserver = new MutationObserver(applyTheme);
    resizeObserver.observe(host);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    colorMedia.addEventListener("change", applyTheme);
    motionMedia.addEventListener("change", startAnimation);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    resize();
    applyTheme();

    return () => {
      stopAnimation();
      if (resizeFrameId !== undefined) {
        window.cancelAnimationFrame(resizeFrameId);
      }
      resizeObserver.disconnect();
      themeObserver.disconnect();
      colorMedia.removeEventListener("change", applyTheme);
      motionMedia.removeEventListener("change", startAnimation);
      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange,
      );
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
    >
      {nebulaVisible ? (
        <Image
          fill
          priority
          alt=""
          draggable={false}
          quality={75}
          sizes="(max-width: 1024px) 100vw, calc(100vw - 16rem)"
          src="/images/brain-nebula.png"
          className="object-cover object-center opacity-65"
        />
      ) : null}
      <canvas
        ref={canvasRef}
        data-visible="false"
        className="absolute inset-0 size-full opacity-0 transition-opacity duration-700 data-[visible=true]:opacity-100 motion-reduce:transition-none"
      />
    </div>
  );
}
