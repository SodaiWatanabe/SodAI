"use client";

import { type FormEvent, useState } from "react";

import { FormField, FormNotice, SubmitButton } from "./form-primitives";
import { authClient } from "@/lib/auth/client";
import { getAuthErrorMessage } from "@/lib/auth/error-message";

export function RegisterForm() {
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();
  const [success, setSuccess] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrorMessage(undefined);
    setSuccess(false);

    const formData = new FormData(event.currentTarget);
    const password = String(formData.get("password"));
    const passwordConfirmation = String(formData.get("passwordConfirmation"));

    if (password !== passwordConfirmation) {
      setErrorMessage("確認用パスワードが一致しません。");
      setPending(false);
      return;
    }

    const { error } = await authClient.signUp.email({
      name: String(formData.get("name")),
      email: String(formData.get("email")),
      password,
      callbackURL: "/account",
    });

    if (error) {
      setErrorMessage(
        getAuthErrorMessage(error, "登録を完了できませんでした。"),
      );
      setPending(false);
      return;
    }

    setSuccess(true);
    setPending(false);
    event.currentTarget.reset();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {errorMessage ? <FormNotice kind="error">{errorMessage}</FormNotice> : null}
      {success ? (
        <FormNotice kind="success">
          登録を受け付けました。届いたメールのリンクから登録を完了してください。
        </FormNotice>
      ) : null}
      <FormField
        label="表示名"
        name="name"
        type="text"
        autoComplete="name"
        required
        disabled={pending}
        minLength={1}
        maxLength={80}
        placeholder="蒼大"
      />
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
      <FormField
        label="パスワード"
        hint="12文字以上で設定してください。"
        name="password"
        type="password"
        autoComplete="new-password"
        required
        disabled={pending}
        minLength={12}
        maxLength={128}
      />
      <FormField
        label="パスワード（確認）"
        name="passwordConfirmation"
        type="password"
        autoComplete="new-password"
        required
        disabled={pending}
        minLength={12}
        maxLength={128}
      />
      <SubmitButton pending={pending}>アカウントを作成</SubmitButton>
      <p className="text-center text-xs leading-5 text-slate-400">
        登録後、届いたメールからアドレスの確認が必要です。
      </p>
    </form>
  );
}
