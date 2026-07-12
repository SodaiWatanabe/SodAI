import { randomInt } from "node:crypto";

import { connection } from "next/server";

import { ChatShell } from "@/components/chat/chat-shell";
import { isGoogleAuthConfigured } from "@/lib/auth/environment";
import { getCurrentSession } from "@/lib/auth/session";

type HomeProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

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

export default async function Home({ searchParams }: HomeProps) {
  await connection();
  const [params, session] = await Promise.all([
    searchParams,
    getCurrentSession(),
  ]);
  const authError = params.authError;
  const greeting = greetings[randomInt(greetings.length)];

  return (
    <ChatShell
      greeting={greeting}
      googleAuthEnabled={isGoogleAuthConfigured()}
      initialUser={
        session?.user
          ? { email: session.user.email, name: session.user.name }
          : null
      }
      initialGoogleAuthError={
        authError === "google" ||
        (Array.isArray(authError) && authError.includes("google"))
      }
    />
  );
}
