export function shouldSubmitMessageFromKeyboard(
  {
    coarsePrimaryPointer,
    enabled,
    shortcutMatches,
  }: {
    coarsePrimaryPointer: boolean;
    enabled: boolean;
    shortcutMatches: boolean;
  },
) {
  return enabled && !coarsePrimaryPointer && shortcutMatches;
}
