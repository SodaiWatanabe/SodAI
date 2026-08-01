"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  createBrainAnswerDraftQueue,
  type SaveBrainAnswerDraft,
} from "@/components/human/brain-answer-draft-queue";
import type { HumanAssignment } from "@/lib/human/types";

const DRAFT_SAVE_DELAY_MS = 400;

export function useBrainAnswerDraft(
  assignment: HumanAssignment,
  saveDraft: SaveBrainAnswerDraft,
) {
  const [answer, setAnswerState] = useState(assignment.draft_content);
  const [draftQueue] = useState(() =>
    createBrainAnswerDraftQueue({
      claimId: assignment.claim_id,
      content: assignment.draft_content,
      revision: assignment.draft_revision,
      saveDraft,
    }),
  );
  const saveTimerRef = useRef<number | undefined>(undefined);

  const clearSaveTimer = useCallback(() => {
    if (saveTimerRef.current !== undefined) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = undefined;
    }
  }, []);

  const persistDraft = useCallback(() => draftQueue.persist(), [draftQueue]);

  const flushDraft = useCallback(() => {
    clearSaveTimer();
    return persistDraft();
  }, [clearSaveTimer, persistDraft]);

  const setAnswer = useCallback(
    (content: string) => {
      draftQueue.setContent(content);
      setAnswerState(content);
      clearSaveTimer();
      saveTimerRef.current = window.setTimeout(() => {
        saveTimerRef.current = undefined;
        void persistDraft();
      }, DRAFT_SAVE_DELAY_MS);
    },
    [clearSaveTimer, draftQueue, persistDraft],
  );

  const readAnswer = useCallback(() => draftQueue.readContent(), [draftQueue]);

  useEffect(() => {
    draftQueue.acceptRevision(assignment.draft_revision);
  }, [assignment.draft_revision, draftQueue]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") void flushDraft();
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      void flushDraft();
    };
  }, [flushDraft]);

  return { answer, flushDraft, readAnswer, setAnswer };
}
