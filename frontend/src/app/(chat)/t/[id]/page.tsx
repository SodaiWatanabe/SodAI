import { ThreadShell } from "@/components/chat/thread-shell";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function ThreadPage(props: PageProps<"/t/[id]">) {
  const [{ id }, searchParams] = await Promise.all([
    props.params,
    props.searchParams,
  ]);
  const entry = searchParams.entry;
  const targetEntryId =
    typeof entry === "string" && UUID_PATTERN.test(entry) ? entry : undefined;

  return (
    <ThreadShell
      key={id}
      threadId={id}
      targetEntryId={targetEntryId}
    />
  );
}
