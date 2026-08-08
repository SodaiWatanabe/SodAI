export type MessageMarkdownBlock =
  | { kind: "text"; content: string }
  | { kind: "unordered-list"; items: string[] }
  | { kind: "ordered-list"; start: number; items: string[] };

const UNORDERED_LIST_ITEM = /^-\s+(.*)$/;
const ORDERED_LIST_ITEM = /^(\d+)\.\s+(.*)$/;

export function hasMessageListMarkdown(content: string): boolean {
  return content
    .split("\n")
    .some(
      (line) =>
        UNORDERED_LIST_ITEM.test(line) || ORDERED_LIST_ITEM.test(line),
    );
}

export function parseMessageMarkdown(content: string): MessageMarkdownBlock[] {
  const blocks: MessageMarkdownBlock[] = [];
  let textLines: string[] = [];
  let unorderedItems: string[] = [];
  let orderedItems: string[] = [];
  let orderedStart = 1;

  function flushText() {
    if (textLines.length === 0) return;
    blocks.push({ kind: "text", content: textLines.join("\n") });
    textLines = [];
  }

  function flushUnorderedList() {
    if (unorderedItems.length === 0) return;
    blocks.push({ kind: "unordered-list", items: unorderedItems });
    unorderedItems = [];
  }

  function flushOrderedList() {
    if (orderedItems.length === 0) return;
    blocks.push({
      kind: "ordered-list",
      start: orderedStart,
      items: orderedItems,
    });
    orderedItems = [];
  }

  for (const line of content.split("\n")) {
    const unorderedItem = line.match(UNORDERED_LIST_ITEM);
    if (unorderedItem) {
      flushText();
      flushOrderedList();
      unorderedItems.push(unorderedItem[1]);
      continue;
    }

    const orderedItem = line.match(ORDERED_LIST_ITEM);
    if (orderedItem) {
      flushText();
      flushUnorderedList();
      if (orderedItems.length === 0) {
        orderedStart = Number.parseInt(orderedItem[1], 10);
      }
      orderedItems.push(orderedItem[2]);
      continue;
    }

    flushUnorderedList();
    flushOrderedList();
    textLines.push(line);
  }

  flushUnorderedList();
  flushOrderedList();
  flushText();
  return blocks;
}
