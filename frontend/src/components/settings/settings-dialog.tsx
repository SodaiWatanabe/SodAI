"use client";

import { ChevronLeft, X } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect, useId, useRef } from "react";

import { useChatAuth } from "@/components/chat/chat-auth-context";
import {
  SettingsIndex,
  SettingsNavigation,
  SettingsRouteLink,
  type SettingsSection,
} from "@/components/settings/settings-navigation";

function getSection(pathname: string): SettingsSection {
  if (pathname.endsWith("/account")) return "account";
  if (pathname.endsWith("/credits")) return "credits";
  if (pathname.endsWith("/keyboard")) return "keyboard";
  if (pathname.endsWith("/general")) return "general";
  return "root";
}

const sectionTitles: Record<SettingsSection, string> = {
  account: "アカウント",
  credits: "クレジット",
  general: "一般",
  keyboard: "キーボード",
  root: "一般",
};

export function SettingsDialog({
  accountPanel,
  closeMode,
  creditPanel,
  generalPanel,
  keyboardPanel,
}: {
  accountPanel: ReactNode;
  closeMode: "back" | "home";
  creditPanel: ReactNode;
  generalPanel: ReactNode;
  keyboardPanel: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { settingsAccessible } = useChatAuth();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const section = getSection(pathname);
  const panel =
    section === "account"
      ? accountPanel
      : section === "credits"
        ? creditPanel
        : section === "keyboard"
          ? keyboardPanel
          : generalPanel;

  useEffect(() => {
    if (!settingsAccessible) {
      router.replace("/");
      return;
    }

    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) {
      dialog.showModal();
      dialog.focus({ preventScroll: true });
    }

    return () => {
      if (dialog.open) dialog.close();
    };
  }, [router, settingsAccessible]);

  function closeDialog() {
    dialogRef.current?.close();
    if (closeMode === "home") {
      router.replace("/");
    } else {
      router.back();
    }
  }

  if (!settingsAccessible) return null;

  return (
    <dialog
      ref={dialogRef}
      tabIndex={-1}
      aria-labelledby={titleId}
      className="settings-dialog m-auto h-[calc(100dvh-1rem)] w-[calc(100%-1rem)] max-w-[620px] overflow-hidden rounded-[28px] border border-[var(--divider)] bg-[var(--surface)] p-0 text-[var(--text)] shadow-[0_28px_80px_var(--dialog-shadow)] outline-none sm:h-[min(520px,calc(100dvh-2rem))] sm:w-[calc(100%-2rem)]"
      onCancel={(event) => {
        event.preventDefault();
        closeDialog();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) closeDialog();
      }}
    >
      <div className="flex h-full min-h-0 pb-[env(safe-area-inset-bottom)] sm:pb-0">
        <aside className="hidden w-44 shrink-0 border-r border-[var(--separator)] bg-[var(--sidebar)] px-1.5 pt-3 sm:block">
          <SettingsNavigation section={section} />
        </aside>

        <section className="flex min-w-0 flex-1 flex-col">
          <header className="relative flex h-14 shrink-0 items-center border-b border-[var(--separator)] px-14 sm:px-6">
            {section !== "root" ? (
              <SettingsRouteLink
                href="/settings"
                aria-label="設定項目一覧へ戻る"
                className="absolute left-2.5 grid size-10 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] sm:hidden"
              >
                <ChevronLeft aria-hidden="true" className="size-5" />
              </SettingsRouteLink>
            ) : null}

            <h1
              id={titleId}
              className="mx-auto text-[15px] font-semibold tracking-[-0.015em] sm:ml-0 sm:mr-auto"
            >
              {section === "root" ? (
                <>
                  <span className="sm:hidden">設定</span>
                  <span className="hidden sm:inline">一般</span>
                </>
              ) : (
                sectionTitles[section]
              )}
            </h1>

            <button
              type="button"
              aria-label="設定を閉じる"
              className="absolute right-2.5 grid size-10 place-items-center rounded-full text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] sm:right-3"
              onClick={closeDialog}
            >
              <X aria-hidden="true" className="size-[18px]" />
            </button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {section === "root" ? (
              <>
                <div className="sm:hidden">
                  <SettingsIndex />
                </div>
                <div className="hidden sm:block">{generalPanel}</div>
              </>
            ) : (
              panel
            )}
          </div>
        </section>
      </div>
    </dialog>
  );
}
