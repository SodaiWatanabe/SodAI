import assert from "node:assert/strict";
import test from "node:test";

import {
  hasMessageListMarkdown,
  parseMessageMarkdown,
} from "./message-markdown.ts";

test("行頭のハイフン項目を箇条書きとしてまとめる", () => {
  assert.deepEqual(parseMessageMarkdown("候補です。\n- 一つ目\n- 二つ目"), [
    { kind: "text", content: "候補です。" },
    { kind: "unordered-list", items: ["一つ目", "二つ目"] },
  ]);
});

test("文中のハイフンと空白のないハイフンは通常文として保つ", () => {
  const content = "東京-大阪\n-箇条書きではない";

  assert.deepEqual(parseMessageMarkdown(content), [
    { kind: "text", content },
  ]);
});

test("通常文を挟んだ箇条書きは別のリストに分ける", () => {
  assert.deepEqual(parseMessageMarkdown("- 前\n説明\n- 後"), [
    { kind: "unordered-list", items: ["前"] },
    { kind: "text", content: "説明" },
    { kind: "unordered-list", items: ["後"] },
  ]);
});

test("番号付きの連続行を先頭番号付きの箇条書きとしてまとめる", () => {
  assert.deepEqual(parseMessageMarkdown("候補です。\n1. 一つ目\n2. 二つ目"), [
    { kind: "text", content: "候補です。" },
    { kind: "ordered-list", start: 1, items: ["一つ目", "二つ目"] },
  ]);

  assert.deepEqual(parseMessageMarkdown("3. 三つ目\n4. 四つ目"), [
    { kind: "ordered-list", start: 3, items: ["三つ目", "四つ目"] },
  ]);
});

test("ストリーミング途中でも完成したリスト記号を検出する", () => {
  assert.equal(hasMessageListMarkdown("説明\n- "), true);
  assert.equal(hasMessageListMarkdown("説明\n1. "), true);
  assert.equal(hasMessageListMarkdown("説明\n1."), false);
});
