import type { Metadata } from "next";
import { cookies } from "next/headers";

import { ThemeProvider } from "@/components/theme/theme-provider";
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

  return (
    <html lang="ja" data-theme={themePreference}>
      <body>
        <ThemeProvider initialPreference={themePreference}>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
