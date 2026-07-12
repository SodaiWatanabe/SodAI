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
        width={18}
        height={18}
        referrerPolicy="no-referrer"
        className="size-[18px] rounded-full object-cover"
        onError={() => setImageFailed(true)}
      />
    );
  }

  return <UserRound aria-hidden="true" className="size-[18px]" />;
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
        aria-haspopup="menu"
        aria-label={`${displayName}のアカウントメニュー`}
        className="flex h-9 w-full items-center rounded-xl text-[#1d1d1f] transition-colors duration-150 hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3]"
      >
        <span className="grid w-10 shrink-0 place-items-center" aria-hidden="true">
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
        role="menu"
        aria-label="アカウントメニュー"
        className={compact ? "w-60" : ""}
      >
        <div className="flex items-center">
          <span className="grid w-10 shrink-0 place-items-center" aria-hidden="true">
            <AccountAvatar key={user.image} image={user.image} />
          </span>
          <div className="min-w-0 flex-1 py-2 pr-3">
            <p className="truncate text-sm font-medium text-[#1d1d1f]">
              {displayName}
            </p>
            <p className="mt-0.5 truncate text-xs text-[#6e6e73]">
              {user.email}
            </p>
          </div>
        </div>
        <div className="mx-2 my-1 h-px bg-black/[0.08]" />
        <PopoverClose
          role="menuitem"
          disabled={signingOut}
          className="flex h-9 w-full items-center rounded-xl text-left text-sm text-[#1d1d1f] transition-colors hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071e3] disabled:cursor-wait disabled:opacity-40"
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
