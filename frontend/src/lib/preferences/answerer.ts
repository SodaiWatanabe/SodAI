import type { AvailableAnswerer } from "@/lib/chat/types";

export const PREFERRED_ANSWERER_COOKIE_NAME = "sodai_preferred_answerer";

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;
const MAX_ANSWERER_ID_LENGTH = 128;

type AnswererPreferenceOption = Pick<
  AvailableAnswerer,
  "id" | "is_default"
>;

export function parsePreferredAnswerer(
  value: string | undefined,
): AvailableAnswerer["id"] | undefined {
  return value && value.length <= MAX_ANSWERER_ID_LENGTH ? value : undefined;
}

export function resolvePreferredAnswerer(
  answerers: readonly AnswererPreferenceOption[],
  preferredAnswerer: AvailableAnswerer["id"] | undefined,
): AvailableAnswerer["id"] | undefined {
  return (
    answerers.find((answerer) => answerer.id === preferredAnswerer)?.id ??
    answerers.find((answerer) => answerer.is_default)?.id ??
    answerers[0]?.id
  );
}

export function createPreferredAnswererCookie(
  answerer: AvailableAnswerer["id"],
  secure: boolean,
) {
  const attributes = [
    `${PREFERRED_ANSWERER_COOKIE_NAME}=${encodeURIComponent(answerer)}`,
    "Path=/",
    `Max-Age=${COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ];

  if (secure) attributes.push("Secure");
  return attributes.join("; ");
}

export function savePreferredAnswerer(answerer: AvailableAnswerer["id"]) {
  document.cookie = createPreferredAnswererCookie(
    answerer,
    window.location.protocol === "https:",
  );
}
