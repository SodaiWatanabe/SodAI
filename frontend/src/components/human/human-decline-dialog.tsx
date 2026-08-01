"use client";

import { useEffect, useId, useRef } from "react";

type HumanDeclineDialogProps = {
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

export function HumanDeclineDialog({
  busy,
  onClose,
  onConfirm,
}: HumanDeclineDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  function closeDialog() {
    if (!busy) dialogRef.current?.close();
  }

  return (
    <dialog
      ref={dialogRef}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="human-decline-dialog m-auto w-[calc(100%-2rem)] max-w-[420px] overflow-hidden rounded-[28px] border border-[var(--divider)] bg-[var(--surface)] p-0 text-[var(--text)] shadow-[0_28px_80px_var(--dialog-shadow)] outline-none"
      onCancel={(event) => {
        event.preventDefault();
        closeDialog();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) closeDialog();
      }}
      onClose={onClose}
    >
      <div className="px-6 pb-6 pt-6 sm:px-7">
        <h2 id={titleId} className="text-lg font-semibold tracking-[-0.02em]">
          回答を辞退しますか？
        </h2>
        <p
          id={descriptionId}
          className="mt-2 text-sm leading-6 text-[var(--muted)]"
        >
          入力中の回答は破棄され、この依頼は別のHumanへ引き継がれます。
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            autoFocus
            disabled={busy}
            className="h-11 rounded-full px-5 text-sm font-medium text-[var(--muted)] transition-colors hover:bg-[var(--hover)] disabled:opacity-50"
            onClick={closeDialog}
          >
            キャンセル
          </button>
          <button
            type="button"
            disabled={busy}
            className="h-11 rounded-full bg-[var(--danger-text)] px-5 text-sm font-medium text-[var(--canvas)] transition-opacity hover:opacity-90 disabled:opacity-50"
            onClick={onConfirm}
          >
            {busy ? "辞退中…" : "辞退する"}
          </button>
        </div>
      </div>
    </dialog>
  );
}
