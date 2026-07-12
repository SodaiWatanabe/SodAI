type AuthError = {
  code?: string;
  message?: string;
  status?: number;
};

const errorMessages: Record<string, string> = {
  EMAIL_NOT_VERIFIED:
    "メールアドレスの確認が必要です。確認メールを再送しました。",
  INVALID_EMAIL_OR_PASSWORD: "メールアドレスまたはパスワードを確認してください。",
  INVALID_PASSWORD: "メールアドレスまたはパスワードを確認してください。",
  INVALID_TOKEN: "リンクが無効か、有効期限が切れています。もう一度お試しください。",
  TOO_MANY_REQUESTS: "操作が続きすぎています。少し時間をおいてお試しください。",
  USER_ALREADY_EXISTS:
    "登録を受け付けました。アカウントが利用可能な場合は確認メールが届きます。",
};

export function getAuthErrorMessage(
  error: AuthError | null | undefined,
  fallback: string,
): string {
  if (!error) {
    return fallback;
  }

  if (error.status === 429) {
    return errorMessages.TOO_MANY_REQUESTS;
  }

  return (error.code && errorMessages[error.code]) || fallback;
}
