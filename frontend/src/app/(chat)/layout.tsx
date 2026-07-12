import { cookies } from "next/headers";

import { ChatDataProvider } from "@/components/chat/chat-data-provider";
import { ChatFrame } from "@/components/chat/chat-frame";
import { ToastProvider } from "@/components/ui/toast-provider";
import { isGoogleAuthConfigured } from "@/lib/auth/environment";
import { getCurrentSession } from "@/lib/auth/session";
import {
  DESKTOP_SIDEBAR_COOKIE_NAME,
  parseDesktopSidebarPreference,
} from "@/lib/preferences/sidebar";

export default async function ChatLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [session, cookieStore] = await Promise.all([
    getCurrentSession(),
    cookies(),
  ]);
  const sidebarPreference = parseDesktopSidebarPreference(
    cookieStore.get(DESKTOP_SIDEBAR_COOKIE_NAME)?.value,
  );
  const user = session?.user
    ? {
        email: session.user.email,
        image: session.user.image ?? null,
        name: session.user.name,
      }
    : null;
  const ownerKey = session?.user.id ?? "guest";

  return (
    <ToastProvider>
      <ChatDataProvider key={ownerKey} ownerKey={ownerKey}>
        <ChatFrame
          googleAuthEnabled={isGoogleAuthConfigured()}
          initialDesktopSidebarCollapsed={sidebarPreference === "collapsed"}
          initialUser={user}
        >
          {children}
        </ChatFrame>
      </ChatDataProvider>
    </ToastProvider>
  );
}
