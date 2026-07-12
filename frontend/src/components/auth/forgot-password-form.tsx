"use client";

import { type FormEvent, useState } from "react";

import { FormField, FormNotice, SubmitButton } from "./form-primitives";
import { authClient } from "@/lib/auth/client";
import { getAuthErrorMessage } from "@/lib/auth/error-message";

export function ForgotPasswordForm() {
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();
  const [success, setSuccess] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrorMessage(undefined);

    const formData = new FormData(event.currentTarget);
    const { error } = await authClient.requestPasswordReset({
      email: String(formData.get("email")),
      redirectTo: `${window.location.origin}/auth/reset-password`,
    });

    if (error) {
      setErrorMessage(
        getAuthErrorMessage(error, "再設定メールを送信できませんでした。"),
      );
      setPending(false);
      return;
    }

    setSuccess(true);
    setPending(false);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {errorMessage ? <FormNotice kind="error">{errorMessage}</FormNotice> : null}
      {success ? (
        <FormNotice kind="success">
          アカウントが存在する場合、パスワード再設定メールが届きます。
        </FormNotice>
      ) : null}
      <FormField
        label="メールアドレス"
        name="email"
        type="email"
        autoComplete="email"
        inputMode="email"
        required
        disabled={pending || success}
        placeholder="you@example.com"
      />
      <SubmitButton pending={pending}>再設定メールを送る</SubmitButton>
    </form>
  );
}
