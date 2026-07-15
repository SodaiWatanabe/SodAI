import assert from "node:assert/strict";
import test from "node:test";

import { splitSearchHighlight } from "./search-highlight.ts";

test("検索語に一致するすべての文字列を大文字小文字を区別せず分割する", () => {
  assert.deepEqual(splitSearchHighlight("SodAIとsodai", "sodai"), [
    { highlighted: true, text: "SodAI" },
    { highlighted: false, text: "と" },
    { highlighted: true, text: "sodai" },
  ]);
});

test("正規表現の記号を検索構文ではなく文字列として扱う", () => {
  assert.deepEqual(splitSearchHighlight("a+b と a.b", "a+b"), [
    { highlighted: true, text: "a+b" },
    { highlighted: false, text: " と a.b" },
  ]);
});

test("空の検索語や一致しない検索語は本文をそのまま返す", () => {
  assert.deepEqual(splitSearchHighlight("会話本文", " "), [
    { highlighted: false, text: "会話本文" },
  ]);
  assert.deepEqual(splitSearchHighlight("会話本文", "不一致"), [
    { highlighted: false, text: "会話本文" },
  ]);
});
