"use client";

import {
  Equal,
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  X,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { AuthDialog, type AuthMode } from "@/components/auth/auth-dialog";
import { useApiAccessToken } from "@/components/auth/api-access-token-provider";
import {
  SidebarAccount,
  type SidebarUser,
} from "@/components/chat/sidebar-account";
import { ChatAuthProvider } from "@/components/chat/chat-auth-context";
import { useChatData } from "@/components/chat/chat-data-provider";
import { ConversationListItem } from "@/components/chat/conversation-list-item";
import { ToastViewport } from "@/components/ui/toast-provider";
import { authClient } from "@/lib/auth/client";
import type { ConversationSummary } from "@/lib/chat/types";
import { saveDesktopSidebarPreference } from "@/lib/preferences/sidebar";

const SIDEBAR_TRANSITION_DURATION = 300;

export type ChatFrameProps = {
  children: ReactNode;
  googleAuthEnabled: boolean;
  initialDesktopSidebarCollapsed: boolean;
  initialUser: SidebarUser | null;
};

type SidebarProps = {
  activeConversationId?: string;
  compact: boolean;
  contentVisible: boolean;
  conversations: ConversationSummary[];
  guestActionsVisible: boolean;
  onClose: () => void;
  onArchiveConversation: (id: string) => void;
  onOpenAuth: (mode: AuthMode) => void;
  onSelectConversation: (id: string) => void;
  onSignOut: () => void;
  signingOut: boolean;
  user: SidebarUser | null;
};

function Sidebar({
  activeConversationId,
  compact,
  contentVisible,
  conversations,
  guestActionsVisible,
  onClose,
  onArchiveConversation,
  onOpenAuth,
  onSelectConversation,
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
        className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-1.5 pt-2"
        aria-label="会話"
      >
        <button
          type="button"
          title="新しい会話"
          className="flex h-9 w-full items-center rounded-xl text-left text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)]"
          onClick={() => onSelectConversation("")}
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

        {conversations.length > 0 ? (
          <div
            aria-hidden={!contentVisible}
            inert={!contentVisible}
            className={`mt-6 transition-opacity duration-150 ${contentVisibility}`}
          >
            <p className="mb-2 pl-2.5 pr-2 text-sm font-bold text-[var(--text)]">
              会話
            </p>
            <div className="space-y-0.5">
              {conversations.map((conversation) => (
                <ConversationListItem
                  key={conversation.id}
                  active={conversation.id === activeConversationId}
                  conversation={conversation}
                  onArchive={() => onArchiveConversation(conversation.id)}
                  onSelect={() => onSelectConversation(conversation.id)}
                />
              ))}
            </div>
          </div>
        ) : null}
      </nav>

      <div className="px-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))]">
        {user ? (
          <SidebarAccount
            compact={compact}
            contentVisible={contentVisible}
            onSignOut={onSignOut}
            signingOut={signingOut}
            user={user}
          />
        ) : guestActionsVisible ? (
          <div className="space-y-1.5">
            <button
              type="button"
              className="h-10 w-full rounded-full border border-[var(--border)] bg-[var(--button-background)] text-sm font-medium transition-colors hover:bg-[var(--button-hover)]"
              onClick={() => onOpenAuth("login")}
            >
              ログイン
            </button>
            <button
              type="button"
              className="h-10 w-full rounded-full border border-[var(--border)] bg-[var(--button-background)] text-sm font-medium transition-colors hover:bg-[var(--button-hover)]"
              onClick={() => onOpenAuth("register")}
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
  initialDesktopSidebarCollapsed,
  initialUser,
}: ChatFrameProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { invalidate: invalidateAccessToken } = useApiAccessToken();
  const { conversations, subscribeRealtime } = useChatData();
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
  const [authMode, setAuthMode] = useState<AuthMode>();
  const [googleAuthError, setGoogleAuthError] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const openMobileSidebar = useCallback(() => {
    setMobileGuestActionsVisible(false);
    setMobileOpen(true);
  }, []);
  const closeMobileSidebar = useCallback(() => {
    setMobileGuestActionsVisible(false);
    setMobileOpen(false);
  }, []);
  const activeConversationId = pathname.startsWith("/c/")
    ? pathname.slice("/c/".length)
    : undefined;

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("authError") !== "google") return;
    requestAnimationFrame(() => {
      setGoogleAuthError(true);
      setAuthMode("login");
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
          event.type !== "conversation.archived" ||
          event.conversation_id !== activeConversationId
        ) {
          return;
        }
        closeMobileSidebar();
        router.replace("/");
      }),
    [activeConversationId, closeMobileSidebar, router, subscribeRealtime],
  );

  function navigate(id: string) {
    closeMobileSidebar();
    router.push(id ? `/c/${id}` : "/");
  }

  function leaveArchivedConversation(id: string) {
    closeMobileSidebar();
    if (id === activeConversationId) router.replace("/");
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
      activeConversationId={activeConversationId}
      compact={compact}
      contentVisible={contentVisible}
      conversations={conversations}
      guestActionsVisible={guestActionsVisible}
      onClose={onClose}
      onArchiveConversation={leaveArchivedConversation}
      onOpenAuth={setAuthMode}
      onSelectConversation={navigate}
      onSignOut={signOut}
      signingOut={signingOut}
      user={initialUser}
    />
  );

  return (
    <ChatAuthProvider
      authenticated={Boolean(initialUser)}
      openAuth={setAuthMode}
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
        id="mobile-conversation-sidebar"
        role="dialog"
        aria-label="会話メニュー"
        aria-hidden={!mobileOpen}
        aria-modal={mobileOpen}
        inert={!mobileOpen}
        tabIndex={-1}
        className={`fixed inset-y-0 left-0 z-40 flex w-[256px] flex-col overflow-x-hidden bg-[var(--sidebar)] shadow-[12px_0_32px_var(--sidebar-shadow)] transition-transform duration-300 lg:hidden ${
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
          aria-controls="mobile-conversation-sidebar"
          aria-expanded={mobileOpen}
          className="absolute left-1.5 top-1 z-20 grid place-items-center rounded-xl p-2.5 text-[var(--muted)] hover:bg-[var(--hover)] lg:hidden"
          onClick={openMobileSidebar}
        >
          <Equal className="size-[21px]" />
        </button>
        {children}
      </main>

      {authMode ? (
        <AuthDialog
          key={authMode}
          googleEnabled={googleAuthEnabled}
          mode={authMode}
          initialError={
            googleAuthError
              ? "Googleログインを完了できませんでした。もう一度お試しください。"
              : undefined
          }
          onClose={() => {
            setAuthMode(undefined);
            setGoogleAuthError(false);
          }}
        />
      ) : null}
      </div>
    </ChatAuthProvider>
  );
}
