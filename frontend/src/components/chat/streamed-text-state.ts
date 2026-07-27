export type StreamedTextSegment = {
  entering: boolean;
  key: number;
  text: string;
};

export type StreamedTextState = {
  animated: boolean;
  content: string;
  nextKey: number;
  segments: StreamedTextSegment[];
};

export const STREAM_RESPONSE_FADE_DURATION_MS = 180;

export function createStreamedTextState(
  content: string,
  animated: boolean,
): StreamedTextState {
  return {
    animated,
    content,
    nextKey: 1,
    segments: content ? [{ entering: animated, key: 0, text: content }] : [],
  };
}

function compactSettledSegments(
  segments: StreamedTextSegment[],
  settledThroughKey: number | undefined,
) {
  if (settledThroughKey === undefined) return segments;
  const settledIndex = segments.findLastIndex(
    (segment) => segment.key <= settledThroughKey,
  );
  if (settledIndex < 0) return segments;
  if (settledIndex === 0) {
    const first = segments[0];
    return first.entering
      ? [{ ...first, entering: false }, ...segments.slice(1)]
      : segments;
  }
  return [
    {
      entering: false,
      key: segments[0].key,
      text: segments
        .slice(0, settledIndex + 1)
        .map((segment) => segment.text)
        .join(""),
    },
    ...segments.slice(settledIndex + 1),
  ];
}

export function appendStreamedText(
  current: StreamedTextState,
  content: string,
  settledThroughKey?: number,
): StreamedTextState {
  if (content === current.content) return current;

  if (content.startsWith(current.content)) {
    const delta = content.slice(current.content.length);
    const settledSegments = compactSettledSegments(
      current.segments,
      settledThroughKey,
    );
    return {
      animated: current.animated,
      content,
      nextKey: current.nextKey + 1,
      segments: delta
        ? [
            ...settledSegments,
            { entering: current.animated, key: current.nextKey, text: delta },
          ]
        : settledSegments,
    };
  }

  return {
    animated: current.animated,
    content,
    nextKey: current.nextKey + 1,
    segments: content
      ? [
          {
            entering: current.animated,
            key: current.nextKey,
            text: content,
          },
        ]
      : [],
  };
}

export function settleStreamedText(
  current: StreamedTextState,
): StreamedTextState {
  if (!current.animated) return current;
  return {
    animated: false,
    content: current.content,
    nextKey: current.nextKey + 1,
    segments: current.content
      ? [{ entering: false, key: current.nextKey, text: current.content }]
      : [],
  };
}
