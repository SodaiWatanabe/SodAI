"use client";

import { useSelectedLayoutSegments } from "next/navigation";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useChatData } from "@/components/chat/chat-data-provider";
import { resolveChatFrameRoute } from "@/components/chat/chat-frame-route";
import { removeResolvedAssignment } from "@/components/human/brain-assignment-state";
import { useToast } from "@/components/ui/toast-provider";
import type {
  BrainState,
  HumanAnswerDetail,
  HumanAnswerSummary,
} from "@/lib/human/types";
import { useHumanApi } from "@/lib/human/use-human-api";

type HumanDataContextValue = {
  answerClaim: (claimId: string, content: string) => Promise<boolean>;
  answers: HumanAnswerSummary[];
  answersLoading: boolean;
  busy: boolean;
  declineClaim: (claimId: string) => Promise<boolean>;
  deadlineExpired: boolean;
  error?: string;
  getAnswer: (executionId: string) => Promise<HumanAnswerDetail>;
  loadMoreAnswers: () => Promise<void>;
  nextAnswersCursor: string | null;
  notice?: string;
  refreshAnswers: () => void;
  refreshState: () => Promise<void>;
  saveClaimDraft: (
    claimId: string,
    content: string,
    revision: number,
  ) => Promise<number>;
  skipClaim: (claimId: string) => Promise<boolean>;
  state?: BrainState;
  toggleReadiness: () => Promise<boolean>;
};

const HumanDataContext = createContext<HumanDataContextValue | null>(null);

export function HumanDataProvider({
  authenticated,
  children,
}: {
  authenticated: boolean;
  children: ReactNode;
}) {
  const childSegments = useSelectedLayoutSegments();
  const brainVisible = resolveChatFrameRoute(childSegments).product === "brain";
  const humanApi = useHumanApi();
  const { realtimeReadyRevision, subscribeRealtime } = useChatData();
  const { dismissToast, showToast } = useToast();
  const [state, setState] = useState<BrainState>();
  const [answers, setAnswers] = useState<HumanAnswerSummary[]>([]);
  const [nextAnswersCursor, setNextAnswersCursor] = useState<string | null>(null);
  const [answersLoading, setAnswersLoading] = useState(true);
  const [answersVersion, setAnswersVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [deadlineExpired, setDeadlineExpired] = useState(false);
  const busyRef = useRef(false);
  const claimIdRef = useRef<string | undefined>(undefined);
  const deadlineReconciliationClaimRef = useRef<string | undefined>(undefined);
  const stateGenerationRef = useRef(0);
  const answersGenerationRef = useRef(0);
  const brainActive = state?.status === "waiting" || state?.status === "assigned";

  const applyState = useCallback((nextState: BrainState) => {
    const nextClaimId = nextState.assignment?.claim_id;
    if (claimIdRef.current !== nextClaimId) {
      setError(undefined);
      setDeadlineExpired(false);
      deadlineReconciliationClaimRef.current = undefined;
      if (nextClaimId) setNotice(undefined);
    }
    claimIdRef.current = nextClaimId;
    setState(nextState);
  }, []);

  const requestState = useCallback(
    async (
      action: () => Promise<BrainState>,
      errorMessage?: string,
    ): Promise<boolean> => {
      const generation = ++stateGenerationRef.current;
      try {
        const nextState = await action();
        if (generation !== stateGenerationRef.current) return false;
        applyState(nextState);
        setError(undefined);
        return true;
      } catch {
        if (generation === stateGenerationRef.current && errorMessage) {
          setError(errorMessage);
        }
        return false;
      }
    },
    [applyState],
  );

  const refreshState = useCallback(async () => {
    if (!authenticated || busyRef.current) return;
    await requestState(humanApi.state, "Brainへ接続できませんでした。");
  }, [authenticated, humanApi, requestState]);

  const refreshAnswers = useCallback(() => {
    setAnswersLoading(true);
    setAnswersVersion((version) => version + 1);
  }, []);

  const run = useCallback(
    async (action: () => Promise<BrainState>): Promise<boolean> => {
      if (busyRef.current) return false;
      busyRef.current = true;
      setBusy(true);
      setError(undefined);
      try {
        return await requestState(
          action,
          "操作を完了できませんでした。もう一度お試しください。",
        );
      } finally {
        busyRef.current = false;
        setBusy(false);
      }
    },
    [requestState],
  );

  useEffect(() => {
    if (!authenticated) {
      claimIdRef.current = undefined;
      return;
    }
    const initialRefresh = window.setTimeout(() => void refreshState(), 0);
    const unsubscribe = subscribeRealtime((event) => {
      if (event.type === "human.assigned") void refreshState();
      const resolvedClaimId = event.data.claim_id;
      if (
        event.type === "human.answer.auto_submitted" &&
        resolvedClaimId &&
        resolvedClaimId === claimIdRef.current
      ) {
        claimIdRef.current = undefined;
        setError(undefined);
        setDeadlineExpired(false);
        setNotice("入力中の回答を自動送信しました。");
        setState((current) =>
          removeResolvedAssignment(current, resolvedClaimId, "idle"),
        );
        refreshAnswers();
        void requestState(humanApi.state);
        return;
      }
      if (
        event.type === "human.assignment.cancelled" &&
        resolvedClaimId &&
        resolvedClaimId === claimIdRef.current
      ) {
        claimIdRef.current = undefined;
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
          removeResolvedAssignment(
            current,
            resolvedClaimId,
            event.data.reason === "requester_cancelled" ? "waiting" : "idle",
          ),
        );
        void requestState(humanApi.state);
      }
    });
    return () => {
      window.clearTimeout(initialRefresh);
      unsubscribe();
    };
  }, [
    authenticated,
    humanApi,
    refreshAnswers,
    refreshState,
    requestState,
    subscribeRealtime,
  ]);

  useEffect(() => {
    if (!authenticated || !brainVisible || !brainActive) return;
    const timer = window.setInterval(() => {
      if (!busyRef.current) void requestState(humanApi.ready);
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [authenticated, brainActive, brainVisible, humanApi, requestState]);

  useEffect(() => {
    if (!authenticated || !brainVisible) return;
    void refreshState();
  }, [authenticated, brainVisible, realtimeReadyRevision, refreshState]);

  useEffect(() => {
    if (!authenticated || !brainVisible || state || !error) return;
    const timer = window.setInterval(() => void refreshState(), 5_000);
    return () => window.clearInterval(timer);
  }, [authenticated, brainVisible, error, refreshState, state]);

  useEffect(() => {
    const deadlineAt = state?.assignment?.deadline_at;
    if (!deadlineAt || !brainVisible) return;
    const remaining = Date.parse(deadlineAt) - Date.now();
    const timer = window.setTimeout(
      () => {
        setDeadlineExpired(true);
        setNotice("入力中の回答を送信しています。");
      },
      Math.max(0, remaining) + 100,
    );
    return () => window.clearTimeout(timer);
  }, [brainVisible, state?.assignment?.deadline_at]);

  useEffect(() => {
    const claimId = state?.assignment?.claim_id;
    if (!brainVisible || !deadlineExpired || busy || !claimId) return;
    if (deadlineReconciliationClaimRef.current === claimId) return;
    deadlineReconciliationClaimRef.current = claimId;
    void requestState(
      humanApi.ready,
      "入力中の回答を確定できませんでした。もう一度お試しください。",
    ).then((reconciled) => {
      if (!reconciled) deadlineReconciliationClaimRef.current = undefined;
    });
  }, [
    brainVisible,
    busy,
    deadlineExpired,
    humanApi,
    requestState,
    state?.assignment?.claim_id,
  ]);

  useEffect(() => {
    if (!authenticated || !brainVisible) return;
    const generation = ++answersGenerationRef.current;
    void humanApi.listAnswers().then(
      (page) => {
        if (generation !== answersGenerationRef.current) return;
        setAnswers(page.items);
        setNextAnswersCursor(page.next_cursor);
        setAnswersLoading(false);
        dismissToast("human-answer-list-load");
      },
      () => {
        if (generation !== answersGenerationRef.current) return;
        setAnswersLoading(false);
        showToast({
          id: "human-answer-list-load",
          message: "回答履歴を読み込めませんでした。",
          tone: "error",
          duration: null,
          action: { label: "再試行", onClick: refreshAnswers },
        });
      },
    );
  }, [
    answersVersion,
    authenticated,
    brainVisible,
    dismissToast,
    humanApi,
    refreshAnswers,
    showToast,
  ]);

  const loadMoreAnswers = useCallback(async () => {
    if (!nextAnswersCursor || answersLoading) return;
    setAnswersLoading(true);
    try {
      const page = await humanApi.listAnswers(nextAnswersCursor);
      setAnswers((current) => {
        const known = new Set(current.map((item) => item.execution_id));
        return [
          ...current,
          ...page.items.filter((item) => !known.has(item.execution_id)),
        ];
      });
      setNextAnswersCursor(page.next_cursor);
      dismissToast("human-answer-list-load");
    } catch {
      showToast({
        id: "human-answer-list-load",
        message: "回答履歴を読み込めませんでした。",
        tone: "error",
      });
    } finally {
      setAnswersLoading(false);
    }
  }, [
    answersLoading,
    dismissToast,
    humanApi,
    nextAnswersCursor,
    showToast,
  ]);

  const answerClaim = useCallback(
    async (claimId: string, content: string) => {
      const answered = await run(() => humanApi.answer(claimId, content));
      if (answered) refreshAnswers();
      return answered;
    },
    [humanApi, refreshAnswers, run],
  );

  const saveClaimDraft = useCallback(
    (claimId: string, content: string, revision: number) =>
      humanApi.saveDraft(claimId, content, revision),
    [humanApi],
  );

  const skipClaim = useCallback(
    (claimId: string) => run(() => humanApi.skip(claimId)),
    [humanApi, run],
  );

  const declineClaim = useCallback(
    (claimId: string) => run(() => humanApi.decline(claimId)),
    [humanApi, run],
  );

  const toggleReadiness = useCallback(
    () => run(state?.status === "waiting" ? humanApi.stop : humanApi.ready),
    [humanApi, run, state?.status],
  );

  const value = useMemo<HumanDataContextValue>(
    () => ({
      answerClaim,
      answers,
      answersLoading,
      busy,
      declineClaim,
      deadlineExpired,
      error,
      getAnswer: humanApi.getAnswer,
      loadMoreAnswers,
      nextAnswersCursor,
      notice,
      refreshAnswers,
      refreshState,
      saveClaimDraft,
      skipClaim,
      state,
      toggleReadiness,
    }),
    [
      answerClaim,
      answers,
      answersLoading,
      busy,
      declineClaim,
      deadlineExpired,
      error,
      humanApi,
      loadMoreAnswers,
      nextAnswersCursor,
      notice,
      refreshAnswers,
      refreshState,
      saveClaimDraft,
      skipClaim,
      state,
      toggleReadiness,
    ],
  );

  return (
    <HumanDataContext.Provider value={value}>
      {children}
    </HumanDataContext.Provider>
  );
}

export function useHumanData() {
  const context = useContext(HumanDataContext);
  if (!context) {
    throw new Error("useHumanData must be used inside HumanDataProvider");
  }
  return context;
}
