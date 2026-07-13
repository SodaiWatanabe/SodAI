import assert from "node:assert/strict";
import test from "node:test";

import {
  getAccountDestination,
  getInitialAuthStep,
} from "./auth-flow.ts";

test("通常の認証はメール入力から始まる", () => {
  assert.equal(
    getInitialAuthStep({ accountUnavailable: false, resumeProfile: false }),
    "email",
  );
});

test("未完了プロフィールは再読込後も再開する", () => {
  assert.equal(
    getInitialAuthStep({ accountUnavailable: false, resumeProfile: true }),
    "profile",
  );
});

test("利用できないアカウントはプロフィールより優先して遮断する", () => {
  assert.equal(
    getInitialAuthStep({ accountUnavailable: true, resumeProfile: true }),
    "blocked",
  );
  assert.equal(
    getAccountDestination({ display_name: null, status: "suspended" }),
    "blocked",
  );
});

test("有効な新規アカウントだけプロフィール設定へ進む", () => {
  assert.equal(
    getAccountDestination({ display_name: null, status: "active" }),
    "profile",
  );
  assert.equal(
    getAccountDestination({ display_name: "雛", status: "active" }),
    "authenticated",
  );
});
