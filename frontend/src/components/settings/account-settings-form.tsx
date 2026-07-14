"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { setCurrentAccountDisplayName } from "@/lib/account/api";

const DISPLAY_NAME_MAX_LENGTH = 200;

type AccountSettingsFormProps = {
  initialDisplayName: string;
};

export function AccountSettingsForm({
  initialDisplayName,
}: AccountSettingsFormProps) {
  const router = useRouter();
  const inputId = useId();
  const labelId = useId();
  const descriptionId = useId();
  const errorId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelBlurSaveRef = useRef(false);
  const [displayName, setDisplayName] = useState(initialDisplayName);
  const [savedDisplayName, setSavedDisplayName] = useState(initialDisplayName);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const normalizedDisplayName = displayName.trim();
  const valid =
    normalizedDisplayName.length > 0 &&
    normalizedDisplayName.length <= DISPLAY_NAME_MAX_LENGTH;
  const changed = normalizedDisplayName !== savedDisplayName;

  useEffect(() => {
    if (!editing || saving) return;
    inputRef.current?.focus({ preventScroll: true });
    inputRef.current?.select();
  }, [editing, saving]);

  async function saveDisplayName() {
    if (saving) return;
    if (!valid) {
      setError("表示名を入力してください。");
      return;
    }
    if (!changed) {
      setDisplayName(savedDisplayName);
      setEditing(false);
      return;
    }

    setError(null);
    setSaving(true);
    try {
      const account = await setCurrentAccountDisplayName(normalizedDisplayName);
      const savedName = account.display_name ?? normalizedDisplayName;
      setDisplayName(savedName);
      setSavedDisplayName(savedName);
      setEditing(false);
      router.refresh();
    } catch {
      setError("表示名を保存できませんでした。時間をおいて、もう一度お試しください。");
      setEditing(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      aria-busy={saving}
      autoComplete="off"
      onSubmit={(event) => {
        event.preventDefault();
        inputRef.current?.blur();
      }}
    >
      <p id={descriptionId} className="sr-only">
        サイドバーなど、SodAI内であなたを表す名前です。
      </p>
      <div className="flex min-h-14 items-center gap-4 rounded-xl">
        <span
          id={labelId}
          className="min-w-0 flex-1 text-sm font-medium text-[var(--text)]"
        >
          表示名
        </span>
        {editing ? (
          <span className="relative h-9 min-w-9 max-w-[62%] overflow-hidden">
            <span
              aria-hidden="true"
              className="invisible block whitespace-pre px-2.5 text-sm font-medium"
            >
              {displayName || " "}
            </span>
            <input
              ref={inputRef}
              id={inputId}
              name="displayName"
              type="text"
              required
              autoComplete="off"
              maxLength={DISPLAY_NAME_MAX_LENGTH}
              disabled={saving}
              aria-labelledby={labelId}
              aria-describedby={
                error ? `${descriptionId} ${errorId}` : descriptionId
              }
              aria-invalid={Boolean(error)}
              className="absolute inset-0 h-9 w-full rounded-xl bg-[var(--field)] px-2.5 text-sm font-medium text-[var(--text)] outline-none placeholder:text-[var(--muted)] disabled:cursor-wait disabled:opacity-60"
              value={displayName}
              onBlur={() => {
                if (cancelBlurSaveRef.current) {
                  cancelBlurSaveRef.current = false;
                  return;
                }
                void saveDisplayName();
              }}
              onChange={(event) => {
                setDisplayName(event.target.value);
                if (error) setError(null);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  event.currentTarget.blur();
                }
                if (event.key === "Escape") {
                  event.preventDefault();
                  cancelBlurSaveRef.current = true;
                  setDisplayName(savedDisplayName);
                  setError(null);
                  event.currentTarget.blur();
                  setEditing(false);
                }
              }}
            />
          </span>
        ) : (
          <button
            type="button"
            aria-label={`表示名を編集: ${savedDisplayName}`}
            className="h-9 max-w-[62%] truncate rounded-xl px-2.5 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)]"
            onClick={() => {
              setEditing(true);
            }}
          >
            {savedDisplayName}
          </button>
        )}
      </div>
      {error ? (
        <p
          id={errorId}
          role="alert"
          className="mt-2 text-xs leading-5 text-[var(--danger-text)]"
        >
          {error}
        </p>
      ) : null}
    </form>
  );
}
