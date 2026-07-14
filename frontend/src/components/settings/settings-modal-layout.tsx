import { redirect } from "next/navigation";

import { AccountSettingsPanel } from "@/components/settings/account-settings-panel";
import { CreditSettings } from "@/components/settings/credit-settings";
import { GeneralSettings } from "@/components/settings/general-settings";
import { KeyboardSettings } from "@/components/settings/keyboard-settings";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { getCurrentSession } from "@/lib/auth/session";

export async function SettingsModalLayout({
  closeMode,
}: {
  closeMode: "back" | "home";
}) {
  const session = await getCurrentSession();
  if (!session) redirect("/");

  return (
    <SettingsDialog
      accountPanel={<AccountSettingsPanel />}
      closeMode={closeMode}
      creditPanel={<CreditSettings />}
      generalPanel={<GeneralSettings />}
      keyboardPanel={<KeyboardSettings />}
    />
  );
}
