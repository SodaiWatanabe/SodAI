export class ChatApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
  }
}

export function isInsufficientCreditsError(error: unknown): boolean {
  return error instanceof ChatApiError && error.status === 402;
}

export const INSUFFICIENT_CREDITS_MESSAGE =
  "クレジットが不足しています。アカウントメニューで無料クレジットの残量を確認できます。";
