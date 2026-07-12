export const THEME_COOKIE_NAME = "sodai_theme";

export const themePreferences = ["system", "light", "dark"] as const;

export type ThemePreference = (typeof themePreferences)[number];

const DEFAULT_THEME: ThemePreference = "system";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export function parseThemePreference(
  value: string | undefined,
): ThemePreference {
  return themePreferences.includes(value as ThemePreference)
    ? (value as ThemePreference)
    : DEFAULT_THEME;
}

export function createThemeCookie(
  preference: ThemePreference,
  secure: boolean,
) {
  const attributes = [
    `${THEME_COOKIE_NAME}=${preference}`,
    "Path=/",
    `Max-Age=${COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ];

  if (secure) {
    attributes.push("Secure");
  }

  return attributes.join("; ");
}
