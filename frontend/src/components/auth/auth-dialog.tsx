"use client";

import { ArrowLeft, Check, X } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  type FormEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import { authClient } from "@/lib/auth/client";

export type AuthMode = "login" | "register";

type AuthStep = "email" | "credentials" | "complete";

type AuthError = {
  code?: string;
  status?: number;
};

type AuthDialogProps = {
  googleEnabled: boolean;
  initialError?: string;
  mode: AuthMode;
  onClose: () => void;
};

const errorMessages: Record<string, string> = {
  EMAIL_NOT_VERIFIED: "確認メールをご確認ください。",
  INVALID_EMAIL_OR_PASSWORD: "メールアドレスまたはパスワードが正しくありません。",
  INVALID_PASSWORD: "メールアドレスまたはパスワードが正しくありません。",
  TOO_MANY_REQUESTS: "少し時間をおいて、もう一度お試しください。",
  USER_ALREADY_EXISTS:
    "登録を受け付けました。利用可能な場合は確認メールが届きます。",
};

function getErrorMessage(error: AuthError | null | undefined, fallback: string) {
  if (error?.status === 429) {
    return errorMessages.TOO_MANY_REQUESTS;
  }

  return (error?.code && errorMessages[error.code]) || fallback;
}

function GoogleMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-[18px]">
      <path
        fill="#4285F4"
        d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.87h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.89-1.74 2.98-4.31 2.98-7.35Z"
      />
      <path
        fill="#34A853"
        d="M12 22c2.7 0 4.96-.9 6.62-2.42l-3.24-2.51c-.89.6-2.04.95-3.38.95-2.61 0-4.81-1.76-5.6-4.12H3.06v2.59A10 10 0 0 0 12 22Z"
      />
      <path
        fill="#FBBC05"
        d="M6.4 13.9A6 6 0 0 1 6.09 12c0-.66.11-1.3.31-1.9V7.51H3.06A10 10 0 0 0 2 12c0 1.61.39 3.14 1.06 4.49L6.4 13.9Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.98c1.47 0 2.79.5 3.82 1.49l2.87-2.87C16.96 2.99 14.7 2 12 2a10 10 0 0 0-8.94 5.51L6.4 10.1c.79-2.36 3-4.12 5.6-4.12Z"
      />
    </svg>
  );
}

export function AuthDialog({
  googleEnabled,
  initialError,
  mode,
  onClose,
}: AuthDialogProps) {
  const router = useRouter();
  const completeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const emailInputRef = useRef<HTMLInputElement>(null);
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const [step, setStep] = useState<AuthStep>("email");
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | undefined>(
    initialError,
  );

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (!dialog.open) {
      dialog.showModal();
    }

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    if (step === "email") {
      emailInputRef.current?.focus();
    } else if (step === "credentials") {
      passwordInputRef.current?.focus();
    } else {
      completeButtonRef.current?.focus();
    }
  }, [step]);

  function closeDialog() {
    if (!pending) {
      dialogRef.current?.close();
    }
  }

  function continueWithEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(undefined);
    setStep("credentials");
  }

  async function continueWithGoogle() {
    if (!googleEnabled) {
      return;
    }

    setPending(true);
    setErrorMessage(undefined);

    const { error } = await authClient.signIn.social({
      provider: "google",
      callbackURL: "/",
      errorCallbackURL: "/?authError=google",
    });

    if (error) {
      setErrorMessage(
        getErrorMessage(error, "Googleで続行できませんでした。"),
      );
      setPending(false);
    }
  }

  async function submitCredentials(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrorMessage(undefined);

    const formData = new FormData(event.currentTarget);
    const password = String(formData.get("password"));

    if (mode === "login") {
      const { error } = await authClient.signIn.email({
        email,
        password,
        callbackURL: "/",
      });

      if (error) {
        setErrorMessage(
          getErrorMessage(error, "ログインできませんでした。"),
        );
        setPending(false);
        return;
      }

      dialogRef.current?.close();
      router.refresh();
      return;
    }

    const { error } = await authClient.signUp.email({
      name: String(formData.get("name")),
      email,
      password,
      callbackURL: "/",
    });

    if (error) {
      setErrorMessage(
        getErrorMessage(error, "アカウントを作成できませんでした。"),
      );
      setPending(false);
      return;
    }

    setPending(false);
    setStep("complete");
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className="auth-dialog m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-[420px] overflow-y-auto overscroll-contain rounded-[28px] border border-[var(--divider)] bg-[var(--surface)] p-0 text-[var(--text)] shadow-[0_28px_80px_var(--dialog-shadow)]"
      onCancel={(event) => {
        event.preventDefault();
        closeDialog();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) {
          closeDialog();
        }
      }}
      onClose={onClose}
    >
      <div className="relative px-6 pb-7 pt-6 sm:px-8 sm:pb-8 sm:pt-7">
        <button
          type="button"
          aria-label="閉じる"
          className="absolute right-4 top-4 grid size-9 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:opacity-40"
          disabled={pending}
          onClick={closeDialog}
        >
          <X className="size-[18px]" />
        </button>

        {step === "complete" ? (
          <div role="status" className="pb-1 pt-5 text-center">
            <div className="mx-auto mb-5 grid size-12 place-items-center rounded-full bg-[var(--primary)] text-[var(--on-primary)]">
              <Check className="size-6" />
            </div>
            <h2 id={titleId} className="text-[22px] font-semibold tracking-[-0.03em]">
              メールを確認してください
            </h2>
            <p className="mx-auto mt-3 max-w-[310px] text-sm leading-6 text-[var(--muted)]">
              <span className="font-medium text-[var(--text)]">{email}</span>
              に確認リンクを送りました。
            </p>
            <button
              ref={completeButtonRef}
              type="button"
              className="mt-7 h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
              onClick={closeDialog}
            >
              閉じる
            </button>
          </div>
        ) : (
          <>
            {step === "credentials" ? (
              <button
                type="button"
                aria-label="メールアドレス入力へ戻る"
                className="absolute left-4 top-4 grid size-9 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:opacity-40"
                disabled={pending}
                onClick={() => {
                  setErrorMessage(undefined);
                  setStep("email");
                }}
              >
                <ArrowLeft className="size-5" />
              </button>
            ) : null}

            <header className="px-8 pt-5 text-center">
              <h2
                id={titleId}
                className="text-[24px] font-semibold tracking-[-0.035em]"
              >
                {step === "email"
                  ? mode === "login"
                    ? "SodAIにログイン"
                    : "アカウントを作成"
                  : mode === "login"
                    ? "パスワードを入力"
                    : "プロフィールを設定"}
              </h2>
              <p className="mt-2 text-sm leading-5 text-[var(--muted)]">
                {step === "email"
                  ? "ログインしてチャットを保存したり、より高度なモデルを利用しましょう。"
                  : email}
              </p>
            </header>

            {errorMessage ? (
              <p
                role="alert"
                className="mt-5 rounded-full bg-[var(--danger-background)] px-4 py-2.5 text-center text-xs leading-5 text-[var(--danger-text)]"
              >
                {errorMessage}
              </p>
            ) : null}

            {step === "email" ? (
              <div className="mt-7">
                <button
                  type="button"
                  aria-describedby={
                    googleEnabled ? undefined : `${titleId}-google-disabled`
                  }
                  className="flex h-12 w-full items-center justify-center gap-2.5 rounded-full border border-[var(--border)] bg-[var(--surface)] text-sm font-medium transition hover:bg-[var(--hover-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!googleEnabled || pending}
                  onClick={continueWithGoogle}
                  title={
                    googleEnabled
                      ? undefined
                      : "Google OAuthの設定後に利用できます"
                  }
                >
                  <GoogleMark />
                  {pending ? "Googleへ接続中…" : "Googleで続行"}
                </button>
                {!googleEnabled ? (
                  <span id={`${titleId}-google-disabled`} className="sr-only">
                    Google OAuthの設定後に利用できます
                  </span>
                ) : null}

                <div className="my-5 flex items-center gap-3" aria-hidden="true">
                  <span className="h-px flex-1 bg-[var(--divider)]" />
                  <span className="text-[11px] text-[var(--muted)]">または</span>
                  <span className="h-px flex-1 bg-[var(--divider)]" />
                </div>

                <form onSubmit={continueWithEmail}>
                  <label htmlFor={`${titleId}-email`} className="sr-only">
                    メールアドレス
                  </label>
                  <input
                    ref={emailInputRef}
                    id={`${titleId}-email`}
                    type="email"
                    autoComplete="email"
                    inputMode="email"
                    required
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="メールアドレス"
                    className="h-12 w-full rounded-full border border-[var(--border)] bg-transparent px-4 text-[15px] outline-none placeholder:text-[var(--muted)]"
                  />
                  <button
                    type="submit"
                    className="mt-3 h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
                  >
                    続行
                  </button>
                </form>
              </div>
            ) : (
              <form className="mt-7" onSubmit={submitCredentials}>
                {mode === "register" ? (
                  <div className="mb-3">
                    <label htmlFor={`${titleId}-name`} className="sr-only">
                      表示名
                    </label>
                    <input
                      id={`${titleId}-name`}
                      name="name"
                      type="text"
                      autoComplete="name"
                      required
                      minLength={1}
                      maxLength={80}
                      disabled={pending}
                      placeholder="表示名"
                      className="h-12 w-full rounded-full border border-[var(--border)] bg-[var(--field)] px-4 text-[15px] outline-none placeholder:text-[var(--muted)] disabled:opacity-50"
                    />
                  </div>
                ) : null}

                <label htmlFor={`${titleId}-password`} className="sr-only">
                  パスワード
                </label>
                <input
                  ref={passwordInputRef}
                  id={`${titleId}-password`}
                  name="password"
                  type="password"
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  required
                  minLength={12}
                  maxLength={128}
                  disabled={pending}
                  placeholder="パスワード"
                  className="h-12 w-full rounded-full border border-[var(--border)] bg-[var(--field)] px-4 text-[15px] outline-none placeholder:text-[var(--muted)] disabled:opacity-50"
                />
                {mode === "register" ? (
                  <p className="mt-2 px-1 text-xs text-[var(--muted)]">
                    12文字以上で設定してください
                  </p>
                ) : null}
                <button
                  type="submit"
                  disabled={pending}
                  className="mt-4 h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)] disabled:cursor-wait disabled:opacity-50"
                >
                  {pending
                    ? "処理中…"
                    : mode === "login"
                      ? "ログイン"
                      : "アカウントを作成"}
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </dialog>
  );
}
