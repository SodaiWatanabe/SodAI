"use client";

import {
  Equal,
  Orbit,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
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
import {
  resolveChatFrameRoute,
  type SodaiProduct,
} from "@/components/chat/chat-frame-route";
import { ProductSwitcher } from "@/components/chat/product-switcher";
import { ThreadListItem } from "@/components/chat/thread-list-item";
import { ThreadSearchDialog } from "@/components/chat/thread-search-dialog";
import {
  ThreadSearchNavigationProvider,
  type ThreadSearchNavigationTarget,
} from "@/components/chat/thread-search-navigation";
import { useKeyboardShortcuts } from "@/components/preferences/keyboard-shortcuts-provider";
import { ToastViewport } from "@/components/ui/toast-provider";
import { HumanAnswerListItem } from "@/components/human/human-answer-list-item";
import { useHumanData } from "@/components/human/human-data-provider";
import { authClient } from "@/lib/auth/client";
import type { ThreadSearchHit, ThreadSummary } from "@/lib/chat/types";
import type { HumanAnswerSummary } from "@/lib/human/types";
import { matchesKeyboardShortcut } from "@/lib/preferences/keyboard-shortcuts";
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
  activeHumanAnswerId?: string;
  activeThreadId?: string;
  answers: HumanAnswerSummary[];
  answersLoading: boolean;
  brainHomeActive: boolean;
  historyDisabled: boolean;
  compact: boolean;
  contentVisible: boolean;
  newChatActive: boolean;
  nextAnswersCursor: string | null;
  product: SodaiProduct;
  threads: ThreadSummary[];
  guestActionsVisible: boolean;
  onClose: () => void;
  onArchiveThread: (id: string) => void;
  onOpenAuth: () => void;
  onOpenCredits: () => void;
  onOpenSearch: () => void;
  onOpenSettings: () => void;
  onLoadMoreAnswers: () => void;
  onSelectHumanAnswer: (id: string) => void;
  onSelectProduct: (product: SodaiProduct) => void;
  onSelectThread: (id: string) => void;
  onSignOut: () => void;
  signingOut: boolean;
  user: SidebarUser | null;
};

function Sidebar({
  activeHumanAnswerId,
  activeThreadId,
  answers,
  answersLoading,
  brainHomeActive,
  compact,
  contentVisible,
  newChatActive,
  nextAnswersCursor,
  product,
  threads,
  guestActionsVisible,
  historyDisabled,
  onClose,
  onArchiveThread,
  onOpenAuth,
  onOpenCredits,
  onOpenSearch,
  onOpenSettings,
  onLoadMoreAnswers,
  onSelectHumanAnswer,
  onSelectProduct,
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
        <ProductSwitcher
          contentVisible={contentVisible}
          product={product}
          onChange={onSelectProduct}
        />
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
        aria-label={product === "chat" ? "会話" : "Brain"}
      >
        {product === "chat" ? (
          <>
            <button
              type="button"
              title="新しい会話"
              aria-current={newChatActive ? "page" : undefined}
              className={`flex h-9 w-full shrink-0 items-center rounded-xl text-left text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] ${
                newChatActive ? "bg-[var(--hover)]" : ""
              }`}
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

            <button
              type="button"
              title="会話を検索"
              className="mt-0.5 flex h-9 w-full shrink-0 items-center rounded-xl text-left text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)]"
              onClick={onOpenSearch}
            >
              <span className="grid shrink-0 place-items-center px-2.5">
                <Search aria-hidden="true" className="size-5" />
              </span>
              <span
                aria-hidden={!contentVisible}
                className={`whitespace-nowrap transition-opacity duration-150 ${contentVisibility}`}
              >
                会話を検索
              </span>
            </button>

            {threads.length > 0 ? (
              <div
                aria-hidden={!contentVisible}
                inert={!contentVisible}
                className={`sidebar-thread-scroll mt-6 min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain transition-opacity duration-150 ${contentVisibility}`}
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
          </>
        ) : (
          <>
            <button
              type="button"
              title="思考する"
              aria-current={brainHomeActive ? "page" : undefined}
              className={`flex h-9 w-full shrink-0 items-center rounded-xl text-left text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] ${
                brainHomeActive ? "bg-[var(--hover)]" : ""
              }`}
              onClick={() => onSelectProduct("brain")}
            >
              <span className="grid shrink-0 place-items-center px-2.5">
                <Orbit aria-hidden="true" className="size-5" />
              </span>
              <span
                aria-hidden={!contentVisible}
                className={`whitespace-nowrap transition-opacity duration-150 ${contentVisibility}`}
              >
                思考する
              </span>
            </button>

            <div
              aria-hidden={!contentVisible}
              inert={!contentVisible}
              className={`sidebar-thread-scroll mt-6 min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain transition-opacity duration-150 ${contentVisibility}`}
            >
              <p className="mb-2 pl-2.5 pr-2 text-sm font-bold text-[var(--text)]">
                回答履歴
              </p>
              {answers.length > 0 ? (
                <div className="space-y-0.5">
                  {answers.map((answer) => (
                    <HumanAnswerListItem
                      key={answer.execution_id}
                      active={answer.execution_id === activeHumanAnswerId}
                      answer={answer}
                      disabled={historyDisabled}
                      onSelect={() => onSelectHumanAnswer(answer.execution_id)}
                    />
                  ))}
                </div>
              ) : !answersLoading ? (
                <p className="px-2.5 py-1 text-sm text-[var(--muted)]">
                  まだ回答履歴はありません
                </p>
              ) : null}
              {nextAnswersCursor ? (
                <button
                  type="button"
                  disabled={answersLoading}
                  className="mt-2 h-9 w-full rounded-xl px-2.5 text-left text-sm font-medium text-[var(--muted)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--text)] disabled:opacity-50"
                  onClick={onLoadMoreAnswers}
                >
                  {answersLoading ? "読み込み中…" : "さらに表示"}
                </button>
              ) : null}
            </div>
          </>
        )}
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
  authClient.useSession();
  const router = useRouter();
  const childSegments = useSelectedLayoutSegments();
  const frameRoute = resolveChatFrameRoute(childSegments);
  const { invalidate: invalidateAccessToken } = useApiAccessToken();
  const { subscribeRealtime, threads } = useChatData();
  const {
    answers,
    answersLoading,
    loadMoreAnswers,
    nextAnswersCursor,
    state: humanState,
  } = useHumanData();
  const { recordingAction, shortcuts } = useKeyboardShortcuts();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileSidebarRef = useRef<HTMLElement>(null);
  const searchOpenedFromMobileRef = useRef(false);
  const searchNavigationSequenceRef = useRef(0);
  const [desktopCollapsed, setDesktopCollapsed] = useState(
    initialDesktopSidebarCollapsed,
  );
  const [desktopGuestActionsVisible, setDesktopGuestActionsVisible] = useState(
    !initialDesktopSidebarCollapsed,
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileGuestActionsVisible, setMobileGuestActionsVisible] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchNavigationTarget, setSearchNavigationTarget] =
    useState<ThreadSearchNavigationTarget | null>(null);
  const [authOpen, setAuthOpen] = useState(
    initialAccountUnavailable || initialProfileIncomplete,
  );
  const [googleAuthError, setGoogleAuthError] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const product = frameRoute.product;
  const activeHumanAnswerId = frameRoute.activeHumanAnswerId;
  const humanAnswerActive = humanState?.status === "assigned";
  const openAuth = useCallback(() => setAuthOpen(true), []);
  const openMobileSidebar = useCallback(() => {
    setMobileGuestActionsVisible(false);
    setMobileOpen(true);
  }, []);
  const closeMobileSidebar = useCallback(() => {
    setMobileGuestActionsVisible(false);
    setMobileOpen(false);
  }, []);
  const openSearch = useCallback(() => {
    searchOpenedFromMobileRef.current = mobileOpen;
    closeMobileSidebar();
    setSearchOpen(true);
  }, [closeMobileSidebar, mobileOpen]);
  const closeSearch = useCallback(() => {
    setSearchOpen(false);
    if (!searchOpenedFromMobileRef.current) return;
    searchOpenedFromMobileRef.current = false;
    requestAnimationFrame(() => menuButtonRef.current?.focus());
  }, []);
  const navigate = useCallback(
    (id: string) => {
      if (humanAnswerActive) return;
      closeMobileSidebar();
      setSearchNavigationTarget(null);
      router.push(id ? `/t/${id}` : "/");
    },
    [closeMobileSidebar, humanAnswerActive, router],
  );
  const activeThreadId = frameRoute.activeThreadId;

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
    if (
      humanAnswerActive &&
      (product !== "brain" || Boolean(activeHumanAnswerId))
    ) {
      const frame = requestAnimationFrame(closeMobileSidebar);
      router.replace("/brain");
      return () => cancelAnimationFrame(frame);
    }
  }, [
    activeHumanAnswerId,
    closeMobileSidebar,
    humanAnswerActive,
    product,
    router,
  ]);

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

  useEffect(() => {
    const shortcut = shortcuts.newChat;
    if (!shortcut) return;
    const activeShortcut = shortcut;

    function handleNewChatShortcut(event: KeyboardEvent) {
      if (
        event.defaultPrevented ||
        event.repeat ||
        recordingAction ||
        document.querySelector("dialog[open]")
      ) {
        return;
      }
      if (
        !matchesKeyboardShortcut(
          {
            altKey: event.altKey,
            ctrlKey: event.ctrlKey,
            isComposing: event.isComposing,
            key: event.key,
            keyCode: event.keyCode,
            metaKey: event.metaKey,
            shiftKey: event.shiftKey,
          },
          activeShortcut,
        )
      ) {
        return;
      }
      event.preventDefault();
      navigate("");
    }

    document.addEventListener("keydown", handleNewChatShortcut);
    return () =>
      document.removeEventListener("keydown", handleNewChatShortcut);
  }, [navigate, recordingAction, shortcuts.newChat]);

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

  function navigateToSettings() {
    closeMobileSidebar();
    setSearchNavigationTarget(null);
    router.push("/settings");
  }

  function navigateToCredits() {
    closeMobileSidebar();
    setSearchNavigationTarget(null);
    router.push("/settings/credits");
  }

  function navigateToProduct(nextProduct: SodaiProduct) {
    closeMobileSidebar();
    setSearchNavigationTarget(null);
    if (nextProduct === "brain" && !initialUser) {
      openAuth();
      return;
    }
    if (humanAnswerActive && nextProduct !== "brain") return;
    router.push(nextProduct === "brain" ? "/brain" : "/");
  }

  function navigateToHumanAnswer(executionId: string) {
    if (humanAnswerActive) return;
    closeMobileSidebar();
    setSearchNavigationTarget(null);
    router.push(`/brain/answers/${encodeURIComponent(executionId)}`);
  }

  function navigateToSearchResult(hit: ThreadSearchHit, query: string) {
    searchOpenedFromMobileRef.current = false;
    setSearchOpen(false);
    const path = `/t/${encodeURIComponent(hit.thread.id)}`;
    if (!hit.entry_id) {
      setSearchNavigationTarget(null);
      router.push(path);
      return;
    }
    searchNavigationSequenceRef.current += 1;
    setSearchNavigationTarget({
      entryId: hit.entry_id,
      query,
      sequence: searchNavigationSequenceRef.current,
      threadId: hit.thread.id,
    });
    router.push(`${path}?entry=${encodeURIComponent(hit.entry_id)}`);
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
      activeHumanAnswerId={activeHumanAnswerId}
      activeThreadId={activeThreadId}
      answers={answers}
      answersLoading={answersLoading}
      brainHomeActive={!activeHumanAnswerId}
      compact={compact}
      contentVisible={contentVisible}
      newChatActive={frameRoute.newChatActive}
      product={product}
      threads={threads}
      guestActionsVisible={guestActionsVisible}
      historyDisabled={humanAnswerActive}
      onClose={onClose}
      onArchiveThread={leaveArchivedThread}
      onOpenAuth={openAuth}
      onOpenCredits={navigateToCredits}
      onOpenSearch={openSearch}
      onOpenSettings={navigateToSettings}
      onLoadMoreAnswers={() => void loadMoreAnswers()}
      onSelectHumanAnswer={navigateToHumanAnswer}
      onSelectProduct={navigateToProduct}
      onSelectThread={navigate}
      onSignOut={signOut}
      signingOut={signingOut}
      nextAnswersCursor={nextAnswersCursor}
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
        className={`fixed inset-y-0 left-0 z-40 flex w-[256px] flex-col overflow-hidden bg-[var(--sidebar)] shadow-[12px_0_32px_var(--sidebar-shadow)] outline-none transition-transform duration-300 lg:hidden ${
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
        <ThreadSearchNavigationProvider target={searchNavigationTarget}>
          {children}
        </ThreadSearchNavigationProvider>
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
      {searchOpen ? (
        <ThreadSearchDialog
          onClose={closeSearch}
          onSelect={navigateToSearchResult}
        />
      ) : null}
      </div>
    </ChatAuthProvider>
  );
}
