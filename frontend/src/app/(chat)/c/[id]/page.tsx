import { ConversationShell } from "@/components/chat/conversation-shell";

export default async function ConversationPage({
  params,
}: PageProps<"/c/[id]">) {
  const { id } = await params;
  return <ConversationShell key={id} conversationId={id} />;
}
