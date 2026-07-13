import { ThreadShell } from "@/components/chat/thread-shell";

export default async function ThreadPage({ params }: PageProps<"/t/[id]">) {
  const { id } = await params;
  return <ThreadShell key={id} threadId={id} />;
}
