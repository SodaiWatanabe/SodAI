import type { AvailableAnswerer } from "@/lib/chat/types";

type AnswererKind = Pick<AvailableAnswerer, "kind">;

export function shouldShowHumanPrivacyDialog(
  currentAnswerer: AnswererKind | undefined,
  nextAnswerer: AnswererKind | undefined,
) {
  return currentAnswerer?.kind === "ai" && nextAnswerer?.kind === "human";
}
