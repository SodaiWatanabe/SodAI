"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { FormField, FormNotice, SubmitButton } from "./form-primitives";
import { authClient } from "@/lib/auth/client";
import { getAuthErrorMessage } from "@/lib/auth/error-message";

export function ResetPasswordForm({ token }: { token?: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      setErrorMessage("再設定リンクが無効です。もう一度メールを送信してください。");
      return;
    }

    setPending(true);
    setErrorMessage(undefined);
    const formData = new FormData(event.currentTarget);
    const password = String(formData.get("password"));
    const passwordConfirmation = String(formData.get("passwordConfirmation"));

    if (password !== passwordConfirmation) {
      setErrorMessage("確認用パスワードが一致しません。");
      setPending(false);
      return;
    }

    const { error } = await authClient.resetPassword({
      newPassword: password,
      token,
    });

    if (error) {
      setErrorMessage(
        getAuthErrorMessage(error, "パスワードを再設定できませんでした。"),
      );
      setPending(false);
      return;
    }

    router.replace("/auth/login?reset=completed");
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {!token ? (
        <FormNotice kind="error">
          再設定リンクが無効か、有効期限が切れています。
        </FormNotice>
      ) : null}
      {errorMessage ? <FormNotice kind="error">{errorMessage}</FormNotice> : null}
      <FormField
        label="新しいパスワード"
        hint="12文字以上で設定してください。"
        name="password"
        type="password"
        autoComplete="new-password"
        required
        disabled={pending || !token}
        minLength={12}
        maxLength={128}
      />
      <FormField
        label="新しいパスワード（確認）"
        name="passwordConfirmation"
        type="password"
        autoComplete="new-password"
        required
        disabled={pending || !token}
        minLength={12}
        maxLength={128}
      />
      <SubmitButton pending={pending}>パスワードを更新</SubmitButton>
    </form>
  );
}
