"use client";

import { useState } from "react";

import { BrainLobbyBackground } from "@/components/human/brain-lobby-background";
import { BrainAnswerConditionSelectors } from "@/components/human/brain-answer-condition-selectors";
import { BrainWaitingGuide } from "@/components/human/brain-waiting-guide";
import type { AvailableAnswerer } from "@/lib/chat/types";
import type { HumanAnswerConditions } from "@/lib/human/types";

type BrainLobbyMode = "signed-out" | "idle" | "waiting";

type BrainLobbyProps = {
  answerers?: AvailableAnswerer[];
  availableAnswererIds?: string[];
  busy?: boolean;
  conditions?: HumanAnswerConditions;
  error?: string;
  mode: BrainLobbyMode;
  notice?: string;
  rankName?: string;
  onAction: (
    conditions?: HumanAnswerConditions,
  ) => boolean | Promise<boolean> | void;
};

const actionLabel = {
  "signed-out": "ログイン",
  idle: "思考をはじめる",
  waiting: "待機をやめる",
} satisfies Record<BrainLobbyMode, string>;

type LobbyActionButtonProps = {
  active?: boolean;
  busy: boolean;
  mode: BrainLobbyMode;
  onAction: () => void;
};

function LobbyActionButton({
  active = true,
  busy,
  mode,
  onAction,
}: LobbyActionButtonProps) {
  const waiting = mode === "waiting";
  const idle = mode === "idle";

  return (
    <button
      type="button"
      aria-busy={active && busy}
      disabled={!active || busy}
      className={`h-10 text-sm font-medium transition-colors disabled:cursor-default disabled:opacity-50 ${
        idle ? "mt-3 rounded-full px-5" : "rounded-full px-5"
      } ${
        waiting
          ? "mt-3 bg-[var(--button-background)] text-[var(--text)] backdrop-blur-md hover:bg-[var(--button-hover)]"
          : "bg-[var(--primary)] text-[var(--on-primary)] hover:bg-[var(--primary-hover)]"
      } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]`}
      onClick={onAction}
    >
      {actionLabel[mode]}
    </button>
  );
}

export function BrainLobby({
  answerers = [],
  availableAnswererIds = [],
  busy = false,
  conditions,
  error,
  mode,
  notice,
  onAction,
  rankName,
}: BrainLobbyProps) {
  const waiting = mode === "waiting";
  const [draftConditions, setDraftConditions] = useState(conditions);
  const [starting, setStarting] = useState(false);

  function runAction() {
    if (mode !== "idle") {
      onAction();
      return;
    }

    setStarting(true);
    void Promise.resolve(onAction(draftConditions)).then(
      () => setStarting(false),
      () => setStarting(false),
    );
  }

  return (
    <section className="relative isolate grid flex-1 place-items-center overflow-hidden px-6">
      <BrainLobbyBackground />

      <div className="relative z-10 w-full max-w-md text-center">
        {mode === "signed-out" ? (
          <LobbyActionButton
            busy={busy}
            mode="signed-out"
            onAction={runAction}
          />
        ) : (
          <div className="relative mx-auto h-[250px] w-full max-w-sm">
            <div
              aria-hidden={waiting || starting}
              inert={waiting || starting}
              className={`absolute inset-0 grid place-items-center transition-[opacity,filter,transform] duration-500 ease-out motion-reduce:transition-none ${
                waiting || starting
                  ? "pointer-events-none scale-[0.98] opacity-0 blur-md"
                  : "scale-100 opacity-100 blur-0"
              }`}
            >
              <div className="w-full rounded-2xl bg-[var(--button-background)] p-3 shadow-[0_12px_36px_var(--popover-shadow)] backdrop-blur-xl">
                {draftConditions && answerers.length > 0 ? (
                  <BrainAnswerConditionSelectors
                    answerers={answerers}
                    availableAnswererIds={availableAnswererIds}
                    disabled={busy}
                    rankName={rankName ?? ""}
                    value={draftConditions}
                    onChange={setDraftConditions}
                  />
                ) : null}
                <LobbyActionButton
                  active={!waiting}
                  busy={busy}
                  mode="idle"
                  onAction={runAction}
                />
              </div>
            </div>

            <div
              aria-hidden={!waiting}
              className={`absolute inset-0 flex flex-col justify-center transition-[opacity,filter] duration-1000 ease-in-out motion-reduce:transition-none ${
                waiting
                  ? "opacity-100 blur-0"
                  : "pointer-events-none opacity-0 blur-md"
              }`}
            >
              <BrainWaitingGuide active={waiting} />
              <LobbyActionButton
                active={waiting}
                busy={busy}
                mode="waiting"
                onAction={runAction}
              />
            </div>
          </div>
        )}

        {error ? (
          <p role="alert" className="mt-4 text-xs text-[var(--danger-text)]">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="mt-4 text-xs text-[var(--muted)]">
            {notice}
          </p>
        ) : null}
      </div>
    </section>
  );
}
