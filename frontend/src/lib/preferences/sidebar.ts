export const DESKTOP_SIDEBAR_COOKIE_NAME = "sodai_sidebar_state";

export type DesktopSidebarPreference = "collapsed" | "expanded";

const DEFAULT_PREFERENCE: DesktopSidebarPreference = "expanded";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export function parseDesktopSidebarPreference(
  value: string | undefined,
): DesktopSidebarPreference {
  return value === "collapsed" || value === "expanded"
    ? value
    : DEFAULT_PREFERENCE;
}

export function createDesktopSidebarCookie(
  preference: DesktopSidebarPreference,
  secure: boolean,
) {
  const attributes = [
    `${DESKTOP_SIDEBAR_COOKIE_NAME}=${preference}`,
    "Path=/",
    `Max-Age=${COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ];

  if (secure) {
    attributes.push("Secure");
  }

  return attributes.join("; ");
}
