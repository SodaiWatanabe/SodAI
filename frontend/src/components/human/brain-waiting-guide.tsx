"use client";

import { useEffect, useState } from "react";

const guideIntervalMs = 7_000;

const guides = [
  {
    description:
      "ユーザーのクエリに、大規模言語モデルとして返答しましょう。",
    title: "あなたはデータセンターの中にいます。",
  },
  {
    description: "ユーザーは高速かつ高精度の回答を望んでいます。",
    title: "より速く、より正確に。",
  },
  {
    description:
      "会話の流れとユーザーの意図を踏まえて回答しましょう。",
    title: "文脈を読み解く。",
  },
  {
    description:
      "最も重要な答えを先に示し、必要な理由を簡潔に続けましょう。",
    title: "結論から、明快に。",
  },
] as const;

type BrainWaitingGuideProps = {
  active: boolean;
};

export function BrainWaitingGuide({ active }: BrainWaitingGuideProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!active) return;

    let intervalId: number | undefined;
    const startId = window.setTimeout(() => {
      setActiveIndex(Math.floor(Math.random() * guides.length));
      intervalId = window.setInterval(() => {
        setActiveIndex((currentIndex) =>
          currentIndex === null ? 0 : (currentIndex + 1) % guides.length,
        );
      }, guideIntervalMs);
    }, 0);

    return () => {
      window.clearTimeout(startId);
      if (intervalId !== undefined) window.clearInterval(intervalId);
    };
  }, [active]);

  return (
    <section
      aria-label="応答のヒント"
      className="relative h-[104px] w-full sm:h-[112px]"
    >
      {guides.map((guide, index) => {
        const active = index === activeIndex;

        return (
          <div
            key={guide.title}
            aria-hidden={!active}
            className={`absolute inset-0 flex flex-col items-center transition-[opacity,filter] duration-1000 ease-in-out motion-reduce:transition-none ${
              active
                ? "z-10 opacity-100 blur-0"
                : "pointer-events-none z-0 opacity-0 blur-md"
            }`}
          >
            <h1 className="text-balance text-xl font-medium tracking-[-0.02em] text-[var(--text)] sm:text-2xl">
              {guide.title}
            </h1>
            <p className="mt-2 text-pretty text-sm leading-6 text-[var(--muted)]">
              {guide.description}
            </p>
          </div>
        );
      })}
    </section>
  );
}
