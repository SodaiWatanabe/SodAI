import { randomInt } from "node:crypto";

import { connection } from "next/server";

import { ChatShell } from "@/components/chat/chat-shell";

const greetings = [
  "こんにちは。",
  "お手伝いさせてください。",
  "今日はどんな気分ですか？",
  "またお会いしましたね。",
  "どんな話をしましょうか。",
  "あなたを笑顔にします。",
  "おかえりなさい。",
  "ようこそ。",
] as const;

export async function HomeView() {
  await connection();
  return <ChatShell greeting={greetings[randomInt(greetings.length)]} />;
}
