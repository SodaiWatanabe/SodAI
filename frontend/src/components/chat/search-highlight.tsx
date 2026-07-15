import { memo } from "react";

import { splitSearchHighlight } from "@/lib/chat/search-highlight";

type SearchHighlightProps = {
  markFirstMatch?: boolean;
  query: string;
  text: string;
};

export const SearchHighlight = memo(function SearchHighlight({
  markFirstMatch = false,
  query,
  text,
}: SearchHighlightProps) {
  const segments = splitSearchHighlight(text, query);
  const firstMatchIndex = segments.findIndex((segment) => segment.highlighted);

  return segments.map((segment, index) =>
    segment.highlighted ? (
      <mark
        key={index}
        data-search-highlight-target={
          markFirstMatch && index === firstMatchIndex ? "" : undefined
        }
        className="rounded bg-[var(--search-highlight)] px-0.5 text-inherit"
      >
        {segment.text}
      </mark>
    ) : (
      segment.text
    ),
  );
});
