export function millisecondsUntilBrainSkipCloses(
  skipAllowedUntil: string,
  now: number = Date.now(),
): number {
  const boundary = Date.parse(skipAllowedUntil);
  return Number.isFinite(boundary) ? Math.max(0, boundary - now) : 0;
}

export function isBrainSkipAllowed(
  skipAllowedUntil: string,
  now: number = Date.now(),
): boolean {
  return millisecondsUntilBrainSkipCloses(skipAllowedUntil, now) > 0;
}
