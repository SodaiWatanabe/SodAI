"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import { useChatData } from "@/components/chat/chat-data-provider";
import { removeCancelledAssignment } from "@/components/human/brain-assignment-state";
import { BrainAssignmentDeadline } from "@/components/human/brain-assignment-deadline";
import { BrainConversation } from "@/components/human/brain-conversation";
import { BrainLobby } from "@/components/human/brain-lobby";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import { useTextareaAutosize } from "@/components/ui/use-textarea-autosize";
import type { BrainState } from "@/lib/human/types";
import { useHumanApi } from "@/lib/human/use-human-api";

export function BrainShell() {
  const { authenticated, openAuth } = useChatAuth();
  const { realtimeReadyRevision, subscribeRealtime } = useChatData();
  const humanApi = useHumanApi();
  const [state, setState] = useState<BrainState>();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [deadlineExpired, setDeadlineExpired] = useState(false);
  const assignedViewRef = useRef<HTMLDivElement>(null);
  const answerRef = useRef<HTMLTextAreaElement>(null);
  const busyRef = useRef(false);
  const claimIdRef = useRef<string | undefined>(undefined);
  const requestGenerationRef = useRef(0);
  const brainActive = state?.status === "waiting" || state?.status === "assigned";
  const activeClaimId = state?.assignment?.claim_id;

  useTextareaAutosize(answerRef, answer, activeClaimId);

  const applyState = useCallback((nextState: BrainState) => {
    const nextClaimId = nextState.assignment?.claim_id;
    if (claimIdRef.current !== nextClaimId) {
      setAnswer("");
      setError(undefined);
      setDeadlineExpired(false);
      if (nextClaimId) setNotice(undefined);
    }
    claimIdRef.current = nextClaimId;
    setState(nextState);
  }, []);

  const requestState = useCallback(
    async (
      action: () => Promise<BrainState>,
      errorMessage?: string,
    ): Promise<void> => {
      const generation = ++requestGenerationRef.current;
      try {
        const nextState = await action();
        if (generation !== requestGenerationRef.current) return;
        applyState(nextState);
        setError(undefined);
      } catch {
        if (generation === requestGenerationRef.current && errorMessage) {
          setError(errorMessage);
        }
      }
    },
    [applyState],
  );

  const refresh = useCallback(async () => {
    if (!authenticated || busyRef.current) return;
    await requestState(
      humanApi.state,
      "Brainへ接続できませんでした。",
    );
  }, [authenticated, humanApi, requestState]);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0);
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type === "human.assigned") void refresh();
      const cancelledClaimId = event.data.claim_id;
      if (
        event.type === "human.assignment.cancelled" &&
        cancelledClaimId &&
        cancelledClaimId === claimIdRef.current
      ) {
        claimIdRef.current = undefined;
        setAnswer("");
        setError(undefined);
        setDeadlineExpired(false);
        setNotice(
          event.data.reason === "answer_deadline_exceeded"
            ? "回答時間が終了しました。"
            : event.data.reason === "assignment_expired"
              ? "接続が途切れたため、この依頼は終了しました。"
              : "依頼者がこの依頼を取り消しました。",
        );
        setState((current) =>
          removeCancelledAssignment(current, cancelledClaimId),
        );
        void requestState(humanApi.state);
      }
    });
    return () => {
      window.clearTimeout(initialRefresh);
      unsubscribe();
    };
  }, [humanApi, realtimeReadyRevision, refresh, requestState, subscribeRealtime]);

  useEffect(() => {
    if (!authenticated || !brainActive) return;
    const timer = window.setInterval(() => {
      if (!busyRef.current) void requestState(humanApi.ready);
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [authenticated, brainActive, humanApi, requestState]);

  useEffect(() => {
    const deadlineAt = state?.assignment?.deadline_at;
    if (!deadlineAt) return;
    const remaining = Date.parse(deadlineAt) - Date.now();
    const timer = window.setTimeout(
      () => {
        setDeadlineExpired(true);
        setAnswer("");
        setNotice("回答時間が終了しました。");
        void requestState(humanApi.ready);
      },
      Math.max(0, remaining) + 100,
    );
    return () => window.clearTimeout(timer);
  }, [humanApi, requestState, state?.assignment?.deadline_at]);

  useLayoutEffect(() => {
    if (!activeClaimId) return;
    const assignedView = assignedViewRef.current;
    if (assignedView) assignedView.scrollTop = assignedView.scrollHeight;
  }, [activeClaimId]);

  async function run(action: () => Promise<BrainState>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(undefined);
    try {
      await requestState(
        action,
        "操作を完了できませんでした。もう一度お試しください。",
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const content = answer.trim();
    const assignment = state?.assignment;
    const claimId = assignment?.claim_id;
    if (
      !content ||
      !claimId ||
      !assignment ||
      busy ||
      deadlineExpired ||
      Date.parse(assignment.deadline_at) <= Date.now()
    ) {
      return;
    }
    await run(() => humanApi.answer(claimId, content));
  }

  if (!authenticated) {
    return (
      <BrainLobby mode="signed-out" onAction={openAuth} />
    );
  }

  if (!state) {
    return (
      <div className="grid flex-1 place-items-center">
        {error ? (
          <button type="button" className="text-sm text-[var(--muted)]" onClick={refresh}>
            {error} 再試行
          </button>
        ) : (
          <IOSSpinner label="Brainを読み込み中" />
        )}
      </div>
    );
  }

  if (state.status === "assigned" && state.assignment) {
    const assignment = state.assignment;
    return (
      <div
        ref={assignedViewRef}
        className="flex min-h-0 flex-1 flex-col overflow-y-auto"
      >
        <header className="sticky top-0 z-10 h-12 shrink-0 border-b border-[var(--separator)] bg-[var(--canvas)]">
          <div className="mx-auto flex h-full w-full max-w-[760px] items-center justify-between pl-12 pr-2 sm:pl-12 sm:pr-5 lg:mx-0 lg:max-w-none lg:px-1.5">
            <p className="truncate rounded-xl px-2.5 py-2 text-sm font-medium text-[var(--text)]">
              <span className="text-[var(--muted)]">You are</span>{" "}
              {assignment.answerer_name}
            </p>
            <BrainAssignmentDeadline deadlineAt={assignment.deadline_at} />
          </div>
        </header>

        <section aria-label="会話" className="relative isolate flex-1">
          <div className="relative z-10 mx-auto w-full max-w-[760px] px-5 pb-[max(2rem,env(safe-area-inset-bottom))] pt-10 sm:px-8">
            <BrainConversation context={assignment.context}>
              <form onSubmit={submit}>
                <label htmlFor="human-answer" className="sr-only">
                  回答
                </label>
                <textarea
                  ref={answerRef}
                  id="human-answer"
                  value={answer}
                  rows={4}
                  maxLength={32000}
                  placeholder="回答を書く"
                  className="block min-h-[130px] w-full resize-none overflow-y-hidden border-0 bg-transparent p-0 text-[15px] leading-7 text-[var(--text)] outline-none placeholder:text-[var(--muted)]"
                  onChange={(event) => setAnswer(event.target.value)}
                />
                <div className="mt-3 flex items-center justify-between gap-3">
                  <button
                    type="button"
                    disabled={busy}
                    className="h-10 rounded-full px-4 text-sm text-[var(--muted)] hover:bg-[var(--hover)] disabled:opacity-50"
                    onClick={() =>
                      run(() => humanApi.skip(assignment.claim_id))
                    }
                  >
                    スキップ
                  </button>
                  <button
                    type="submit"
                    disabled={busy || deadlineExpired || !answer.trim()}
                    className="h-10 rounded-full bg-[var(--primary)] px-5 text-sm font-medium text-[var(--on-primary)] hover:bg-[var(--primary-hover)] disabled:opacity-40"
                  >
                    {deadlineExpired ? "時間切れ" : "回答する"}
                  </button>
                </div>
                {error ? (
                  <p className="mt-2 text-center text-xs text-[var(--danger-text)]">
                    {error}
                  </p>
                ) : null}
              </form>
            </BrainConversation>
          </div>
        </section>
      </div>
    );
  }

  return (
    <BrainLobby
      busy={busy}
      error={error}
      mode={state.status === "waiting" ? "waiting" : "idle"}
      notice={notice}
      onAction={() => {
        void run(state.status === "waiting" ? humanApi.stop : humanApi.ready);
      }}
    />
  );
}
