"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { FormField, FormNotice, SubmitButton } from "./form-primitives";
import { authClient } from "@/lib/auth/client";
import { getAuthErrorMessage } from "@/lib/auth/error-message";

export function LoginForm({ initialError }: { initialError?: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState(
    initialError ? "Googleログインを完了できませんでした。" : undefined,
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrorMessage(undefined);

    const formData = new FormData(event.currentTarget);
    const { error } = await authClient.signIn.email({
      email: String(formData.get("email")),
      password: String(formData.get("password")),
      callbackURL: "/account",
    });

    if (error) {
      setErrorMessage(
        getAuthErrorMessage(
          error,
          "ログインできませんでした。入力内容を確認してください。",
        ),
      );
      setPending(false);
      return;
    }

    router.replace("/account");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {errorMessage ? <FormNotice kind="error">{errorMessage}</FormNotice> : null}
      <FormField
        label="メールアドレス"
        name="email"
        type="email"
        autoComplete="email"
        inputMode="email"
        required
        disabled={pending}
        placeholder="you@example.com"
      />
      <div>
        <FormField
          label="パスワード"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          disabled={pending}
          minLength={12}
        />
        <div className="mt-2 text-right">
          <Link
            href="/auth/forgot-password"
            className="text-xs font-medium text-blue-600 transition hover:text-blue-700"
          >
            パスワードを忘れた場合
          </Link>
        </div>
      </div>
      <SubmitButton pending={pending}>ログイン</SubmitButton>
    </form>
  );
}
