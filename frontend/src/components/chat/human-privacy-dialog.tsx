"use client";

import { X } from "lucide-react";
import Image from "next/image";
import { useId, useRef } from "react";

import {
  ModalDialog,
  type ModalDialogHandle,
} from "@/components/ui/modal-dialog";

type HumanPrivacyDialogProps = {
  onClose: () => void;
  scope: "message" | "thread";
};

export function HumanPrivacyDialog({ onClose, scope }: HumanPrivacyDialogProps) {
  const dialogRef = useRef<ModalDialogHandle>(null);
  const titleId = useId();
  const descriptionId = useId();
  const title = scope === "thread" ? "会話が共有されます" : "Humanへの送信";
  const description =
    scope === "thread"
      ? "このスレッド内の全メッセージが第三者のユーザーに送信されます。個人情報と機密情報は含めないようにしてください。"
      : "プロンプトは第三者のユーザーに送信されます。個人情報と機密情報は含めないようにしてください。";

  function closeDialog() {
    dialogRef.current?.close();
  }

  return (
    <ModalDialog
      ref={dialogRef}
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="w-[calc(100%-2rem)] max-w-[420px] overflow-hidden"
      initialFocus="dialog"
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
          aria-label={`${title}を閉じる`}
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
          {title}
        </h2>
        <p
          id={descriptionId}
          className="mt-1.5 text-sm leading-6 text-[var(--muted)]"
        >
          {description}
        </p>
        <button
          type="button"
          className="mt-6 h-11 w-full rounded-full bg-[var(--primary)] px-5 text-sm font-medium text-[var(--on-primary)] transition-colors hover:bg-[var(--primary-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
          onClick={closeDialog}
        >
          確認しました
        </button>
      </div>
    </ModalDialog>
  );
}
