export type BrainStar = {
  alpha: number;
  depth: number;
  driftX: number;
  driftY: number;
  glow: boolean;
  phase: number;
  radius: number;
  twinkleAmount: number;
  twinkleSpeed: number;
  x: number;
  y: number;
};

const MIN_STAR_COUNT = 96;
const MAX_STAR_COUNT = 220;
const AREA_PER_STAR = 5_500;
const QUIET_ZONE_X_RADIUS = 0.18;
const QUIET_ZONE_Y_RADIUS = 0.13;
const QUIET_ZONE_REJECTION_RATE = 0.78;
const PRONOUNCED_TWINKLE_MINIMUM = 0.5;

function createRandom(seed: number) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let mixed = value;
    mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4_294_967_296;
  };
}

export function isInsideBrainStarfieldQuietZone(x: number, y: number) {
  const normalizedX = (x - 0.5) / QUIET_ZONE_X_RADIUS;
  const normalizedY = (y - 0.5) / QUIET_ZONE_Y_RADIUS;
  return normalizedX * normalizedX + normalizedY * normalizedY < 1;
}

export function resolveBrainStarAlpha(
  star: BrainStar,
  elapsedSeconds: number,
) {
  const wave = Math.sin(
    elapsedSeconds * star.twinkleSpeed + star.phase,
  );
  const twinkle =
    star.twinkleAmount >= PRONOUNCED_TWINKLE_MINIMUM
      ? 0.18 +
        Math.pow((wave + 1) / 2, 3) * (1.25 + star.twinkleAmount)
      : 1 + wave * star.twinkleAmount;

  return Math.max(0, Math.min(1, star.alpha * twinkle));
}

export function createBrainStarfield(
  width: number,
  height: number,
  seed = 0x57a2f13d,
) {
  const safeWidth = Math.max(width, 1);
  const safeHeight = Math.max(height, 1);
  const starCount = Math.max(
    MIN_STAR_COUNT,
    Math.min(
      MAX_STAR_COUNT,
      Math.round((safeWidth * safeHeight) / AREA_PER_STAR),
    ),
  );
  const random = createRandom(seed);
  const stars: BrainStar[] = [];
  const maximumAttempts = starCount * 20;

  for (
    let attempts = 0;
    stars.length < starCount && attempts < maximumAttempts;
    attempts += 1
  ) {
    const x = random();
    const y = random();
    if (
      isInsideBrainStarfieldQuietZone(x, y) &&
      random() < QUIET_ZONE_REJECTION_RATE
    ) {
      continue;
    }

    const depth = random();
    const glow = random() < 0.045;
    const pronouncedTwinkle = glow || random() < 0.14;
    stars.push({
      alpha: Math.min(
        0.68,
        0.1 + depth * 0.34 + (glow ? 0.12 : 0),
      ),
      depth,
      driftX: (random() - 0.5) * (0.22 + depth * 0.5),
      driftY: (random() - 0.5) * (0.14 + depth * 0.34),
      glow,
      phase: random() * Math.PI * 2,
      radius: 0.38 + depth * 0.78 + (glow ? 0.42 : 0),
      twinkleAmount: pronouncedTwinkle
        ? PRONOUNCED_TWINKLE_MINIMUM +
          random() * (glow ? 0.3 : 0.22)
        : 0.04 + random() * 0.06,
      twinkleSpeed: pronouncedTwinkle
        ? 0.85 + random() * 0.65
        : 0.22 + random() * 0.24,
      x,
      y,
    });
  }

  return stars;
}
