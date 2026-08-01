"use client";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import { BrainAssignmentView } from "@/components/human/brain-assignment-view";
import { BrainLobby } from "@/components/human/brain-lobby";
import { useHumanData } from "@/components/human/human-data-provider";
import { IOSSpinner } from "@/components/ui/ios-spinner";

export function BrainShell() {
  const { authenticated, openAuth } = useChatAuth();
  const { busy, error, notice, state, toggleReadiness } = useHumanData();

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

  return (
    <BrainLobby
      busy={busy}
      error={error}
      mode={state.status === "waiting" ? "waiting" : "idle"}
      notice={notice}
      onAction={() => void toggleReadiness()}
    />
  );
}
