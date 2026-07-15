export type SearchHighlightSegment = {
  highlighted: boolean;
  text: string;
};

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function splitSearchHighlight(
  text: string,
  query: string,
): SearchHighlightSegment[] {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) return [{ highlighted: false, text }];

  const matches = text.matchAll(
    new RegExp(escapeRegExp(normalizedQuery), "giu"),
  );
  const segments: SearchHighlightSegment[] = [];
  let cursor = 0;

  for (const match of matches) {
    const index = match.index;
    if (index > cursor) {
      segments.push({ highlighted: false, text: text.slice(cursor, index) });
    }
    segments.push({ highlighted: true, text: match[0] });
    cursor = index + match[0].length;
  }

  if (cursor < text.length) {
    segments.push({ highlighted: false, text: text.slice(cursor) });
  }
  return segments.length > 0 ? segments : [{ highlighted: false, text }];
}
