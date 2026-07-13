import { redirect } from "next/navigation";

import { AccountSettingsForm } from "@/components/settings/account-settings-form";
import { SettingsReloadButton } from "@/components/settings/settings-reload-button";
import { getCurrentAccount } from "@/lib/account/server";

export async function AccountSettingsPanel() {
  const account = await getCurrentAccount();

  if (!account) {
    return (
      <div className="w-full px-5 pb-7 pt-2 sm:px-6 sm:pb-8 sm:pt-2">
        <div role="alert" className="text-center">
          <p className="text-sm font-medium text-[var(--text)]">
            アカウント情報を読み込めませんでした。
          </p>
          <SettingsReloadButton />
        </div>
      </div>
    );
  }

  if (account.status !== "active" || account.display_name === null) {
    redirect("/");
  }

  return (
    <div className="w-full px-5 pb-7 pt-2 sm:px-6 sm:pb-8 sm:pt-2">
      <AccountSettingsForm initialDisplayName={account.display_name} />
    </div>
  );
}
