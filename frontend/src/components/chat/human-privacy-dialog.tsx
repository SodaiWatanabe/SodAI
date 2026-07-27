"use client";

import { X } from "lucide-react";
import Image from "next/image";
import { useEffect, useId, useRef } from "react";

type HumanPrivacyDialogProps = {
  onClose: () => void;
};

export function HumanPrivacyDialog({ onClose }: HumanPrivacyDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
  }, []);

  function closeDialog() {
    dialogRef.current?.close();
  }

  return (
    <dialog
      ref={dialogRef}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="human-privacy-dialog m-auto w-[calc(100%-2rem)] max-w-[420px] overflow-hidden rounded-[28px] border border-[var(--divider)] bg-[var(--surface)] p-0 text-[var(--text)] shadow-[0_28px_80px_var(--dialog-shadow)] outline-none"
      onCancel={(event) => {
        event.preventDefault();
        closeDialog();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) closeDialog();
      }}
      onClose={onClose}
    >
      <div className="relative">
        <Image
          src="/images/human-warmth.webp"
          alt=""
          width={1280}
          height={488}
          className="h-auto w-full object-cover"
        />
        <button
          type="button"
          aria-label="Humanへの送信についてを閉じる"
          className="absolute right-3 top-3 grid size-9 place-items-center rounded-full border border-[var(--border)] bg-[var(--surface-translucent)] text-[var(--muted)] shadow-sm backdrop-blur-md transition-colors hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
          onClick={closeDialog}
        >
          <X aria-hidden="true" className="size-[18px]" />
        </button>
      </div>
      <div className="px-6 pb-6 pt-5 sm:px-7">
        <h2
          id={titleId}
          className="text-lg font-semibold tracking-[-0.02em]"
        >
          Humanへの送信
        </h2>
        <p
          id={descriptionId}
          className="mt-1.5 text-sm leading-6 text-[var(--muted)]"
        >
          プロンプトは第三者のユーザーに送信されます。個人情報と機密情報は含めないようにしてください。
        </p>
        <button
          type="button"
          autoFocus
          className="mt-6 h-11 w-full rounded-full bg-[var(--primary)] px-5 text-sm font-medium text-[var(--on-primary)] transition-colors hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
          onClick={closeDialog}
        >
          確認しました
        </button>
      </div>
    </dialog>
  );
}
