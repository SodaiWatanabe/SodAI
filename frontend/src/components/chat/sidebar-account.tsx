"use client";

import { LogOut, Settings, UserRound } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { AccountCreditUsage } from "@/components/chat/account-credit-usage";

export type SidebarUser = {
  email: string;
  image: string | null;
  name: string;
};

type SidebarAccountProps = {
  compact: boolean;
  contentVisible: boolean;
  onOpenSettings: () => void;
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
  onOpenSettings,
  onSignOut,
  signingOut,
  user,
}: SidebarAccountProps) {
  const displayName = user.name || "SodAIユーザー";
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [creditRequestVersion, setCreditRequestVersion] = useState(0);
  const labelVisibilityClass = contentVisible
    ? "opacity-100 delay-100 motion-reduce:delay-0"
    : "pointer-events-none opacity-0";

  return (
    <Popover
      collisionPadding={6}
      placement={compact ? "right-end" : "top-start"}
      matchTriggerWidth={!compact}
      onOpenChange={(open) => {
        setAccountMenuOpen(open);
        if (open) setCreditRequestVersion((version) => version + 1);
      }}
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
        className={compact ? "grid w-60 gap-0.5" : "grid gap-0.5"}
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
        <AccountCreditUsage
          active={accountMenuOpen}
          requestVersion={creditRequestVersion}
          onRetry={() => setCreditRequestVersion((version) => version + 1)}
        />
        <div className="mx-2 my-1 h-px bg-[var(--divider)]" />
        <PopoverClose
          className="flex h-9 w-full items-center rounded-xl text-left text-sm text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
          onClick={onOpenSettings}
        >
          <span className="grid w-10 shrink-0 place-items-center" aria-hidden="true">
            <Settings className="size-[17px]" />
          </span>
          <span>設定</span>
        </PopoverClose>
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
