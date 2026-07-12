import { cookies } from "next/headers";

import { ConversationShell } from "@/components/chat/conversation-shell";
import { isGoogleAuthConfigured } from "@/lib/auth/environment";
import { getCurrentSession } from "@/lib/auth/session";
import {
  DESKTOP_SIDEBAR_COOKIE_NAME,
  parseDesktopSidebarPreference,
} from "@/lib/preferences/sidebar";

export default async function ConversationPage({
  params,
}: PageProps<"/c/[id]">) {
  const [{ id }, session, cookieStore] = await Promise.all([
    params,
    getCurrentSession(),
    cookies(),
  ]);
  const sidebarPreference = parseDesktopSidebarPreference(
    cookieStore.get(DESKTOP_SIDEBAR_COOKIE_NAME)?.value,
  );

  return (
    <ConversationShell
      key={id}
      conversationId={id}
      googleAuthEnabled={isGoogleAuthConfigured()}
      initialDesktopSidebarCollapsed={sidebarPreference === "collapsed"}
      initialGoogleAuthError={false}
      initialUser={
        session?.user
          ? {
              email: session.user.email,
              image: session.user.image ?? null,
              name: session.user.name,
            }
          : null
      }
    />
  );
}
