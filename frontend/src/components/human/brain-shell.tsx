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
import { BrainConversation } from "@/components/human/brain-conversation";
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
    });
    return () => {
      window.clearTimeout(initialRefresh);
      unsubscribe();
    };
  }, [realtimeReadyRevision, refresh, subscribeRealtime]);

  useEffect(() => {
    if (!authenticated || !brainActive) return;
    const timer = window.setInterval(() => {
      if (!busyRef.current) void requestState(humanApi.ready);
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [authenticated, brainActive, humanApi, requestState]);

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
    const claimId = state?.assignment?.claim_id;
    if (!content || !claimId || busy) return;
    await run(() => humanApi.answer(claimId, content));
  }

  if (!authenticated) {
    return (
      <section className="grid flex-1 place-items-center px-6">
        <div className="max-w-sm text-center">
          <h1 className="text-2xl font-semibold tracking-[-0.04em] text-[var(--text)]">
            SodAI Brain
          </h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Humanとしてプロンプトに答えるには、ログインしてください。
          </p>
          <button
            type="button"
            className="mt-6 h-10 rounded-full bg-[var(--primary)] px-5 text-sm font-medium text-[var(--on-primary)] hover:bg-[var(--primary-hover)]"
            onClick={openAuth}
          >
            ログイン
          </button>
        </div>
      </section>
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
          <div className="mx-auto flex h-full w-full max-w-[760px] items-center px-12 sm:px-8 lg:mx-0 lg:max-w-none lg:px-1.5">
            <p className="truncate rounded-xl px-2.5 py-2 text-sm font-semibold text-[var(--text)]">
              {assignment.answerer_name}
            </p>
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
                    disabled={busy || !answer.trim()}
                    className="h-10 rounded-full bg-[var(--primary)] px-5 text-sm font-medium text-[var(--on-primary)] hover:bg-[var(--primary-hover)] disabled:opacity-40"
                  >
                    回答する
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
    <section className="grid flex-1 place-items-center px-6">
      <div className="w-full max-w-sm text-center">
        <p className="text-xs font-medium text-[var(--muted)]">
          {state.rank_name}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-[var(--text)]">
          {state.status === "waiting" ? "割り当てを待っています" : "SodAI Brain"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
          {state.status === "waiting"
            ? "条件に合うプロンプトが届くと、ここに表示されます。"
            : "準備ができたら、Humanとしてプロンプトに答えられます。"}
        </p>
        {state.status === "waiting" ? (
          <button
            type="button"
            disabled={busy}
            className="mt-6 h-10 rounded-full border border-[var(--border)] px-5 text-sm font-medium text-[var(--text)] hover:bg-[var(--hover)] disabled:opacity-50"
            onClick={() => run(humanApi.stop)}
          >
            待機をやめる
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            className="mt-6 h-10 rounded-full bg-[var(--primary)] px-5 text-sm font-medium text-[var(--on-primary)] hover:bg-[var(--primary-hover)] disabled:opacity-50"
            onClick={() => run(humanApi.ready)}
          >
            脳の重みをロード
          </button>
        )}
        {error ? <p className="mt-4 text-xs text-[var(--danger-text)]">{error}</p> : null}
      </div>
    </section>
  );
}
