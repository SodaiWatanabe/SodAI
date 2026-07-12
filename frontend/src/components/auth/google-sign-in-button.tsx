"use client";

import { useState } from "react";

import { authClient } from "@/lib/auth/client";
import { getAuthErrorMessage } from "@/lib/auth/error-message";

export function GoogleSignInButton({ enabled }: { enabled: boolean }) {
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();

  async function signInWithGoogle() {
    setPending(true);
    setErrorMessage(undefined);

    const { error } = await authClient.signIn.social({
      provider: "google",
      callbackURL: "/account",
      errorCallbackURL: "/auth/login?error=google",
    });

    if (error) {
      setErrorMessage(
        getAuthErrorMessage(error, "Googleでログインできませんでした。"),
      );
      setPending(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        disabled={!enabled || pending}
        onClick={signInWithGoogle}
        className="flex w-full items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-slate-950/5 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5">
          <path
            fill="#4285F4"
            d="M21.6 12.227c0-.709-.064-1.391-.182-2.045H12v3.868h5.382a4.6 4.6 0 0 1-1.995 3.018v2.509h3.232c1.891-1.741 2.982-4.305 2.982-7.35Z"
          />
          <path
            fill="#34A853"
            d="M12 22c2.7 0 4.964-.895 6.618-2.423l-3.232-2.51c-.895.6-2.04.955-3.386.955-2.605 0-4.81-1.759-5.6-4.123H3.06v2.59A9.997 9.997 0 0 0 12 22Z"
          />
          <path
            fill="#FBBC05"
            d="M6.4 13.9A6.014 6.014 0 0 1 6.086 12c0-.66.114-1.305.314-1.9V7.51H3.06A9.997 9.997 0 0 0 2 12c0 1.614.386 3.141 1.059 4.49L6.4 13.9Z"
          />
          <path
            fill="#EA4335"
            d="M12 5.977c1.468 0 2.786.505 3.823 1.496l2.868-2.868C16.959 2.99 14.695 2 12 2a9.997 9.997 0 0 0-8.941 5.51L6.4 10.1c.791-2.364 2.995-4.123 5.6-4.123Z"
          />
        </svg>
        {pending ? "Googleへ接続中…" : "Googleで続ける"}
      </button>
      {!enabled ? (
        <p className="mt-2 text-center text-xs text-slate-400">
          Google OAuthは環境設定後に有効になります。
        </p>
      ) : null}
      {errorMessage ? (
        <p role="alert" className="mt-2 text-center text-xs text-rose-600">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
