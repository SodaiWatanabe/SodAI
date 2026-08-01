export const BRAIN_AUTO_SUBMIT_LEAD_MS = 300;

export function millisecondsUntilBrainAutoSubmit(
  deadlineAt: string,
  now: number = Date.now(),
): number {
  const deadline = Date.parse(deadlineAt);
  return Number.isFinite(deadline)
    ? Math.max(0, deadline - now - BRAIN_AUTO_SUBMIT_LEAD_MS)
    : 0;
}
