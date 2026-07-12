"use client";

import {
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useEffect, useRef, useState } from "react";

import { AuthDialog, type AuthMode } from "@/components/auth/auth-dialog";
import { authClient } from "@/lib/auth/client";

type ChatShellProps = {
  greeting: string;
  googleAuthEnabled: boolean;
  initialGoogleAuthError: boolean;
  initialUser: SidebarUser | null;
};

type SidebarUser = {
  email: string;
  name: string;
};

type SidebarContentProps = {
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
  const iconPositionClass = compact
    ? "lg:translate-x-[11px]"
    : "translate-x-0";

  return (
    <>
      <div className="relative flex h-12 shrink-0 items-center px-1.5">
        <span
          className={`absolute left-2 whitespace-nowrap text-[18px] font-semibold tracking-[-0.025em] text-[#1d1d1f] transition-opacity duration-150 ${
            compact
              ? "lg:pointer-events-none lg:opacity-0"
              : "opacity-100 lg:delay-150"
          }`}
        >
          SodAI
        </span>
        <button
          type="button"
          aria-label={compact ? "サイドバーを開く" : "サイドバーを閉じる"}
          aria-expanded={!compact}
          className="ml-auto hidden size-10 place-items-center rounded-lg text-[#6e6e73] transition-colors hover:bg-black/[0.05] hover:text-[#3a3a3c] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] lg:grid"
          onClick={onClose}
        >
          {compact ? (
            <PanelLeftOpen className="size-5" />
          ) : (
            <PanelLeftClose className="size-5" />
          )}
        </button>
        <button
          type="button"
          aria-label="サイドバーを閉じる"
          data-mobile-sidebar-close
          className="ml-auto grid size-10 place-items-center rounded-lg text-[#6e6e73] transition-colors hover:bg-black/[0.05] hover:text-[#3a3a3c] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] lg:hidden"
          onClick={onClose}
        >
          <X className="size-5" />
        </button>
      </div>

      <nav className="px-1.5" aria-label="チャット">
        <button
          type="button"
          title="新しいチャット"
          className="flex h-10 w-full items-center gap-2.5 rounded-xl px-0 text-left text-[14px] font-medium text-[#1d1d1f] transition-colors hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]"
          onClick={onNewChat}
        >
          <SquarePen
            className={`size-[18px] shrink-0 transition-transform duration-300 ease-out ${iconPositionClass}`}
          />
          <span className={`whitespace-nowrap transition-opacity ${labelClass}`}>
            新しいチャット
          </span>
        </button>
      </nav>

      <div className="flex-1" />

      <div className="space-y-1.5 px-1.5 pb-[max(0.625rem,env(safe-area-inset-bottom))]">
        {user ? (
          <div
            className="flex h-10 items-center gap-2.5 rounded-full px-1.5"
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
              className={`grid size-8 shrink-0 place-items-center rounded-full text-[#3a3a3c] transition hover:bg-black/[0.05] hover:text-[#1d1d1f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] disabled:opacity-40 ${
                compact ? "lg:hidden" : ""
              }`}
              onClick={onSignOut}
            >
              <LogOut className="size-[17px]" />
            </button>
          </div>
        ) : (
          <div className={compact ? "lg:hidden" : "space-y-1.5"}>
            <button
              type="button"
              title="ログイン"
              className="flex h-10 w-full items-center justify-center rounded-full border border-black/[0.12] bg-transparent px-1.5 text-center text-[14px] font-medium text-[#1d1d1f] transition-colors hover:bg-black/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]"
              onClick={onLogin}
            >
              ログイン
            </button>
            <button
              type="button"
              title="アカウントを作成"
              className="flex h-10 w-full items-center justify-center rounded-full border border-black/[0.12] bg-transparent px-1.5 text-center text-[14px] font-medium text-[#1d1d1f] transition-colors hover:bg-black/[0.035] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]"
              onClick={onCreateAccount}
            >
              アカウントを作成
            </button>
          </div>
        )}
      </div>
    </>
  );
}

export function ChatShell({
  greeting,
  googleAuthEnabled,
  initialGoogleAuthError,
  initialUser,
}: ChatShellProps) {
  const router = useRouter();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileSidebarRef = useRef<HTMLElement>(null);
  const messageInputRef = useRef<HTMLInputElement>(null);
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

    requestAnimationFrame(() => {
      mobileSidebarRef.current?.focus();
    });

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

      if (
        event.shiftKey &&
        (document.activeElement === firstElement ||
          document.activeElement === sidebar)
      ) {
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
    requestAnimationFrame(() => messageInputRef.current?.focus());
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

  function updateMessage(event: ChangeEvent<HTMLInputElement>) {
    setMessage(event.target.value);
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
          desktopCollapsed ? "w-[52px]" : "w-[256px]"
        }`}
      >
        <SidebarContent
          {...sidebarProps}
          compact={desktopCollapsed}
          onClose={() => setDesktopCollapsed((collapsed) => !collapsed)}
        />
      </aside>

      <div
        aria-hidden="true"
        className={`fixed inset-0 z-30 bg-black/20 backdrop-blur-[2px] transition-opacity duration-300 ease-out lg:hidden ${
          mobileSidebarOpen
            ? "pointer-events-auto opacity-100"
            : "pointer-events-none opacity-0"
        }`}
        onClick={closeMobileSidebar}
      />
      <aside
        ref={mobileSidebarRef}
        id="mobile-chat-sidebar"
        role="dialog"
        aria-label="チャットメニュー"
        aria-hidden={!mobileSidebarOpen}
        aria-modal={mobileSidebarOpen}
        inert={!mobileSidebarOpen}
        tabIndex={-1}
        className={`fixed inset-y-0 left-0 z-40 flex w-[min(86vw,320px)] flex-col overflow-y-auto border-r border-black/[0.06] bg-[#f5f5f7] shadow-[20px_0_60px_rgba(0,0,0,0.12)] outline-none transition-transform duration-300 ease-out lg:hidden ${
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <SidebarContent {...sidebarProps} onClose={closeMobileSidebar} />
      </aside>

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
            className="grid size-10 place-items-center rounded-lg text-[#1d1d1f] transition-colors hover:bg-black/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <Menu className="size-[21px]" />
          </button>
        </div>

        <section className="mx-auto flex w-full max-w-[720px] flex-1 flex-col justify-center px-5 pb-20 pt-24 sm:px-8 lg:pb-16 lg:pt-16">
          <div className="w-full -translate-y-[7vh]">
            <h1 className="text-center text-[27px] font-normal tracking-[-0.035em] text-[#1d1d1f] sm:text-[30px]">
              {greeting}
            </h1>
            <label htmlFor="chat-message" className="sr-only">
              SodAIへのメッセージ
            </label>
            <input
              ref={messageInputRef}
              id="chat-message"
              type="text"
              value={message}
              onChange={updateMessage}
              placeholder="話しかけてください"
              spellCheck="true"
              className="mt-6 block h-14 w-full rounded-full border border-black/[0.1] bg-white px-6 text-[16px] text-[#1d1d1f] shadow-[0_6px_24px_rgba(0,0,0,0.055)] outline-none placeholder:text-[#6e6e73]"
            />
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
