import assert from "node:assert/strict";
import test from "node:test";

import { getClientIpAddressHeaders } from "../src/environment.js";

function withTrustedHeader(value: string | undefined, assertion: () => void): void {
  const previous = process.env.AUTH_TRUSTED_CLIENT_IP_HEADER;
  try {
    if (value === undefined) {
      delete process.env.AUTH_TRUSTED_CLIENT_IP_HEADER;
    } else {
      process.env.AUTH_TRUSTED_CLIENT_IP_HEADER = value;
    }
    assertion();
  } finally {
    if (previous === undefined) {
      delete process.env.AUTH_TRUSTED_CLIENT_IP_HEADER;
    } else {
      process.env.AUTH_TRUSTED_CLIENT_IP_HEADER = previous;
    }
  }
}

test("明示されていない転送ヘッダーはクライアントIPとして信用しない", () => {
  withTrustedHeader(undefined, () => {
    assert.deepEqual(getClientIpAddressHeaders(), ["x-sodai-remote-address"]);
  });
});

test("信頼済みgatewayのヘッダーだけを直接接続元より優先する", () => {
  withTrustedHeader("CF-Connecting-IP", () => {
    assert.deepEqual(getClientIpAddressHeaders(), [
      "cf-connecting-ip",
      "x-sodai-remote-address",
    ]);
  });
});

test("proxy経路と共有していないヘッダーは設定できない", () => {
  withTrustedHeader("invalid header", () => {
    assert.throws(() => getClientIpAddressHeaders(), /cf-connecting-ip/);
  });
  withTrustedHeader("true-client-ip", () => {
    assert.throws(() => getClientIpAddressHeaders(), /x-forwarded-for/);
  });
});
