export type AuthStep = "blocked" | "email" | "otp" | "resolving" | "profile";

type InitialAuthState = {
  accountUnavailable: boolean;
  resumeProfile: boolean;
};

type ResolvedAccount = {
  display_name: string | null;
  status: "active" | "suspended" | "disabled";
};

export type AccountDestination = "authenticated" | "blocked" | "profile";

export function getInitialAuthStep({
  accountUnavailable,
  resumeProfile,
}: InitialAuthState): AuthStep {
  if (accountUnavailable) return "blocked";
  if (resumeProfile) return "profile";
  return "email";
}

export function getAccountDestination(
  account: ResolvedAccount,
): AccountDestination {
  if (account.status !== "active") return "blocked";
  if (!account.display_name) return "profile";
  return "authenticated";
}
