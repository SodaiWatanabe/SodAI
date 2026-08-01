"use client";

import { useId, useRef } from "react";

import {
  ModalDialog,
  type ModalDialogHandle,
} from "@/components/ui/modal-dialog";

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
  const dialogRef = useRef<ModalDialogHandle>(null);
  const titleId = useId();
  const descriptionId = useId();

  function closeDialog() {
    if (!busy) dialogRef.current?.close();
  }

  return (
    <ModalDialog
      ref={dialogRef}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="w-[calc(100%-2rem)] max-w-[420px] overflow-hidden"
      dismissible={!busy}
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
    </ModalDialog>
  );
}
