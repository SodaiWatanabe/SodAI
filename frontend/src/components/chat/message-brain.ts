import type {
  AvailableAnswerer,
  ThreadEntry,
} from "@/lib/chat/types";

export type MessageBrain = {
  name: string;
};

export function resolveMessageBrain(
  entry: ThreadEntry,
  answerers: AvailableAnswerer[],
): MessageBrain {
  const answerer = answerers.find((option) => option.id === entry.answerer);
  return {
    name: answerer?.name ?? entry.author.name,
  };
}
