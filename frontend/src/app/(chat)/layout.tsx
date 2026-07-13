import { cookies } from "next/headers";

import { ApiAccessTokenProvider } from "@/components/auth/api-access-token-provider";
import { ChatDataProvider } from "@/components/chat/chat-data-provider";
import { ChatFrame } from "@/components/chat/chat-frame";
import { ToastProvider } from "@/components/ui/toast-provider";
import { getCurrentAccount } from "@/lib/account/server";
import { isGoogleAuthConfigured } from "@/lib/auth/environment";
import { getCurrentSession } from "@/lib/auth/session";
import {
  DESKTOP_SIDEBAR_COOKIE_NAME,
  parseDesktopSidebarPreference,
} from "@/lib/preferences/sidebar";

export default async function ChatLayout({
  children,
  settings,
}: Readonly<{
  children: React.ReactNode;
  settings: React.ReactNode;
}>) {
  const [session, cookieStore] = await Promise.all([
    getCurrentSession(),
    cookies(),
  ]);
  const sidebarPreference = parseDesktopSidebarPreference(
    cookieStore.get(DESKTOP_SIDEBAR_COOKIE_NAME)?.value,
  );
  const account = session ? await getCurrentAccount() : null;
  const user = session?.user
    ? {
        email: session.user.email,
        image: session.user.image ?? null,
        name: account?.display_name ?? session.user.name,
      }
    : null;
  const ownerKey = session?.user.id ?? "guest";

  return (
    <ToastProvider>
      <ApiAccessTokenProvider key={ownerKey} authenticated={Boolean(session)}>
        <ChatDataProvider>
          <ChatFrame
            googleAuthEnabled={isGoogleAuthConfigured()}
            initialAccountUnavailable={Boolean(
              account && account.status !== "active",
            )}
            initialDesktopSidebarCollapsed={sidebarPreference === "collapsed"}
            initialProfileIncomplete={
              account?.status === "active" && account.display_name === null
            }
            initialUser={user}
          >
            {children}
            {settings}
          </ChatFrame>
        </ChatDataProvider>
      </ApiAccessTokenProvider>
    </ToastProvider>
  );
}
