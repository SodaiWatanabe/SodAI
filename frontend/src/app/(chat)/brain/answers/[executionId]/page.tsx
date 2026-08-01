import { notFound } from "next/navigation";

import { HumanAnswerShell } from "@/components/human/human-answer-shell";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function HumanAnswerPage({
  params,
}: {
  params: Promise<{ executionId: string }>;
}) {
  const { executionId } = await params;
  if (!UUID_PATTERN.test(executionId)) notFound();
  return <HumanAnswerShell key={executionId} executionId={executionId} />;
}
