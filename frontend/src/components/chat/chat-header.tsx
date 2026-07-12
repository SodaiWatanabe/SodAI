"use client";

import { ModelSelector } from "@/components/chat/model-selector";
import type { AvailableModel } from "@/lib/chat/types";

type ChatHeaderProps = {
  disabled?: boolean;
  model?: AvailableModel["id"];
  models: AvailableModel[];
  onModelChange: (model: AvailableModel["id"]) => void;
  showPseudoBadge?: boolean;
};

export function ChatHeader({
  disabled = false,
  model,
  models,
  onModelChange,
  showPseudoBadge = false,
}: ChatHeaderProps) {
  return (
    <header className="sticky top-0 z-10 h-12 shrink-0 border-b border-[var(--separator)] bg-[var(--canvas)]">
      <div className="mx-auto flex h-full w-full max-w-[760px] items-center px-12 sm:px-8 lg:mx-0 lg:max-w-none lg:px-1.5">
        <ModelSelector
          disabled={disabled}
          model={model}
          models={models}
          onChange={onModelChange}
          showPseudoBadge={showPseudoBadge}
        />
      </div>
    </header>
  );
}
