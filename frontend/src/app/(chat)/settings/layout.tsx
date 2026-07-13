import { HomeView } from "@/components/chat/home-view";
import { SettingsModalLayout } from "@/components/settings/settings-modal-layout";

export default function SettingsLayout() {
  return (
    <>
      <HomeView />
      <SettingsModalLayout closeMode="home" />
    </>
  );
}
