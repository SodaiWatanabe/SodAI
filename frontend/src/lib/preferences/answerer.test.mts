import assert from "node:assert/strict";
import test from "node:test";

import {
  createPreferredAnswererCookie,
  parsePreferredAnswerer,
  resolvePreferredAnswerer,
} from "./answerer.ts";

const answerers = [
  { id: "asuka-1.1", is_default: true },
  { id: "hina", is_default: false },
  { id: "human-pro", is_default: false },
];

test("最後に選択した回答者を種別にかかわらず復元する", () => {
  assert.equal(resolvePreferredAnswerer(answerers, "hina"), "hina");
  assert.equal(
    resolvePreferredAnswerer(answerers, "asuka-1"),
    "asuka-1.1",
  );
  assert.equal(
    resolvePreferredAnswerer(answerers, "human-pro"),
    "human-pro",
  );
});

test("保存済みの回答者が利用不能なら既定値へ戻す", () => {
  assert.equal(
    resolvePreferredAnswerer(answerers, "retired-answerer"),
    "asuka-1.1",
  );
  assert.equal(resolvePreferredAnswerer(answerers, undefined), "asuka-1.1");
  assert.equal(
    resolvePreferredAnswerer(
      answerers.map((answerer) => ({ ...answerer, is_default: false })),
      undefined,
    ),
    "asuka-1.1",
  );
  assert.equal(resolvePreferredAnswerer([], "asuka-1.1"), undefined);
});

test("回答者IDをCookieへ安全に保存して復元する", () => {
  const cookie = createPreferredAnswererCookie("human pro/v2", true);
  assert.equal(
    cookie,
    "sodai_preferred_answerer=human%20pro%2Fv2; Path=/; Max-Age=31536000; SameSite=Lax; Secure",
  );
  assert.equal(parsePreferredAnswerer("human pro/v2"), "human pro/v2");
  assert.equal(parsePreferredAnswerer(""), undefined);
  assert.equal(parsePreferredAnswerer("a".repeat(129)), undefined);
});
