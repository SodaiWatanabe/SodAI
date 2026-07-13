const DESKTOP_VIEWPORT = "(min-width: 64rem)";

export function settleComposerFocus(input: HTMLInputElement | null) {
  requestAnimationFrame(() => {
    if (!input?.isConnected) return;
    if (window.matchMedia(DESKTOP_VIEWPORT).matches) {
      input.focus({ preventScroll: true });
      return;
    }
    input.blur();
  });
}
