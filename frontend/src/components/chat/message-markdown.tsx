import { parseMessageMarkdown } from "@/lib/chat/message-markdown";

type MessageMarkdownProps = {
  content: string;
};

export function MessageMarkdown({ content }: MessageMarkdownProps) {
  return parseMessageMarkdown(content).map((block, index) => {
    if (block.kind === "text") {
      return <span key={index}>{block.content}</span>;
    }

    const items = block.items.map((item, itemIndex) => (
      <li
        key={itemIndex}
        className="grid grid-cols-[1em_minmax(0,1fr)]"
      >
        <span aria-hidden="true" className="select-none tabular-nums">
          {block.kind === "unordered-list"
            ? "•"
            : `${block.start + itemIndex}.`}
        </span>
        <span>{item}</span>
      </li>
    ));
    const className = "my-2 list-none space-y-1 whitespace-normal p-0";

    return block.kind === "unordered-list" ? (
      <ul key={index} role="list" className={className}>
        {items}
      </ul>
    ) : (
      <ol
        key={index}
        role="list"
        start={block.start}
        className={className}
      >
        {items}
      </ol>
    );
  });
}
