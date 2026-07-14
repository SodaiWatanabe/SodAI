"use client";

import {
  Equal,
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  X,
} from "lucide-react";
import { useRouter, useSelectedLayoutSegments } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { AuthDialog } from "@/components/auth/auth-dialog";
import { useApiAccessToken } from "@/components/auth/api-access-token-provider";
import {
  SidebarAccount,
  type SidebarUser,
} from "@/components/chat/sidebar-account";
import { ChatAuthProvider } from "@/components/chat/chat-auth-context";
import { useChatData } from "@/components/chat/chat-data-provider";
import { ThreadListItem } from "@/components/chat/thread-list-item";
import { ToastViewport } from "@/components/ui/toast-provider";
import { authClient } from "@/lib/auth/client";
import type { ThreadSummary } from "@/lib/chat/types";
import { saveDesktopSidebarPreference } from "@/lib/preferences/sidebar";

const SIDEBAR_TRANSITION_DURATION = 300;

export type ChatFrameProps = {
  children: ReactNode;
  googleAuthEnabled: boolean;
  initialAccountUnavailable: boolean;
  initialDesktopSidebarCollapsed: boolean;
  initialProfileIncomplete: boolean;
  initialUser: SidebarUser | null;
};

type SidebarProps = {
  activeThreadId?: string;
  compact: boolean;
  contentVisible: boolean;
  threads: ThreadSummary[];
  guestActionsVisible: boolean;
  onClose: () => void;
  onArchiveThread: (id: string) => void;
  onOpenAuth: () => void;
  onOpenCredits: () => void;
  onOpenSettings: () => void;
  onSelectThread: (id: string) => void;
  onSignOut: () => void;
  signingOut: boolean;
  user: SidebarUser | null;
};

function Sidebar({
  activeThreadId,
  compact,
  contentVisible,
  threads,
  guestActionsVisible,
  onClose,
  onArchiveThread,
  onOpenAuth,
  onOpenCredits,
  onOpenSettings,
  onSelectThread,
  onSignOut,
  signingOut,
  user,
}: SidebarProps) {
  const contentVisibility = contentVisible
    ? "opacity-100 delay-100 motion-reduce:delay-0"
    : "pointer-events-none opacity-0";

  return (
    <>
      <div className="relative flex h-12 shrink-0 items-center px-1.5">
        <span
          aria-hidden={!contentVisible}
          className={`absolute left-4 whitespace-nowrap text-lg font-semibold tracking-[-0.025em] text-[var(--text)] transition-opacity duration-150 ${contentVisibility}`}
        >
          SodAI
        </span>
        <button
          type="button"
          aria-label={compact ? "サイドバーを開く" : "サイドバーを閉じる"}
          className="ml-auto hidden place-items-center rounded-xl p-2.5 text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] lg:grid"
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
          className="ml-auto grid place-items-center rounded-xl p-2.5 text-[var(--muted)] lg:hidden"
          onClick={onClose}
        >
          <X className="size-5" />
        </button>
      </div>

      <nav
        className="flex min-h-0 flex-1 flex-col overflow-hidden px-1.5 pt-2"
        aria-label="会話"
      >
        <button
          type="button"
          title="新しい会話"
          className="flex h-9 w-full shrink-0 items-center rounded-xl text-left text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)]"
          onClick={() => onSelectThread("")}
        >
          <span className="grid shrink-0 place-items-center px-2.5">
            <SquarePen className="size-5" />
          </span>
          <span
            aria-hidden={!contentVisible}
            className={`whitespace-nowrap transition-opacity duration-150 ${contentVisibility}`}
          >
            新しい会話
          </span>
        </button>

        {threads.length > 0 ? (
          <div
            aria-hidden={!contentVisible}
            inert={!contentVisible}
            className={`mt-6 min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain transition-opacity duration-150 ${contentVisibility}`}
          >
            <p className="mb-2 pl-2.5 pr-2 text-sm font-bold text-[var(--text)]">
              会話
            </p>
            <div className="space-y-0.5">
              {threads.map((thread) => (
                <ThreadListItem
                  key={thread.id}
                  active={thread.id === activeThreadId}
                  thread={thread}
                  onArchive={() => onArchiveThread(thread.id)}
                  onSelect={() => onSelectThread(thread.id)}
                />
              ))}
            </div>
          </div>
        ) : null}
      </nav>

      <div className="px-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))] pt-1.5">
        {user ? (
          <SidebarAccount
            compact={compact}
            contentVisible={contentVisible}
            onOpenCredits={onOpenCredits}
            onOpenSettings={onOpenSettings}
            onSignOut={onSignOut}
            signingOut={signingOut}
            user={user}
          />
        ) : guestActionsVisible ? (
          <div className="space-y-1.5">
            <button
              type="button"
              className="h-10 w-full rounded-full border border-[var(--border)] bg-[var(--button-background)] text-sm font-medium transition-colors hover:bg-[var(--button-hover)]"
              onClick={onOpenAuth}
            >
              ログイン
            </button>
            <button
              type="button"
              className="h-10 w-full rounded-full border border-[var(--border)] bg-[var(--button-background)] text-sm font-medium transition-colors hover:bg-[var(--button-hover)]"
              onClick={onOpenAuth}
            >
              アカウントを作成
            </button>
          </div>
        ) : null}
      </div>
    </>
  );
}

export function ChatFrame({
  children,
  googleAuthEnabled,
  initialAccountUnavailable,
  initialDesktopSidebarCollapsed,
  initialProfileIncomplete,
  initialUser,
}: ChatFrameProps) {
  const router = useRouter();
  const childSegments = useSelectedLayoutSegments();
  const { invalidate: invalidateAccessToken } = useApiAccessToken();
  const { subscribeRealtime, threads } = useChatData();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileSidebarRef = useRef<HTMLElement>(null);
  const [desktopCollapsed, setDesktopCollapsed] = useState(
    initialDesktopSidebarCollapsed,
  );
  const [desktopGuestActionsVisible, setDesktopGuestActionsVisible] = useState(
    !initialDesktopSidebarCollapsed,
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileGuestActionsVisible, setMobileGuestActionsVisible] = useState(false);
  const [authOpen, setAuthOpen] = useState(
    initialAccountUnavailable || initialProfileIncomplete,
  );
  const [googleAuthError, setGoogleAuthError] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const openAuth = useCallback(() => setAuthOpen(true), []);
  const openMobileSidebar = useCallback(() => {
    setMobileGuestActionsVisible(false);
    setMobileOpen(true);
  }, []);
  const closeMobileSidebar = useCallback(() => {
    setMobileGuestActionsVisible(false);
    setMobileOpen(false);
  }, []);
  const activeThreadId =
    childSegments.at(0) === "t" ? childSegments.at(1) : undefined;

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("authError") !== "google") return;
    requestAnimationFrame(() => {
      setGoogleAuthError(true);
      setAuthOpen(true);
    });
    url.searchParams.delete("authError");
    window.history.replaceState(window.history.state, "", url);
  }, []);

  useEffect(() => {
    if (desktopCollapsed || desktopGuestActionsVisible) return;
    const timer = setTimeout(
      () => setDesktopGuestActionsVisible(true),
      SIDEBAR_TRANSITION_DURATION,
    );
    return () => clearTimeout(timer);
  }, [desktopCollapsed, desktopGuestActionsVisible]);

  useEffect(() => {
    if (!mobileOpen || mobileGuestActionsVisible) return;
    const timer = setTimeout(
      () => setMobileGuestActionsVisible(true),
      SIDEBAR_TRANSITION_DURATION,
    );
    return () => clearTimeout(timer);
  }, [mobileGuestActionsVisible, mobileOpen]);

  useEffect(() => {
    if (!mobileOpen) return;
    requestAnimationFrame(() => mobileSidebarRef.current?.focus());

    function handleKeyDown(event: KeyboardEvent) {
      const sidebar = mobileSidebarRef.current;
      if (!sidebar) return;
      if (event.key === "Escape") {
        event.preventDefault();
        closeMobileSidebar();
        requestAnimationFrame(() => menuButtonRef.current?.focus());
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        sidebar.querySelectorAll<HTMLButtonElement | HTMLAnchorElement>(
          "button:not([disabled]), a[href]",
        ),
      ).filter((element) => element.getClientRects().length > 0);
      const first = focusable.at(0);
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && (document.activeElement === first || document.activeElement === sidebar)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeMobileSidebar, mobileOpen]);

  useEffect(
    () =>
      subscribeRealtime((event) => {
        if (
          event.type !== "thread.archived" ||
          event.thread_id !== activeThreadId
        ) {
          return;
        }
        closeMobileSidebar();
        router.replace("/");
      }),
    [activeThreadId, closeMobileSidebar, router, subscribeRealtime],
  );

  function navigate(id: string) {
    closeMobileSidebar();
    router.push(id ? `/t/${id}` : "/");
  }

  function navigateToSettings() {
    closeMobileSidebar();
    router.push("/settings");
  }

  function navigateToCredits() {
    closeMobileSidebar();
    router.push("/settings/credits");
  }

  function leaveArchivedThread(id: string) {
    closeMobileSidebar();
    if (id === activeThreadId) router.replace("/");
  }

  function toggleDesktop() {
    const next = !desktopCollapsed;
    if (next) setDesktopGuestActionsVisible(false);
    setDesktopCollapsed(next);
    saveDesktopSidebarPreference(next ? "collapsed" : "expanded");
  }

  async function signOut() {
    setSigningOut(true);
    invalidateAccessToken();
    await authClient.signOut();
    setSigningOut(false);
    router.refresh();
  }

  const sidebar = (
    compact: boolean,
    contentVisible: boolean,
    guestActionsVisible: boolean,
    onClose: () => void,
  ) => (
    <Sidebar
      activeThreadId={activeThreadId}
      compact={compact}
      contentVisible={contentVisible}
      threads={threads}
      guestActionsVisible={guestActionsVisible}
      onClose={onClose}
      onArchiveThread={leaveArchivedThread}
      onOpenAuth={openAuth}
      onOpenCredits={navigateToCredits}
      onOpenSettings={navigateToSettings}
      onSelectThread={navigate}
      onSignOut={signOut}
      signingOut={signingOut}
      user={initialUser}
    />
  );

  return (
    <ChatAuthProvider
      authenticated={Boolean(initialUser)}
      openAuth={openAuth}
      settingsAccessible={
        Boolean(initialUser) &&
        !initialAccountUnavailable &&
        !initialProfileIncomplete
      }
    >
      <div className="flex h-[100dvh] overflow-hidden bg-[var(--canvas)]">
      <aside
        aria-label="会話サイドバー"
        className={`hidden shrink-0 flex-col overflow-hidden bg-[var(--sidebar)] shadow-[inset_-1px_0_0_var(--separator)] transition-[width] duration-300 lg:flex ${
          desktopCollapsed ? "w-[52px]" : "w-[256px]"
        }`}
      >
        {sidebar(
          desktopCollapsed,
          !desktopCollapsed,
          desktopGuestActionsVisible,
          toggleDesktop,
        )}
      </aside>

      <div
        aria-hidden="true"
        className={`fixed inset-0 z-30 bg-[var(--overlay)] transition-opacity duration-300 lg:hidden ${
          mobileOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={closeMobileSidebar}
      />
      <aside
        ref={mobileSidebarRef}
        id="mobile-thread-sidebar"
        role="dialog"
        aria-label="会話メニュー"
        aria-hidden={!mobileOpen}
        aria-modal={mobileOpen}
        inert={!mobileOpen}
        tabIndex={-1}
        className={`fixed inset-y-0 left-0 z-40 flex w-[256px] flex-col overflow-hidden bg-[var(--sidebar)] shadow-[12px_0_32px_var(--sidebar-shadow)] transition-transform duration-300 lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {sidebar(false, true, mobileGuestActionsVisible, closeMobileSidebar)}
      </aside>

      <main
        data-desktop-sidebar={desktopCollapsed ? "collapsed" : "expanded"}
        className="relative flex min-w-0 flex-1 flex-col"
      >
        <ToastViewport />
        <button
          ref={menuButtonRef}
          type="button"
          aria-label="サイドバーを開く"
          aria-controls="mobile-thread-sidebar"
          aria-expanded={mobileOpen}
          className="absolute left-1.5 top-1 z-20 grid place-items-center rounded-xl p-2.5 text-[var(--muted)] hover:bg-[var(--hover)] lg:hidden"
          onClick={openMobileSidebar}
        >
          <Equal className="size-[21px]" />
        </button>
        {children}
      </main>

      {authOpen ? (
        <AuthDialog
          accountUnavailable={initialAccountUnavailable}
          googleEnabled={googleAuthEnabled}
          resumeProfile={initialProfileIncomplete}
          initialError={
            googleAuthError
              ? "Googleログインを完了できませんでした。もう一度お試しください。"
              : undefined
          }
          onClose={() => {
            setAuthOpen(false);
            setGoogleAuthError(false);
          }}
        />
      ) : null}
      </div>
    </ChatAuthProvider>
  );
}
