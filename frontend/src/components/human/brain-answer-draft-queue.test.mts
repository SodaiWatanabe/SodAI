import assert from "node:assert/strict";
import test from "node:test";

import { createBrainAnswerDraftQueue } from "./brain-answer-draft-queue.ts";

test("変更された下書きだけを単調増加するrevisionで保存する", async () => {
  const saves: Array<{ content: string; revision: number }> = [];
  const queue = createBrainAnswerDraftQueue({
    claimId: "claim",
    content: "",
    revision: 0,
    saveDraft: async (_claimId, content, revision) => {
      saves.push({ content, revision });
      return revision;
    },
  });

  await queue.persist();
  queue.setContent("入力中");
  await queue.persist();
  await queue.persist();
  queue.setContent("入力中の回答");
  await queue.persist();

  assert.deepEqual(saves, [
    { content: "入力中", revision: 1 },
    { content: "入力中の回答", revision: 2 },
  ]);
});

test("保存失敗後も同じ内容を新しいrevisionで再試行する", async () => {
  const revisions: number[] = [];
  const queue = createBrainAnswerDraftQueue({
    claimId: "claim",
    content: "",
    revision: 3,
    saveDraft: async (_claimId, _content, revision) => {
      revisions.push(revision);
      if (revisions.length === 1) throw new Error("temporary failure");
      return revision;
    },
  });

  queue.setContent("失われない回答");
  await queue.persist();
  await queue.persist();

  assert.deepEqual(revisions, [4, 5]);
  assert.equal(queue.readContent(), "失われない回答");
});

test("サーバーから復元したrevisionより後ろへ保存する", async () => {
  let savedRevision = 0;
  const queue = createBrainAnswerDraftQueue({
    claimId: "claim",
    content: "復元済み",
    revision: 2,
    saveDraft: async (_claimId, _content, revision) => {
      savedRevision = revision;
      return revision;
    },
  });

  queue.acceptRevision(8);
  queue.setContent("再開後の回答");
  await queue.persist();

  assert.equal(savedRevision, 9);
});
