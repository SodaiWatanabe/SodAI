import assert from "node:assert/strict";
import test from "node:test";

import { shouldShowHumanPrivacyDialog } from "./human-privacy-transition.ts";

test("AIからHumanへ切り替えるときだけ注意モーダルを表示する", () => {
  assert.equal(
    shouldShowHumanPrivacyDialog({ kind: "ai" }, { kind: "human" }),
    true,
  );
  assert.equal(
    shouldShowHumanPrivacyDialog({ kind: "human" }, { kind: "human" }),
    false,
  );
  assert.equal(
    shouldShowHumanPrivacyDialog({ kind: "ai" }, { kind: "ai" }),
    false,
  );
  assert.equal(
    shouldShowHumanPrivacyDialog({ kind: "human" }, { kind: "ai" }),
    false,
  );
  assert.equal(
    shouldShowHumanPrivacyDialog(undefined, { kind: "human" }),
    false,
  );
});
