export type ChatMutationFailure = {
  message: string;
  tone: "error" | "warning";
};

function hasHttpStatus(error: unknown, status: number): boolean {
  return (
    error instanceof Error &&
    "status" in error &&
    (error as Error & { status: unknown }).status === status
  );
}

export function resolveChatMutationFailure(
  error: unknown,
  fallbackMessage: string,
): ChatMutationFailure {
  if (hasHttpStatus(error, 402)) {
    return {
      message:
        "クレジットが不足しています。アカウントメニューで無料クレジットの残量を確認できます。",
      tone: "warning",
    };
  }
  if (hasHttpStatus(error, 429)) {
    return {
      message: "現在、回答の生成が混み合っています。少し待ってからもう一度お試しください。",
      tone: "warning",
    };
  }
  if (hasHttpStatus(error, 503)) {
    return {
      message: "回答モデルを一時的に利用できません。少し待ってからもう一度お試しください。",
      tone: "warning",
    };
  }
  return { message: fallbackMessage, tone: "error" };
}
