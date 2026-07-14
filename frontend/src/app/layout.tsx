import type { Metadata } from "next";
import { cookies } from "next/headers";

import { KeyboardShortcutsProvider } from "@/components/preferences/keyboard-shortcuts-provider";
import { ThemeProvider } from "@/components/theme/theme-provider";
import {
  MESSAGE_SEND_SHORTCUT_COOKIE_NAME,
  NEW_CHAT_SHORTCUT_COOKIE_NAME,
  parseKeyboardShortcuts,
} from "@/lib/preferences/keyboard-shortcuts";
import {
  parseThemePreference,
  THEME_COOKIE_NAME,
} from "@/lib/preferences/theme";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "SodAI",
    template: "%s · SodAI",
  },
  description: "SodAIと対話するためのチャットプラットフォーム。",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const themePreference = parseThemePreference(
    cookieStore.get(THEME_COOKIE_NAME)?.value,
  );
  const keyboardShortcuts = parseKeyboardShortcuts({
    messageSend: cookieStore.get(MESSAGE_SEND_SHORTCUT_COOKIE_NAME)?.value,
    newChat: cookieStore.get(NEW_CHAT_SHORTCUT_COOKIE_NAME)?.value,
  });

  return (
    <html lang="ja" data-theme={themePreference}>
      <body>
        <ThemeProvider initialPreference={themePreference}>
          <KeyboardShortcutsProvider initialShortcuts={keyboardShortcuts}>
            {children}
          </KeyboardShortcutsProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
