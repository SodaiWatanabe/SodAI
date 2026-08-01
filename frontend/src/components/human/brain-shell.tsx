"use client";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import { useChatData } from "@/components/chat/chat-data-provider";
import { BrainAssignmentView } from "@/components/human/brain-assignment-view";
import { BrainLobby } from "@/components/human/brain-lobby";
import { useHumanData } from "@/components/human/human-data-provider";
import { IOSSpinner } from "@/components/ui/ios-spinner";

export function BrainShell() {
  const { authenticated, openAuth } = useChatAuth();
  const { answerers } = useChatData();
  const {
    busy,
    error,
    notice,
    state,
    toggleReadiness,
  } = useHumanData();

  if (!authenticated) {
    return <BrainLobby mode="signed-out" onAction={openAuth} />;
  }

  if (!state) {
    return (
      <div className="grid flex-1 place-items-center">
        {error ? (
          <p role="alert" className="text-sm text-[var(--muted)]">
            {error}
          </p>
        ) : (
          <IOSSpinner label="Brainを読み込み中" />
        )}
      </div>
    );
  }

  if (state.status === "assigned" && state.assignment) {
    return (
      <BrainAssignmentView
        key={state.assignment.claim_id}
        assignment={state.assignment}
      />
    );
  }

  const humanAnswerers = answerers.filter(
    (answerer) => answerer.kind === "human" && !answerer.is_legacy,
  );
  const conditionKey = [
    ...state.answer_conditions.answerer_ids,
    "|",
    ...state.answer_conditions.reasoning_efforts,
    "|",
    ...state.available_answerer_ids,
  ].join(":");

  return (
    <BrainLobby
      key={conditionKey}
      answerers={humanAnswerers}
      availableAnswererIds={state.available_answerer_ids}
      busy={busy}
      conditions={state.answer_conditions}
      error={error}
      mode={state.status === "waiting" ? "waiting" : "idle"}
      notice={notice}
      onAction={(conditions) => toggleReadiness(conditions)}
      rankName={state.rank_name}
    />
  );
}
