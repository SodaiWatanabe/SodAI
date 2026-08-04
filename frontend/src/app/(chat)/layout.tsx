import { cookies } from "next/headers";

import { ApiAccessTokenProvider } from "@/components/auth/api-access-token-provider";
import { ChatDataProvider } from "@/components/chat/chat-data-provider";
import { ChatFrame } from "@/components/chat/chat-frame";
import { CreditBalanceProvider } from "@/components/credits/credit-balance-provider";
import { HumanDataProvider } from "@/components/human/human-data-provider";
import { ToastProvider } from "@/components/ui/toast-provider";
import { getCurrentAccount } from "@/lib/account/server";
import { getAuthCapabilities, getCurrentSession } from "@/lib/auth/session";
import {
  PREFERRED_ANSWERER_COOKIE_NAME,
  parsePreferredAnswerer,
} from "@/lib/preferences/answerer";
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
  const [session, authCapabilities, cookieStore] = await Promise.all([
    getCurrentSession(),
    getAuthCapabilities(),
    cookies(),
  ]);
  const sidebarPreference = parseDesktopSidebarPreference(
    cookieStore.get(DESKTOP_SIDEBAR_COOKIE_NAME)?.value,
  );
  const preferredAnswerer = parsePreferredAnswerer(
    cookieStore.get(PREFERRED_ANSWERER_COOKIE_NAME)?.value,
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
        <CreditBalanceProvider>
          <ChatDataProvider initialPreferredAnswerer={preferredAnswerer}>
            <HumanDataProvider authenticated={Boolean(session)}>
              <ChatFrame
                googleAuthEnabled={authCapabilities.google}
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
            </HumanDataProvider>
          </ChatDataProvider>
        </CreditBalanceProvider>
      </ApiAccessTokenProvider>
    </ToastProvider>
  );
}
