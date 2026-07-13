"use client";

import { ArrowLeft, X } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  type FormEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import {
  getAccountDestination,
  getInitialAuthStep,
  type AuthStep,
} from "@/components/auth/auth-flow";
import { IOSSpinner } from "@/components/ui/ios-spinner";
import {
  getCurrentAccount,
  setCurrentAccountDisplayName,
} from "@/lib/account/api";
import { authClient } from "@/lib/auth/client";

type AuthError = {
  code?: string;
  status?: number;
};

type AuthDialogProps = {
  accountUnavailable?: boolean;
  googleEnabled: boolean;
  initialError?: string;
  onClose: () => void;
  resumeProfile?: boolean;
};

const OTP_LENGTH = 6;
const RESEND_DELAY_SECONDS = 30;

const errorMessages: Record<string, string> = {
  INVALID_OTP: "コードが正しくありません。もう一度お試しください。",
  OTP_EXPIRED: "コードの有効期限が切れました。新しいコードをお試しください。",
  TOO_MANY_ATTEMPTS: "入力回数の上限に達しました。新しいコードをお試しください。",
  TOO_MANY_REQUESTS: "少し時間をおいて、もう一度お試しください。",
};

function getErrorMessage(error: AuthError | null | undefined, fallback: string) {
  if (error?.status === 429) return errorMessages.TOO_MANY_REQUESTS;
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
  accountUnavailable = false,
  googleEnabled,
  initialError,
  onClose,
  resumeProfile = false,
}: AuthDialogProps) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const emailInputRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(true);
  const otpInputRef = useRef<HTMLInputElement>(null);
  const profileInputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const errorId = useId();
  const [step, setStep] = useState<AuthStep>(() =>
    getInitialAuthStep({ accountUnavailable, resumeProfile }),
  );
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [pending, setPending] = useState(false);
  const [sessionEstablished, setSessionEstablished] = useState(
    accountUnavailable || resumeProfile,
  );
  const [resendSeconds, setResendSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | undefined>(
    initialError,
  );

  useEffect(() => {
    mountedRef.current = true;
    const dialog = dialogRef.current;
    if (!dialog) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (!dialog.open) dialog.showModal();

    return () => {
      mountedRef.current = false;
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    if (step === "email") emailInputRef.current?.focus();
    if (step === "otp") otpInputRef.current?.focus();
    if (step === "profile") profileInputRef.current?.focus();
  }, [step]);

  useEffect(() => {
    if (step !== "otp" || resendSeconds <= 0) return;
    const timer = window.setInterval(() => {
      setResendSeconds((seconds) => Math.max(0, seconds - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendSeconds, step]);

  function finishAuthentication() {
    dialogRef.current?.close();
    router.refresh();
  }

  function closeDialog() {
    if (pending) return;
    if (!sessionEstablished) {
      dialogRef.current?.close();
      return;
    }

    void discardIncompleteSession();
  }

  async function discardIncompleteSession() {
    setPending(true);
    setErrorMessage(undefined);
    try {
      const { error } = await authClient.signOut();
      if (!mountedRef.current) return;
      if (error) throw error;
      dialogRef.current?.close();
      router.refresh();
    } catch {
      if (!mountedRef.current) return;
      setErrorMessage("ログアウトできませんでした。もう一度お試しください。");
      setPending(false);
    }
  }

  async function sendOtp() {
    setPending(true);
    setErrorMessage(undefined);

    const normalizedEmail = email.trim().toLowerCase();
    const { error } = await authClient.emailOtp.sendVerificationOtp({
      email: normalizedEmail,
      type: "sign-in",
    });

    if (!mountedRef.current) return;
    setPending(false);
    if (error) {
      setErrorMessage(
        getErrorMessage(error, "ログインコードを送信できませんでした。"),
      );
      return;
    }

    setEmail(normalizedEmail);
    setOtp("");
    setResendSeconds(RESEND_DELAY_SECONDS);
    setStep("otp");
  }

  async function submitEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await sendOtp();
  }

  async function continueWithGoogle() {
    if (!googleEnabled) return;

    setPending(true);
    setErrorMessage(undefined);
    const { error } = await authClient.signIn.social({
      provider: "google",
      callbackURL: "/",
      errorCallbackURL: "/?authError=google",
    });

    if (!mountedRef.current) return;
    if (error) {
      setErrorMessage(
        getErrorMessage(error, "Googleで続行できませんでした。"),
      );
      setPending(false);
    }
  }

  async function resolveAccount() {
    setStep("resolving");
    setPending(true);
    setErrorMessage(undefined);

    try {
      const account = await getCurrentAccount();
      if (!mountedRef.current) return;
      const destination = getAccountDestination(account);
      if (destination === "blocked") {
        setStep("blocked");
        return;
      }
      if (destination === "authenticated") {
        finishAuthentication();
        return;
      }
      setStep("profile");
    } catch {
      if (!mountedRef.current) return;
      setErrorMessage("アカウントを準備できませんでした。もう一度お試しください。");
    } finally {
      if (mountedRef.current) setPending(false);
    }
  }

  async function submitOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrorMessage(undefined);

    const { error } = await authClient.signIn.emailOtp({ email, otp });
    if (!mountedRef.current) return;
    if (error) {
      setErrorMessage(
        getErrorMessage(error, "ログインコードを確認できませんでした。"),
      );
      setPending(false);
      return;
    }

    setSessionEstablished(true);
    await resolveAccount();
  }

  async function submitProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrorMessage(undefined);

    const formData = new FormData(event.currentTarget);
    const displayName = String(formData.get("displayName")).trim();
    try {
      await setCurrentAccountDisplayName(displayName);
      if (!mountedRef.current) return;
      finishAuthentication();
    } catch {
      if (!mountedRef.current) return;
      setErrorMessage("表示名を保存できませんでした。もう一度お試しください。");
      setPending(false);
    }
  }

  const description =
    step === "blocked"
      ? "このアカウントは現在利用できません。"
      : step === "email"
      ? "ログインして、チャットを保存したり、高度なモデルにアクセスしたりしましょう。"
      : step === "otp"
        ? `${email} に送信したコードを入力してください。`
        : step === "profile"
          ? "最後に、SodAIで使う名前を設定してください。"
          : "SodAIアカウントを準備しています。";

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      className="auth-dialog m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-[420px] overflow-y-auto overscroll-contain rounded-[28px] border border-[var(--divider)] bg-[var(--surface)] p-0 text-[var(--text)] shadow-[0_28px_80px_var(--dialog-shadow)]"
      onCancel={(event) => {
        event.preventDefault();
        closeDialog();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) closeDialog();
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

        {step === "otp" ? (
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
            className="text-2xl font-semibold tracking-[-0.035em]"
          >
            ログインまたは新規登録
          </h2>
          <p
            id={descriptionId}
            className="mt-2 text-sm leading-5 text-[var(--muted)]"
          >
            {description}
          </p>
        </header>

        {errorMessage ? (
          <p
            id={errorId}
            role="alert"
            className="mt-5 rounded-2xl bg-[var(--danger-background)] px-4 py-2.5 text-center text-xs leading-5 text-[var(--danger-text)]"
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
                googleEnabled ? undefined : "Google OAuthの設定後に利用できます"
              }
            >
              <GoogleMark />
              Googleで続行
            </button>
            {!googleEnabled ? (
              <span id={`${titleId}-google-disabled`} className="sr-only">
                Google OAuthの設定後に利用できます
              </span>
            ) : null}

            <div className="my-5 flex items-center gap-3" aria-hidden="true">
              <span className="h-px flex-1 bg-[var(--divider)]" />
              <span className="text-xs text-[var(--muted)]">または</span>
              <span className="h-px flex-1 bg-[var(--divider)]" />
            </div>

            <form onSubmit={submitEmail}>
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
                aria-invalid={Boolean(errorMessage)}
                aria-errormessage={errorMessage ? errorId : undefined}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="メールアドレス"
                className="h-12 w-full rounded-full border border-[var(--border)] bg-transparent px-4 text-sm outline-none placeholder:text-[var(--muted)]"
              />
              <button
                type="submit"
                disabled={pending}
                className="mt-3 h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)] disabled:cursor-wait disabled:opacity-50"
              >
                {pending ? "送信中…" : "続行"}
              </button>
            </form>
          </div>
        ) : null}

        {step === "otp" ? (
          <form className="mt-7" onSubmit={submitOtp}>
            <label htmlFor={`${titleId}-otp`} className="sr-only">
              ログインコード
            </label>
            <input
              ref={otpInputRef}
              id={`${titleId}-otp`}
              type="text"
              autoComplete="one-time-code"
              inputMode="numeric"
              pattern="[0-9]*"
              minLength={OTP_LENGTH}
              maxLength={OTP_LENGTH}
              required
              aria-invalid={Boolean(errorMessage)}
              aria-errormessage={errorMessage ? errorId : undefined}
              value={otp}
              onChange={(event) => {
                setOtp(event.target.value.replace(/\D/g, "").slice(0, OTP_LENGTH));
              }}
              placeholder="6桁のコード"
              className="h-12 w-full rounded-full border border-[var(--border)] bg-transparent px-4 text-center text-lg tracking-[0.18em] outline-none placeholder:text-sm placeholder:tracking-normal placeholder:text-[var(--muted)]"
            />
            <button
              type="submit"
              disabled={pending || otp.length !== OTP_LENGTH}
              className="mt-3 h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)] disabled:cursor-wait disabled:opacity-50"
            >
              {pending ? "確認中…" : "ログイン"}
            </button>
            <button
              type="button"
              disabled={pending || resendSeconds > 0}
              className="mt-3 h-9 w-full text-xs font-medium text-[var(--muted)] transition-colors hover:text-[var(--text)] disabled:cursor-default disabled:opacity-60"
              onClick={sendOtp}
            >
              {resendSeconds > 0
                ? `${resendSeconds}秒後に再送信`
                : "コードを再送信"}
            </button>
          </form>
        ) : null}

        {step === "resolving" ? (
          <div className="mt-8 flex min-h-28 flex-col items-center justify-center gap-5">
            {pending ? <IOSSpinner label="アカウントを準備中" /> : null}
            {!pending ? (
              <button
                type="button"
                className="h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
                onClick={resolveAccount}
              >
                再試行
              </button>
            ) : null}
          </div>
        ) : null}

        {step === "blocked" ? (
          <div className="mt-7">
            <button
              type="button"
              disabled={pending}
              className="h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:cursor-wait disabled:opacity-50"
              onClick={discardIncompleteSession}
            >
              {pending ? "ログアウト中…" : "ログアウト"}
            </button>
          </div>
        ) : null}

        {step === "profile" ? (
          <form className="mt-7" onSubmit={submitProfile}>
            <label htmlFor={`${titleId}-display-name`} className="sr-only">
              表示名
            </label>
            <input
              ref={profileInputRef}
              id={`${titleId}-display-name`}
              name="displayName"
              type="text"
              autoComplete="name"
              required
              aria-invalid={Boolean(errorMessage)}
              aria-errormessage={errorMessage ? errorId : undefined}
              minLength={1}
              maxLength={200}
              placeholder="表示名"
              className="h-12 w-full rounded-full border border-[var(--border)] bg-transparent px-4 text-sm outline-none placeholder:text-[var(--muted)]"
            />
            <button
              type="submit"
              disabled={pending}
              className="mt-3 h-12 w-full rounded-full bg-[var(--primary)] text-sm font-medium text-[var(--on-primary)] transition hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)] disabled:cursor-wait disabled:opacity-50"
            >
              {pending ? "保存中…" : "はじめる"}
            </button>
          </form>
        ) : null}
      </div>
    </dialog>
  );
}
