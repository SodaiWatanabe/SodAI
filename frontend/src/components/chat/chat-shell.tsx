"use client";

import { useRouter } from "next/navigation";
import { type ChangeEvent, useEffect, useRef, useState } from "react";

import { AuthDialog, type AuthMode } from "@/components/auth/auth-dialog";
import {
  CloseIcon,
  LoginIcon,
  LogoutIcon,
  MenuIcon,
  PanelCloseIcon,
  PanelOpenIcon,
  PlusIcon,
  UserPlusIcon,
} from "@/components/ui/icons";
import { authClient } from "@/lib/auth/client";

type ChatShellProps = {
  googleAuthEnabled: boolean;
  initialGoogleAuthError: boolean;
  initialUser: SidebarUser | null;
};

type SidebarUser = {
  email: string;
  name: string;
};

type SidebarContentProps = {
  autoFocusClose?: boolean;
  compact?: boolean;
  onClose: () => void;
  onCreateAccount: () => void;
  onLogin: () => void;
  onNewChat: () => void;
  onSignOut: () => void;
  signingOut: boolean;
  user: SidebarUser | null;
};

function SidebarContent({
  autoFocusClose = false,
  compact = false,
  onClose,
  onCreateAccount,
  onLogin,
  onNewChat,
  onSignOut,
  signingOut,
  user,
}: SidebarContentProps) {
  const labelClass = compact ? "hidden" : "opacity-100";
  const buttonLayout = compact ? "lg:justify-center lg:px-0" : "";

  return (
    <>
      <div className="flex h-16 shrink-0 items-center justify-end px-4">
        <button
          type="button"
          aria-label={compact ? "サイドバーを開く" : "サイドバーを閉じる"}
          aria-expanded={!compact}
          className="hidden size-9 place-items-center rounded-xl text-[#6e6e73] transition-colors hover:bg-black/[0.05] hover:text-[#1d1d1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] lg:grid"
          onClick={onClose}
        >
          {compact ? (
            <PanelOpenIcon className="size-5" />
          ) : (
            <PanelCloseIcon className="size-5" />
          )}
        </button>
        <button
          type="button"
          aria-label="サイドバーを閉じる"
          autoFocus={autoFocusClose}
          className="grid size-9 place-items-center rounded-xl text-[#6e6e73] transition-colors hover:bg-black/[0.05] hover:text-[#1d1d1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] lg:hidden"
          onClick={onClose}
        >
          <CloseIcon className="size-5" />
        </button>
      </div>

      <nav className="px-3" aria-label="チャット">
        <button
          type="button"
          title="新しいチャット"
          className={`flex h-11 w-full items-center gap-3 rounded-xl px-3 text-left text-sm font-medium text-[#1d1d1f] transition-colors hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] ${buttonLayout}`}
          onClick={onNewChat}
        >
          <PlusIcon className="size-[19px] shrink-0" />
          <span className={`whitespace-nowrap transition-opacity ${labelClass}`}>
            新しいチャット
          </span>
        </button>
      </nav>

      <div className="flex-1" />

      <div className="space-y-2 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        {user ? (
          <div
            className={`flex min-h-12 items-center gap-3 rounded-2xl px-2 ${
              compact ? "lg:justify-center" : ""
            }`}
          >
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-[#1d1d1f] text-xs font-semibold text-white">
              {(user.name || user.email).slice(0, 1).toUpperCase()}
            </span>
            <span className={`min-w-0 flex-1 transition-opacity ${labelClass}`}>
              <span className="block truncate text-xs font-medium text-[#1d1d1f]">
                {user.name || "SodAIユーザー"}
              </span>
              <span className="block truncate text-[11px] text-[#6e6e73]">
                {user.email}
              </span>
            </span>
            <button
              type="button"
              title="ログアウト"
              aria-label="ログアウト"
              disabled={signingOut}
              className={`grid size-8 shrink-0 place-items-center rounded-xl text-[#6e6e73] transition hover:bg-black/[0.05] hover:text-[#1d1d1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] disabled:opacity-40 ${
                compact ? "lg:hidden" : ""
              }`}
              onClick={onSignOut}
            >
              <LogoutIcon className="size-[17px]" />
            </button>
          </div>
        ) : (
          <>
            <button
              type="button"
              title="ログイン"
              className={`flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm font-medium text-[#1d1d1f] transition-colors hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] ${buttonLayout}`}
              onClick={onLogin}
            >
              <LoginIcon className="size-[19px] shrink-0" />
              <span className={`whitespace-nowrap transition-opacity ${labelClass}`}>
                ログイン
              </span>
            </button>
            <button
              type="button"
              title="アカウントを作成"
              className={`flex h-11 w-full items-center gap-3 rounded-xl bg-[#1d1d1f] px-3 text-sm font-medium text-white transition-colors hover:bg-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] focus-visible:ring-offset-2 focus-visible:ring-offset-[#f5f5f7] ${buttonLayout}`}
              onClick={onCreateAccount}
            >
              <UserPlusIcon className="size-[19px] shrink-0" />
              <span className={`whitespace-nowrap transition-opacity ${labelClass}`}>
                アカウントを作成
              </span>
            </button>
          </>
        )}
      </div>
    </>
  );
}

export function ChatShell({
  googleAuthEnabled,
  initialGoogleAuthError,
  initialUser,
}: ChatShellProps) {
  const router = useRouter();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileSidebarRef = useRef<HTMLElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode | undefined>(
    initialGoogleAuthError ? "login" : undefined,
  );
  const [googleAuthError, setGoogleAuthError] = useState(
    initialGoogleAuthError,
  );
  const [message, setMessage] = useState("");
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    if (initialGoogleAuthError) {
      router.replace("/", { scroll: false });
    }
  }, [initialGoogleAuthError, router]);

  useEffect(() => {
    if (!mobileSidebarOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      const sidebar = mobileSidebarRef.current;
      if (!sidebar) {
        return;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        setMobileSidebarOpen(false);
        requestAnimationFrame(() => menuButtonRef.current?.focus());
        return;
      }

      if (event.key !== "Tab") {
        return;
      }

      const focusableElements = Array.from(
        sidebar.querySelectorAll<HTMLButtonElement>("button:not([disabled])"),
      ).filter((element) => element.getClientRects().length > 0);
      const firstElement = focusableElements.at(0);
      const lastElement = focusableElements.at(-1);

      if (!firstElement || !lastElement) {
        return;
      }

      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileSidebarOpen]);

  function startNewChat() {
    setMessage("");
    setMobileSidebarOpen(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.focus();
    }
  }

  function openAuth(mode: AuthMode) {
    setMobileSidebarOpen(false);
    setGoogleAuthError(false);
    setAuthMode(mode);
  }

  function closeMobileSidebar() {
    setMobileSidebarOpen(false);
    requestAnimationFrame(() => menuButtonRef.current?.focus());
  }

  async function signOut() {
    setSigningOut(true);
    await authClient.signOut();
    setSigningOut(false);
    setMobileSidebarOpen(false);
    router.refresh();
  }

  function updateMessage(event: ChangeEvent<HTMLTextAreaElement>) {
    setMessage(event.target.value);
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 160)}px`;
  }

  const sidebarProps = {
    onCreateAccount: () => openAuth("register"),
    onLogin: () => openAuth("login"),
    onNewChat: startNewChat,
    onSignOut: signOut,
    signingOut,
    user: initialUser,
  };

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-white">
      <aside
        aria-label="チャットサイドバー"
        className={`hidden shrink-0 flex-col overflow-y-auto border-r border-black/[0.06] bg-[#f5f5f7] transition-[width] duration-300 ease-out lg:flex ${
          desktopCollapsed ? "w-[72px]" : "w-[264px]"
        }`}
      >
        <SidebarContent
          {...sidebarProps}
          compact={desktopCollapsed}
          onClose={() => setDesktopCollapsed((collapsed) => !collapsed)}
        />
      </aside>

      {mobileSidebarOpen ? (
        <>
          <div
            aria-hidden="true"
            className="fixed inset-0 z-30 bg-black/20 backdrop-blur-[2px] lg:hidden"
            onClick={closeMobileSidebar}
          />
          <aside
            ref={mobileSidebarRef}
            id="mobile-chat-sidebar"
            role="dialog"
            aria-label="チャットメニュー"
            aria-modal="true"
            className="fixed inset-y-0 left-0 z-40 flex w-[min(86vw,320px)] flex-col overflow-y-auto border-r border-black/[0.06] bg-[#f5f5f7] shadow-[20px_0_60px_rgba(0,0,0,0.12)] lg:hidden"
          >
            <SidebarContent
              {...sidebarProps}
              autoFocusClose
              onClose={closeMobileSidebar}
            />
          </aside>
        </>
      ) : null}

      <main
        inert={mobileSidebarOpen}
        className="relative flex min-w-0 flex-1 flex-col"
      >
        <div className="absolute left-4 top-[max(1rem,env(safe-area-inset-top))] z-10 lg:hidden">
          <button
            ref={menuButtonRef}
            type="button"
            aria-label="サイドバーを開く"
            aria-controls="mobile-chat-sidebar"
            aria-expanded={mobileSidebarOpen}
            className="grid size-10 place-items-center rounded-xl text-[#3a3a3c] transition-colors hover:bg-black/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <MenuIcon className="size-[21px]" />
          </button>
        </div>

        <section className="mx-auto flex w-full max-w-[720px] flex-1 flex-col justify-center px-5 pb-20 pt-24 sm:px-8 lg:pb-16 lg:pt-16">
          <div className="w-full -translate-y-[4vh]">
            <h1 className="text-center text-[34px] font-semibold tracking-[-0.045em] text-[#1d1d1f] sm:text-[38px]">
              SodAI
            </h1>
            <div className="mt-7 rounded-[26px] border border-black/[0.1] bg-white p-1.5 shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition focus-within:border-[#0071e3] focus-within:shadow-[0_10px_36px_rgba(0,0,0,0.09)]">
              <label htmlFor="chat-message" className="sr-only">
                SodAIへのメッセージ
              </label>
              <textarea
                ref={textareaRef}
                id="chat-message"
                rows={1}
                value={message}
                onChange={updateMessage}
                placeholder="話しかけてください"
                spellCheck="true"
                className="block min-h-12 max-h-40 w-full resize-none overflow-y-auto bg-transparent px-4 py-[13px] text-[16px] leading-6 text-[#1d1d1f] outline-none placeholder:text-[#6e6e73]"
              />
            </div>
          </div>
        </section>
      </main>

      {authMode ? (
        <AuthDialog
          key={authMode}
          googleEnabled={googleAuthEnabled}
          initialError={
            googleAuthError
              ? "Googleログインを完了できませんでした。もう一度お試しください。"
              : undefined
          }
          mode={authMode}
          onClose={() => {
            setAuthMode(undefined);
            setGoogleAuthError(false);
          }}
        />
      ) : null}
    </div>
  );
}
