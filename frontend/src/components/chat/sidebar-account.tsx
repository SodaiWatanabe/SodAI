"use client";

import { LogOut, UserRound } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ThemeSelector } from "@/components/theme/theme-selector";

export type SidebarUser = {
  email: string;
  image: string | null;
  name: string;
};

type SidebarAccountProps = {
  compact: boolean;
  contentVisible: boolean;
  onSignOut: () => void;
  signingOut: boolean;
  user: SidebarUser;
};

function AccountAvatar({ image }: Pick<SidebarUser, "image">) {
  const [imageFailed, setImageFailed] = useState(false);

  if (image && !imageFailed) {
    return (
      <Image
        unoptimized
        src={image}
        alt=""
        width={20}
        height={20}
        referrerPolicy="no-referrer"
        className="size-5 rounded-full object-cover"
        onError={() => setImageFailed(true)}
      />
    );
  }

  return <UserRound aria-hidden="true" className="size-5" />;
}

export function SidebarAccount({
  compact,
  contentVisible,
  onSignOut,
  signingOut,
  user,
}: SidebarAccountProps) {
  const displayName = user.name || "SodAIユーザー";
  const labelVisibilityClass = contentVisible
    ? "opacity-100 delay-100 motion-reduce:delay-0"
    : "pointer-events-none opacity-0";

  return (
    <Popover
      collisionPadding={6}
      placement={compact ? "right-end" : "top-start"}
      matchTriggerWidth={!compact}
    >
      <PopoverTrigger
        aria-haspopup="dialog"
        aria-label={`${displayName}のアカウントメニュー`}
        className="flex h-9 w-full items-center rounded-xl text-[var(--text)] transition-colors duration-150 hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
      >
        <span className="grid shrink-0 place-items-center px-2.5" aria-hidden="true">
          <AccountAvatar key={user.image} image={user.image} />
        </span>
        <span
          className={`min-w-0 flex-1 truncate pr-2 text-left text-sm font-medium transition-opacity duration-150 ${
            compact ? "lg:w-0 lg:overflow-hidden lg:pr-0" : ""
          } ${labelVisibilityClass}`}
        >
          {displayName}
        </span>
      </PopoverTrigger>

      <PopoverContent
        role="dialog"
        aria-label="アカウントメニュー"
        className={compact ? "w-60" : ""}
      >
        <div className="flex items-center">
          <span className="grid shrink-0 place-items-center px-2.5" aria-hidden="true">
            <AccountAvatar key={user.image} image={user.image} />
          </span>
          <div className="min-w-0 flex-1 py-2 pr-3">
            <p className="truncate text-sm font-medium text-[var(--text)]">
              {displayName}
            </p>
            <p className="mt-0.5 truncate text-xs text-[var(--muted)]">
              {user.email}
            </p>
          </div>
        </div>
        <div className="mx-2 my-1 h-px bg-[var(--divider)]" />
        <ThemeSelector />
        <div className="mx-2 my-1 h-px bg-[var(--divider)]" />
        <PopoverClose
          disabled={signingOut}
          className="flex h-9 w-full items-center rounded-xl text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] disabled:cursor-wait disabled:opacity-40"
          onClick={onSignOut}
        >
          <span className="grid w-10 shrink-0 place-items-center" aria-hidden="true">
            <LogOut className="size-[17px]" />
          </span>
          <span>{signingOut ? "ログアウト中…" : "ログアウト"}</span>
        </PopoverClose>
      </PopoverContent>
    </Popover>
  );
}
