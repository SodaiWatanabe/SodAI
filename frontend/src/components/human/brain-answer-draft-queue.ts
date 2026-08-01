export type SaveBrainAnswerDraft = (
  claimId: string,
  content: string,
  revision: number,
) => Promise<number>;

export function createBrainAnswerDraftQueue({
  claimId,
  content: initialContent,
  revision: initialRevision,
  saveDraft,
}: {
  claimId: string;
  content: string;
  revision: number;
  saveDraft: SaveBrainAnswerDraft;
}) {
  let content = initialContent;
  let revision = initialRevision;
  let persistedContent = initialContent;
  let queuedContent = initialContent;
  let saveChain = Promise.resolve();

  function persist() {
    const contentToSave = content;
    if (contentToSave === queuedContent) return saveChain;

    const revisionToSave = revision + 1;
    revision = revisionToSave;
    queuedContent = contentToSave;

    const save = async () => {
      try {
        const savedRevision = await saveDraft(
          claimId,
          contentToSave,
          revisionToSave,
        );
        revision = Math.max(revision, savedRevision);
        persistedContent = contentToSave;
      } catch {
        if (revision === revisionToSave) queuedContent = persistedContent;
      }
    };

    saveChain = saveChain.then(save, save);
    return saveChain;
  }

  return {
    acceptRevision(serverRevision: number) {
      revision = Math.max(revision, serverRevision);
    },
    persist,
    readContent: () => content,
    setContent(nextContent: string) {
      content = nextContent;
    },
  };
}
