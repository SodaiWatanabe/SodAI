"use client";

import {
  ChevronRight,
  Coins,
  Keyboard,
  Settings2,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import type { AnchorHTMLAttributes, ReactNode } from "react";

export type SettingsSection =
  | "account"
  | "credits"
  | "general"
  | "keyboard"
  | "root";

type SettingsItem = {
  href: string;
  icon: LucideIcon;
  label: string;
  mobileHref: string;
  mobileVisible?: boolean;
  section: Exclude<SettingsSection, "root">;
};

const settingsItems: readonly SettingsItem[] = [
  {
    href: "/settings",
    icon: Settings2,
    label: "一般",
    mobileHref: "/settings/general",
    section: "general",
  },
  {
    href: "/settings/account",
    icon: UserRound,
    label: "アカウント",
    mobileHref: "/settings/account",
    section: "account",
  },
  {
    href: "/settings/credits",
    icon: Coins,
    label: "クレジット",
    mobileHref: "/settings/credits",
    section: "credits",
  },
  {
    href: "/settings/keyboard",
    icon: Keyboard,
    label: "キーボード",
    mobileHref: "/settings/keyboard",
    mobileVisible: false,
    section: "keyboard",
  },
] as const;

type SettingsRouteLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  children: ReactNode;
  href: string;
};

export function SettingsRouteLink({
  children,
  href,
  onClick,
  ...props
}: SettingsRouteLinkProps) {
  return (
    <a
      {...props}
      href={href}
      onClick={(event) => {
        onClick?.(event);
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        window.history.replaceState(null, "", href);
      }}
    >
      {children}
    </a>
  );
}

export function SettingsNavigation({
  section,
  variant = "sidebar",
}: {
  section: SettingsSection;
  variant?: "index" | "sidebar";
}) {
  return (
    <nav aria-label="設定項目" className="space-y-0.5">
      {settingsItems.map(
        ({
          href,
          icon: Icon,
          label,
          mobileHref,
          mobileVisible = true,
          section: itemSection,
        }) => {
          if (variant === "index" && !mobileVisible) return null;
          const linkHref = variant === "index" ? mobileHref : href;
          const active =
            variant === "sidebar" &&
            (section === itemSection ||
              (section === "root" && itemSection === "general"));

          return (
            <SettingsRouteLink
              key={linkHref}
              href={linkHref}
              aria-current={active ? "page" : undefined}
              className={`flex h-9 w-full items-center rounded-xl text-left text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] ${
                active ? "bg-[var(--hover)]" : ""
              }`}
            >
              <span className="grid shrink-0 place-items-center px-2.5">
                <Icon aria-hidden="true" className="size-5" />
              </span>
              <span>{label}</span>
              {variant === "index" ? (
                <ChevronRight
                  aria-hidden="true"
                  className="ml-auto mr-2.5 size-4 shrink-0 text-[var(--muted)]"
                />
              ) : null}
            </SettingsRouteLink>
          );
        },
      )}
    </nav>
  );
}

export function SettingsIndex() {
  return (
    <div className="min-h-full px-1.5 pt-3">
      <SettingsNavigation section="root" variant="index" />
    </div>
  );
}
