"use client";

import {
  Equal,
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useEffect, useRef, useState } from "react";

import { AuthDialog, type AuthMode } from "@/components/auth/auth-dialog";
import {
  SidebarAccount,
  type SidebarUser,
} from "@/components/chat/sidebar-account";
import { authClient } from "@/lib/auth/client";
import { createDesktopSidebarCookie } from "@/lib/preferences/sidebar";

type ChatShellProps = {
  greeting: string;
  googleAuthEnabled: boolean;
  initialDesktopSidebarCollapsed: boolean;
  initialGoogleAuthError: boolean;
  initialUser: SidebarUser | null;
};

type SidebarContentProps = {
  compact?: boolean;
  contentVisible: boolean;
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
  contentVisible,
  onClose,
  onCreateAccount,
  onLogin,
  onNewChat,
  onSignOut,
  signingOut,
  user,
}: SidebarContentProps) {
  const primaryLabelClass = contentVisible
    ? "opacity-100 delay-100 motion-reduce:delay-0"
    : "pointer-events-none opacity-0";
  return (
    <>
      <div className="relative flex h-12 shrink-0 items-center px-1.5">
        <span
          className={`absolute left-[19px] whitespace-nowrap text-lg font-semibold tracking-[-0.025em] text-[var(--text)] transition-opacity duration-150 ${
            compact
              ? "lg:pointer-events-none lg:opacity-0"
              : "opacity-100 lg:delay-100 lg:motion-reduce:delay-0"
          }`}
        >
          SodAI
        </span>
        <button
          type="button"
          aria-label={compact ? "サイドバーを開く" : "サイドバーを閉じる"}
          aria-expanded={!compact}
          className="ml-auto hidden size-10 place-items-center rounded-xl text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--icon-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] lg:grid"
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
          className="ml-auto grid size-10 place-items-center rounded-xl text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--icon-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] lg:hidden"
          onClick={onClose}
        >
          <X className="size-5" />
        </button>
      </div>

      <nav className="px-1.5 pt-2" aria-label="チャット">
        <button
          type="button"
          title="新しいチャット"
          className="flex h-9 w-full items-center rounded-xl text-left text-sm font-medium text-[var(--text)] transition-colors duration-150 hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
          onClick={onNewChat}
        >
          <span className="grid w-10 shrink-0 place-items-center" aria-hidden="true">
            <SquarePen className="size-[18px]" />
          </span>
          <span
            className={`whitespace-nowrap transition-opacity duration-150 ${
              compact ? "lg:w-0 lg:overflow-hidden" : ""
            } ${primaryLabelClass}`}
          >
            新しいチャット
          </span>
        </button>
      </nav>

      <div className="flex-1" />

      <div className="space-y-1.5 px-1.5 pb-[max(0.625rem,env(safe-area-inset-bottom))]">
        {user ? (
          <SidebarAccount
            compact={compact}
            contentVisible={contentVisible}
            onSignOut={onSignOut}
            signingOut={signingOut}
            user={user}
          />
        ) : (
          <div
            aria-hidden={!contentVisible}
            inert={!contentVisible}
            className={`space-y-1.5 transition-opacity duration-150 ${
              contentVisible
                ? "opacity-100 delay-300 motion-reduce:delay-0"
                : "pointer-events-none opacity-0"
            }`}
          >
            <button
              type="button"
              title="ログイン"
              className="flex h-10 w-full items-center justify-center rounded-full border border-[var(--border)] bg-[var(--button-background)] px-1.5 text-center text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--button-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
              onClick={onLogin}
            >
              ログイン
            </button>
            <button
              type="button"
              title="アカウントを作成"
              className="flex h-10 w-full items-center justify-center rounded-full border border-[var(--border)] bg-[var(--button-background)] px-1.5 text-center text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--button-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
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
  initialDesktopSidebarCollapsed,
  initialGoogleAuthError,
  initialUser,
}: ChatShellProps) {
  const router = useRouter();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileSidebarRef = useRef<HTMLElement>(null);
  const messageInputRef = useRef<HTMLInputElement>(null);
  const [desktopCollapsed, setDesktopCollapsed] = useState(
    initialDesktopSidebarCollapsed,
  );
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

  function toggleDesktopSidebar() {
    const nextCollapsed = !desktopCollapsed;
    setDesktopCollapsed(nextCollapsed);
    document.cookie = createDesktopSidebarCookie(
      nextCollapsed ? "collapsed" : "expanded",
      window.location.protocol === "https:",
    );
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
    <div className="flex h-[100dvh] overflow-hidden bg-[var(--canvas)]">
      <aside
        aria-label="チャットサイドバー"
        className={`hidden shrink-0 flex-col overflow-hidden bg-[var(--sidebar)] shadow-[inset_-1px_0_0_var(--separator)] transition-[width] duration-300 ease-out lg:flex ${
          desktopCollapsed ? "w-[52px]" : "w-[256px]"
        }`}
      >
        <SidebarContent
          {...sidebarProps}
          compact={desktopCollapsed}
          contentVisible={!desktopCollapsed}
          onClose={toggleDesktopSidebar}
        />
      </aside>

      <div
        aria-hidden="true"
        className={`fixed inset-0 z-30 bg-[var(--overlay)] transition-opacity duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] will-change-[opacity] motion-reduce:transition-none lg:hidden ${
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
        className="fixed inset-y-0 left-0 z-40 flex w-[256px] flex-col overflow-hidden bg-[var(--sidebar)] shadow-[inset_-1px_0_0_var(--separator),12px_0_32px_var(--sidebar-shadow)] outline-none transition-transform duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] will-change-transform motion-reduce:transition-none lg:hidden"
        style={{
          transform: mobileSidebarOpen
            ? "translate3d(0, 0, 0)"
            : "translate3d(-100%, 0, 0)",
        }}
      >
        <SidebarContent
          {...sidebarProps}
          contentVisible
          onClose={closeMobileSidebar}
        />
      </aside>

      <main
        inert={mobileSidebarOpen}
        className="relative flex min-w-0 flex-1 flex-col"
      >
        <header className="flex h-12 shrink-0 items-center px-1.5">
          <button
            ref={menuButtonRef}
            type="button"
            aria-label="サイドバーを開く"
            aria-controls="mobile-chat-sidebar"
            aria-expanded={mobileSidebarOpen}
            className="grid size-10 place-items-center rounded-xl text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--icon-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] lg:hidden"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <Equal className="size-[21px]" />
          </button>
        </header>

        <section className="mx-auto flex w-full max-w-[720px] flex-1 flex-col justify-center px-5 pb-20 sm:px-8 lg:pb-16">
          <div className="w-full -translate-y-[7vh]">
            <h1 className="text-center text-2xl font-normal tracking-[-0.035em] text-[var(--text)] sm:text-[27px]">
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
              className="mt-6 block h-13 w-full rounded-full border border-[var(--field-border)] bg-[var(--surface)] px-6 text-[16px] text-[var(--text)] shadow-[0_6px_24px_var(--input-shadow)] outline-none placeholder:text-[var(--muted)]"
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
